"""Testes dos estados legados no harvest e do VLOOKUP dinâmico no filler."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import filler, harvest  # noqa: E402


def test_estado_pe03_canonicos_sem_legado():
    assert harvest._estado_pe03("Abierto") == ("Abierto", "")
    assert harvest._estado_pe03("cerrado") == ("Cerrado", "")
    assert harvest._estado_pe03(None) == (None, "")


def test_estado_pe03_legados_mapeados_com_rastreio():
    assert harvest._estado_pe03("Controlado") == ("Resuelto", "Controlado")
    assert harvest._estado_pe03("CONFORME") == ("Cerrado", "CONFORME")
    assert harvest._estado_pe03("Resuelto/Cerrado") == ("Cerrado", "Resuelto/Cerrado")


def test_estado_pe03_cancelado_passa_intacto_como_nao_normativo():
    # Sem equivalente no PE/03 — não inventar mapeamento (decisão pendente do RE).
    assert harvest._estado_pe03("Cancelado") == ("Cancelado", "Cancelado")


def test_punto_to_row_inclui_estado_legado():
    row = harvest._punto_to_row(
        {"n": 1, "estado": "Controlado", "valoracion": "Importante",
         "dialogo": [{"tipo": "Hallazgo", "texto": "t"}]},
        "EXC2025-16126 LPA",
    )
    assert row["estado"] == "Resuelto"
    assert row["estado_legado"] == "Controlado"
    assert "estado_legado" in harvest.FIELDS


def test_vlookup_dinamico_cobre_todas_as_linhas():
    f = filler.VLOOKUP_REF.format(r=2, last=312)
    assert "$G$312" in f and "148" not in f


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
