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
