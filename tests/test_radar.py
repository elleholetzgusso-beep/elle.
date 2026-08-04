"""Testes do radar dirigido (radar.py).

Cada teste monta uma base mínima (linhas no formato do harvest) e verifica que:
  - o radar cruza o texto real com a base certa (por tipo de documento);
  - as sondas disparam com apoio histórico e ficam caladas sem ele;
  - a exclusão de obra evita "colar da própria resposta";
  - o radar nunca inventa: sem sinal no texto, sem pista.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import radar  # noqa: E402


def _row(**kw):
    base = {"fuente": "LPA-X", "documento": "", "punto": "", "valoracion": "Crítico",
            "estado": "Cerrado", "hallazgo": "", "discusion": "", "obra": "EXC2025-00001", "tema": ""}
    base.update(kw)
    return base


def _rep_row(**kw):
    kw.setdefault("documento", "Anejo 12. Registro de Peligros (REP)")
    kw.setdefault("tema", "Hazard Log / REP")
    return _row(**kw)


def _escrever(dir_: Path, nome: str, texto: str) -> Path:
    p = dir_ / nome
    p.write_text(texto, encoding="utf-8")
    return p


# --- frentes / base_do_tipo ------------------------------------------------

def test_base_do_tipo_filtra_por_tipo_de_documento():
    base = [
        _rep_row(hallazgo="perigo sem evidencia"),
        _row(documento="Safety Case del sistema", hallazgo="falta conclusion", tema="Safety Case"),
    ]
    rep = radar.base_do_tipo(base, "REP / Registro de Peligros")
    assert len(rep) == 1
    assert "peligros" in radar.guide.tipo_documento(rep[0]["documento"]).lower()


def test_excluir_obra_remove_a_propria_obra_da_base():
    base = [
        _rep_row(obra="EXC2026-16883-002", hallazgo="da propria obra"),
        _rep_row(obra="EXC2025-04019", hallazgo="de outra obra"),
    ]
    fora = radar.base_do_tipo(base, "REP / Registro de Peligros", excluir_obra="EXC2026-16883")
    assert len(fora) == 1
    assert fora[0]["obra"] == "EXC2025-04019"


def test_frentes_por_tema_ordena_criticos_primeiro():
    rows = [
        _rep_row(tema="V&V", valoracion="Importante"),
        _rep_row(tema="Hazard Log / REP", valoracion="Crítico"),
        _rep_row(tema="Hazard Log / REP", valoracion="Crítico"),
    ]
    frentes = radar.frentes_por_tema(rows)
    assert frentes[0]["tema"] == "Hazard Log / REP"
    assert frentes[0]["criticos"] == 2


# --- sondas -----------------------------------------------------------------

def test_sonda_anexos_cruzados_deteta_nome_divergente(tmp_path):
    base = [_rep_row(hallazgo="como evidencia aparece Anejo 5. Estructuras sin embargo no es")]
    texto = ("Registro de peligros. Peligro 1: caida. Evidencia: Anejo 5. Estructuras.\n"
             "Peligro 6: drenaje. Evidencia: Anejo 5. Climatologia.")
    p = _escrever(tmp_path, "Anejo 12. Registro de Peligros (REP).txt", texto)
    reg = radar.analisar_documento(p, base)
    titulos = [x.titulo for x in reg["pistas"]]
    assert any("Anexo 5" in t and "inconsistente" in t for t in titulos)


def test_sonda_anexos_cruzados_nao_dispara_quando_coerente(tmp_path):
    base = [_rep_row(hallazgo="evidencia Anejo 5")]
    texto = ("Peligro 1. Evidencia: Anejo 5. Estructuras.\n"
             "Peligro 2. Evidencia: Anejo 5. Estructuras.")
    p = _escrever(tmp_path, "Anejo 12. Registro de Peligros (REP).txt", texto)
    reg = radar.analisar_documento(p, base)
    assert not any("inconsistente" in x.titulo for x in reg["pistas"])


def test_sonda_evidencias_dispara_com_apoio_e_cala_sem_apoio(tmp_path):
    texto = "Registro de peligros. Peligro 1: caida a la via."  # sem a palavra 'evidencia'
    p = _escrever(tmp_path, "Anejo 12. Registro de Peligros (REP).txt", texto)

    com_apoio = radar.analisar_documento(p, [_rep_row(hallazgo="no se observa columna de Evidencias")])
    assert any("Evidencias" in x.titulo for x in com_apoio["pistas"])

    # Sem nenhum hallazgo histórico do tipo que fale de evidencia, a sonda cala-se
    # (não inventa apoio que não existe).
    sem_apoio = radar.analisar_documento(p, [_rep_row(hallazgo="tema totalmente diferente")])
    assert not any("Evidencias" in x.titulo for x in sem_apoio["pistas"])


def test_sonda_id_nao_dispara_quando_ha_ids(tmp_path):
    base = [_rep_row(hallazgo="falta un ID para cada requisito")]
    texto = "Peligro ID-333: caida. Peligro ID-334: drenaje. Evidencia presente. estado del riesgo: abierto."
    p = _escrever(tmp_path, "Anejo 12. Registro de Peligros (REP).txt", texto)
    reg = radar.analisar_documento(p, base)
    assert not any("ID único" in x.titulo for x in reg["pistas"])


def test_documento_ilegivel_nao_rebenta(tmp_path):
    p = tmp_path / "imagem.png"
    p.write_bytes(b"\x89PNG not-text")
    reg = radar.analisar_documento(p, [])
    assert reg["caracteres"] == 0
    assert reg["pistas"] == []
    assert reg["notas"]


def test_relatorio_menciona_porque_e_onde(tmp_path):
    base = [_rep_row(hallazgo="no se observa columna de Evidencias", fuente="LPA-DEMO")]
    texto = "Registro de peligros. Peligro 1 sin nada."
    p = _escrever(tmp_path, "Anejo 12. Registro de Peligros (REP).txt", texto)
    reg = radar.analisar_documento(p, base)
    txt = radar.relatorio([reg])
    assert "porquê:" in txt and "onde:" in txt
    assert "não é veredito" in txt.lower()


if __name__ == "__main__":
    import traceback
    falhas = 0
    for nome, fn in sorted(globals().items()):
        if nome.startswith("test_") and callable(fn):
            try:
                import inspect
                if "tmp_path" in inspect.signature(fn).parameters:
                    import tempfile
                    with tempfile.TemporaryDirectory() as d:
                        fn(Path(d))
                else:
                    fn()
                print(f"ok  {nome}")
            except Exception:
                falhas += 1
                print(f"FALHOU  {nome}")
                traceback.print_exc()
    sys.exit(1 if falhas else 0)
