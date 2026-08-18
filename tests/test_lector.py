"""Testes da leitura de documentos (lector.py) — texto, apartados, diff."""
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import lector  # noqa: E402


def test_referencias_citadas_so_com_ancora():
    txt = "Corregido en el apartado 3.2 y actualizada la pág. 14. Enviado el 12/03/2026."
    refs = lector.referencias_citadas(txt)
    assert "3.2" in refs
    assert "14" in refs
    # A data (12/03/2026) e o número solto não entram: não têm palavra-âncora.
    assert "12" not in refs and "2026" not in refs


def test_referencias_ordem_sem_repetir():
    txt = "Ver sección 2, sección 2 de novo, y el punto 5.1."
    assert lector.referencias_citadas(txt) == ["2", "5.1"]


def test_localizar_seccion_encontra_cabecalho():
    doc = "1 Introducción\nblah\n3.2 Gestión de la seguridad\nEl plan define X Y Z.\n4 Anexos"
    trecho = lector.localizar_seccion(doc, "3.2", janela=50)
    assert trecho is not None
    assert trecho.startswith("3.2 Gestión de la seguridad")


def test_localizar_seccion_inexistente_devolve_none():
    doc = "1 Introducción\n2 Alcance\n3 Conclusión"
    assert lector.localizar_seccion(doc, "9.9") is None


def test_localizar_nao_confunde_numero_no_meio():
    # "3.2" no meio de uma frase não é cabeçalho; só conta no início da linha.
    doc = "Como se ve en el apartado 3.2 esto es texto corrido, no un título."
    assert lector.localizar_seccion(doc, "3.2") is None


def test_diff_versoes_mostra_mudancas():
    v5 = "Linea igual\nParrafo antiguo sobre el peligro\nOtra linea igual"
    v6 = "Linea igual\nParrafo NUEVO con la mitigacion\nOtra linea igual"
    d = lector.diff_versoes(v5, v6)
    assert any(l.startswith("-") and "antiguo" in l for l in d)
    assert any(l.startswith("+") and "NUEVO" in l for l in d)
    # As linhas iguais não aparecem.
    assert not any("igual" in l for l in d)


def test_extract_text_tipo_nao_suportado():
    assert lector.extract_text("qualquer.dwg") == ""
    assert "não legível" in lector.motivo_vazio("qualquer.dwg")


def _docx_minimo(dest: Path, *paragrafos: str) -> None:
    corpo = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragrafos)
    xml = (
        '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
        f"{corpo}</w:body></w:document>"
    )
    with zipfile.ZipFile(dest, "w") as z:
        z.writestr("word/document.xml", xml)


def test_docx_text_roundtrip():
    # Monta um .docx mínimo num diretório temporário e lê de volta.
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "doc.docx"
        _docx_minimo(dest, "3.2 Gestión de la seguridad", "El plan define las medidas.")
        txt = lector.extract_text(dest)
    assert "Gestión de la seguridad" in txt
    assert lector.localizar_seccion(txt, "3.2") is not None


class _PdfReaderLento:
    """Simula um pypdf.PdfReader que nunca devolve (PDF corrompido/gigante)."""

    def __init__(self, _path):
        import time

        time.sleep(5)  # bem mais que o PDF_TIMEOUT_S reduzido no teste

    pages: list = []


class _PdfReaderRapido:
    class _Pagina:
        def extract_text(self):
            return "3.2 Gestión de la seguridad presente."

    def __init__(self, _path):
        self.pages = [self._Pagina()]


def test_pdf_timeout_nao_trava_e_explica_motivo():
    # PDF "lento" nunca devolve: extract_text deve voltar rápido (não travar
    # o teste) e motivo_vazio deve explicar que foi por timeout.
    import types

    fake = types.SimpleNamespace(PdfReader=_PdfReaderLento)
    ok_orig, pypdf_orig, timeout_orig = lector.PDF_OK, getattr(lector, "pypdf", None), lector.PDF_TIMEOUT_S
    lector.PDF_OK = True
    lector.pypdf = fake
    lector.PDF_TIMEOUT_S = 0.3
    try:
        texto = lector.extract_text("qualquer.pdf")
        assert texto == ""
        assert "excedeu" in lector.motivo_vazio("qualquer.pdf")
    finally:
        lector.PDF_OK = ok_orig
        if pypdf_orig is not None:
            lector.pypdf = pypdf_orig
        lector.PDF_TIMEOUT_S = timeout_orig


def test_pdf_rapido_le_normalmente_dentro_do_timeout():
    import types

    fake = types.SimpleNamespace(PdfReader=_PdfReaderRapido)
    ok_orig, pypdf_orig = lector.PDF_OK, getattr(lector, "pypdf", None)
    lector.PDF_OK = True
    lector.pypdf = fake
    try:
        texto = lector.extract_text("outro.pdf")
        assert "Gestión de la seguridad" in texto
    finally:
        lector.PDF_OK = ok_orig
        if pypdf_orig is not None:
            lector.pypdf = pypdf_orig


def test_o_mesmo_ficheiro_nao_e_lido_duas_vezes():
    # O 'leer' e o 'radar' percorrem a mesma pasta um a seguir ao outro. Sem
    # cache, cada .pdf lento é pago duas vezes — era o passo 2 a demorar o dobro.
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "doc.txt"
        p.write_text("3.2 Gestión de la seguridad", encoding="utf-8")

        leituras = []
        original = lector._extract_text_sem_cache

        def contar(path):
            leituras.append(str(path))
            return original(path)

        lector._extract_text_sem_cache = contar
        lector._CACHE.clear()
        try:
            primeira = lector.extract_text(p)
            segunda = lector.extract_text(p)
        finally:
            lector._extract_text_sem_cache = original

        assert primeira == segunda == "3.2 Gestión de la seguridad"
        assert len(leituras) == 1


def test_ficheiro_alterado_e_relido():
    # A cache é por (mtime, tamanho): se o documento foi substituído por uma
    # versão nova entre dois comandos, tem de ser lido outra vez.
    import os

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "doc.txt"
        p.write_text("versão 1", encoding="utf-8")
        lector._CACHE.clear()
        assert lector.extract_text(p) == "versão 1"

        p.write_text("versão 2 (revista)", encoding="utf-8")
        os.utime(p, (0, 0))  # garante mtime diferente mesmo em relógios grosseiros
        assert lector.extract_text(p) == "versão 2 (revista)"


def test_documento_quase_sem_texto_e_assinalado():
    """Uma digitalização "lê-se" com êxito e devolve quase nada.

    Sem este aviso, um PDF de 4 caracteres passava por documento lido: o
    checklist dava tudo por ausente (como se faltassem partes ao documento, e
    não a leitura) e o radar dava-o "sem pistas", igual a um documento limpo.
    """
    assert lector.aviso_texto_curto("x" * 4)
    assert "OCR" in lector.aviso_texto_curto("x" * 4)
    assert "4 caracteres" in lector.aviso_texto_curto("x" * 4)


def test_documento_com_texto_a_serio_nao_e_assinalado():
    assert lector.aviso_texto_curto("y" * lector.MIN_TEXTO_UTIL) == ""
    assert lector.texto_utilizavel("y" * lector.MIN_TEXTO_UTIL)


def test_ficheiro_totalmente_vazio_tem_o_outro_aviso():
    # Zero caracteres já era tratado por motivo_vazio — não se duplica a queixa.
    assert lector.aviso_texto_curto("") == ""
    assert lector.aviso_texto_curto("   ") == ""


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    sys.exit(1 if failed else 0)
