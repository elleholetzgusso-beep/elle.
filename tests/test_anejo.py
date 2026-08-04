"""Testes do Anejo A.2 — Base de Datos de No Conformidades (PE/05).

Um registo de compliance auditável tem duas obrigações que estes testes fixam:

  * a chave é o ID estável, não o nº de apresentação — senão a mesma não
    conformidade muda de identidade entre revisões;
  * o que não é derivável do diálogo fica ``(a preencher)``, nunca um valor
    plausível inventado.
"""
import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from lpa_filler import anejo  # noqa: E402


def _punto(id_="H-001", n=1, estado="Cerrado", dialogo=None):
    return {
        "id": id_,
        "n": n,
        "estado": estado,
        "dialogo": dialogo if dialogo is not None else [
            {"tipo": "Hallazgo", "texto": "Falta el análisis de riesgos."},
            {"tipo": "Respuesta UTE (02/02/2026)", "texto": "Se incorpora en la v0.6."},
            {"tipo": "Respuesta Exceltic (10/02/2026)", "texto": "Verificado."},
        ],
    }


# --- chave do registo -------------------------------------------------------

def test_a_chave_e_o_id_e_o_n_fica_como_referencia():
    linha = anejo.punto_to_anejo(_punto(id_="H-042", n=7))
    assert linha["id"] == "H-042"
    assert linha["n"] == 7
    assert anejo.CAMPOS[0] == "id"


def test_punto_sem_id_nao_inventa_chave():
    """Melhor uma chave visivelmente por preencher do que uma fabricada."""
    pt = _punto()
    del pt["id"]
    assert anejo.punto_to_anejo(pt)["id"] == anejo.A_PREENCHER


# --- filtro por ID ----------------------------------------------------------

def _projeto():
    return {"puntos": [_punto("H-001", 1), _punto("H-005", 2), _punto("H-009", 3)]}


def test_solo_seleciona_por_id_e_aceita_formas_abreviadas():
    linhas = anejo.build(_projeto(), solo=["H-005", "9"])
    assert [ln["id"] for ln in linhas] == ["H-005", "H-009"]


def test_solo_segue_o_hallazgo_e_nao_a_posicao():
    """O filtro tem de resistir à renumeração: pedir H-005 traz o H-005, mesmo
    que ele já não seja o segundo punto da folha."""
    projeto = _projeto()
    projeto["puntos"].insert(0, _punto("H-011", 1))
    for i, pt in enumerate(projeto["puntos"], start=1):   # renumera o 'n'
        pt["n"] = i
    linhas = anejo.build(projeto, solo=["H-005"])
    assert len(linhas) == 1 and linhas[0]["id"] == "H-005" and linhas[0]["n"] == 3


def test_id_inexistente_e_erro_e_nao_uma_linha_em_falta():
    with pytest.raises(anejo.IdDesconhecido, match="H-777"):
        anejo.build(_projeto(), solo=["H-001", "H-777"])


def test_id_ilegivel_e_erro():
    with pytest.raises(anejo.IdDesconhecido, match="ilegíveis"):
        anejo.build(_projeto(), solo=["o quinto"])


def test_sem_solo_gera_todos():
    assert len(anejo.build(_projeto())) == 3


# --- derivação sem fabricar -------------------------------------------------

def test_resultado_verificacion_mapeia_o_estado_pe03():
    esperado = {
        "Cerrado": "Verificada y cerrada",
        "Resuelto": "Aceptada, pendiente de evidencia",
        "Abierto": "Pendiente",
    }
    for estado, texto in esperado.items():
        assert anejo.punto_to_anejo(_punto(estado=estado))["resultado_verificacion"] == texto


def test_responsable_e_a_parte_que_responde_nao_o_avaliador():
    assert anejo.punto_to_anejo(_punto())["responsable"] == "UTE"


def test_fecha_cierre_so_existe_se_o_punto_esta_cerrado():
    assert anejo.punto_to_anejo(_punto(estado="Cerrado"))["fecha_cierre"] == "10/02/2026"
    assert anejo.punto_to_anejo(_punto(estado="Abierto"))["fecha_cierre"] == ""


def test_dialogo_sem_respostas_deixa_a_preencher_em_vez_de_adivinhar():
    pt = _punto(dialogo=[{"tipo": "Hallazgo", "texto": "Falta el REP."}])
    linha = anejo.punto_to_anejo(pt)
    assert linha["accion_a_implantar"] == anejo.A_PREENCHER
    assert linha["responsable"] == anejo.A_PREENCHER
    assert linha["aspecto_detectado"] == "Falta el REP."


def test_placeholder_de_data_nao_e_lido_como_data():
    pt = _punto(dialogo=[
        {"tipo": "Hallazgo", "texto": "x"},
        {"tipo": "Respuesta UTE (dd/mm/aaaa)", "texto": "y"},
    ])
    assert anejo.punto_to_anejo(pt)["fecha_cierre"] == anejo.A_PREENCHER


# --- CSV --------------------------------------------------------------------

def test_csv_leva_o_id_na_primeira_coluna():
    with tempfile.TemporaryDirectory() as td:
        out = anejo.to_csv(anejo.build(_projeto()), Path(td) / "a.csv")
        with out.open(encoding="utf-8-sig", newline="") as f:
            linhas = list(csv.DictReader(f))
    assert list(linhas[0])[0] == "id"
    assert [ln["id"] for ln in linhas] == ["H-001", "H-005", "H-009"]
