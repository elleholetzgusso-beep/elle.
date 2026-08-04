"""Testes do fluxo de revisão: update preserva puntos e mescla documentos."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import updater  # noqa: E402


def _projeto_com_puntos():
    return {
        "portada": {"titulo": "PROYECTO X"},
        "versiones": [{"rev": 1, "fecha": "2026-01-01", "descripcion": "primera"}],
        "documentos": [
            {"nombre": "Anejo 27", "firmado": "NA", "estado": "auto",
             "envios": [{"referencia": "Anejo 27_v05", "version": 5, "envio": 1}]},
        ],
        "puntos": [
            {"n": 1, "valoracion": "Crítico", "estado": "Abierto",
             "dialogo": [{"tipo": "Hallazgo", "texto": "algo"}]},
        ],
    }


def test_update_preserva_puntos_e_versiones():
    proj = _projeto_com_puntos()
    novos = [{"nombre": "Documento Novo", "envios": [{"referencia": "Doc Novo_v01", "version": 1}]}]
    updater.merge_documentos(proj, novos)
    assert len(proj["puntos"]) == 1               # puntos intactos
    assert len(proj["versiones"]) == 1            # versiones intactas
    assert proj["portada"]["titulo"] == "PROYECTO X"


def test_update_acrescenta_documento_novo():
    proj = _projeto_com_puntos()
    novos = [{"nombre": "Documento Novo", "envios": [{"referencia": "Doc Novo_v01", "version": 1}]}]
    r = updater.merge_documentos(proj, novos)
    assert r["novos_documentos"] == 1
    assert len(proj["documentos"]) == 2
    assert any(d["nombre"] == "Documento Novo" for d in proj["documentos"])


def test_update_anexa_envio_novo_a_documento_existente():
    proj = _projeto_com_puntos()
    # Mesmo documento (Anejo 27), agora com uma versão nova (v06).
    novos = [{"nombre": "Anejo 27", "envios": [{"referencia": "Anejo 27_v06", "version": 6, "envio": 2}]}]
    r = updater.merge_documentos(proj, novos)
    assert r["novos_documentos"] == 0
    assert r["novos_envios"] == 1
    doc = proj["documentos"][0]
    assert len(doc["envios"]) == 2
    assert {e["version"] for e in doc["envios"]} == {5, 6}


def test_update_nao_duplica_envio_ja_existente():
    proj = _projeto_com_puntos()
    # Mesmo envío que já está lá (mesma referência) — não deve duplicar.
    novos = [{"nombre": "Anejo 27", "envios": [{"referencia": "Anejo 27_v05", "version": 5, "envio": 1}]}]
    r = updater.merge_documentos(proj, novos)
    assert r["novos_envios"] == 0
    assert len(proj["documentos"][0]["envios"]) == 1


def test_update_match_por_nome_normalizado():
    proj = _projeto_com_puntos()
    # Nome com acentos/maiúsculas/espaços diferentes casa com o existente.
    novos = [{"nombre": "  anejo  27 ", "envios": [{"referencia": "outro_v07", "version": 7}]}]
    r = updater.merge_documentos(proj, novos)
    assert r["novos_documentos"] == 0
    assert r["novos_envios"] == 1


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
