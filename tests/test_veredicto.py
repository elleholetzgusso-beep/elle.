"""Testes do veredito esperado do IES (PE/03)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import model  # noqa: E402


def test_critico_abierto_bloqueia():
    data = {"puntos": [
        {"n": 1, "valoracion": "Crítico", "estado": "Abierto"},
        {"n": 2, "valoracion": "Importante", "estado": "Abierto"},
    ]}
    v = model.veredicto(data)
    assert v["resultado"] == "NO_FAVORABLE"
    assert v["criticos_abiertos"] == [1]
    assert v["importantes_abiertos"] == [2]


def test_critico_cerrado_nao_bloqueia():
    data = {"puntos": [
        {"n": 1, "valoracion": "Crítico", "estado": "Cerrado"},
        {"n": 2, "valoracion": "Importante", "estado": "Resuelto"},
    ]}
    v = model.veredicto(data)
    assert v["resultado"] == "FAVORABLE"
    assert v["criticos_abiertos"] == []
    assert v["importantes_abiertos"] == []


def test_estado_em_falta_conta_como_abierto():
    data = {"puntos": [{"n": 7, "valoracion": "Crítico"}]}
    assert model.veredicto(data)["resultado"] == "NO_FAVORABLE"


def test_importantes_sem_limiar_arbitrario():
    # 12 importantes abertos: contagem em bruto, veredito continua FAVORABLE.
    data = {"puntos": [
        {"n": i, "valoracion": "Importante", "estado": "Abierto"} for i in range(1, 13)
    ]}
    v = model.veredicto(data)
    assert v["resultado"] == "FAVORABLE"
    assert len(v["importantes_abiertos"]) == 12


def test_veredicto_texto():
    v = model.veredicto({"puntos": [{"n": 3, "valoracion": "Crítico", "estado": "Abierto"}]})
    t = model.veredicto_texto(v)
    assert "NO_FAVORABLE" in t and "PE/03" in t and "3" in t


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
