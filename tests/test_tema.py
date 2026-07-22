"""Testes da classificação temática RAMS (tema.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import harvest, tema  # noqa: E402


def test_hazard_log():
    t = tema.classify("En el REP el peligro ID2 no tiene medida mitigadora asociada")
    assert "Hazard Log / REP" in t


def test_safety_case_e_interfaces():
    t = tema.classify("En la Definición del Sistema faltan las interfaces físicas y funcionales")
    assert "Safety Case" in t
    assert "Interfaces" in t


def test_vv_e_software():
    t = tema.classify("El plan de verificación y validación del software no cubre el SIL requerido")
    assert "V&V" in t
    assert "Software / SIL" in t


def test_srac():
    assert "SRAC" in tema.classify("Las condiciones de aplicación (SRAC) deben exportarse al mantenedor")


def test_analisis_ram():
    assert "Análisis RAM" in tema.classify("Falta el cálculo de disponibilidad y el FMEA del subsistema")


def test_sem_tema_nao_forca_etiqueta():
    # Achado genérico (assinatura/errata) não tem área RAMS.
    assert tema.classify("Se solicita el envío de la documentación debidamente firmada") == []
    assert tema.as_field("") == ""


def test_ordem_de_prioridade():
    # Vários temas saem na ordem definida em TEMAS (Hazard Log antes de V&V).
    t = tema.classify("Validación del registro de peligros")
    assert t.index("Hazard Log / REP") < t.index("V&V")


def test_harvest_inclui_coluna_tema():
    assert "tema" in harvest.FIELDS
    row = harvest._punto_to_row(
        {"n": 1, "valoracion": "Crítico", "estado": "Abierto",
         "documento": "REP", "dialogo": [{"tipo": "Hallazgo", "texto": "peligro sin mitigación"}]},
        "LPA-X",
    )
    assert "Hazard Log / REP" in row["tema"]


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
