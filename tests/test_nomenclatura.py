"""Testes da validação de nomenclatura Exceltic (PE/05)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import nomenclatura  # noqa: E402


def test_filenames_validos():
    for s in [
        "EXC2025-00001-001-LPA-01",
        "EXC2024-03868-001-PES-01",
        "EXC2025-16126-1-001-PES-02",
        "EXC2026-16883-12-003-IES-01",
    ]:
        assert nomenclatura.check_filename(s) is None, s


def test_filenames_invalidos_geram_aviso():
    for s in [
        "EXC2025-00001-001-LPA-1",      # versão com 1 dígito
        "EXC2025-00001-LPA-01",          # falta nº do documento
        "EXC25-00001-001-LPA-01",        # ano com 2 dígitos
        "EXC2025-00001-001-lpa-01",      # tipo em minúsculas
    ]:
        motivo = nomenclatura.check_filename(s)
        assert motivo and "PE/05" in motivo, s


def test_terceiros_nao_geram_aviso():
    assert nomenclatura.check_filename("Anejo 27. Estudio Previo Seguridad_v06") is None
    assert nomenclatura.check_referencia("UTE-DOC-0001") is None


def test_referencias_validas_e_invalidas():
    assert nomenclatura.check_referencia("EXC2025-16126-1/002/LPA/05") is None
    assert nomenclatura.check_referencia("EXC2025-16126/002/LPA/05") is None
    assert nomenclatura.check_referencia("EXC2025-16126-1/002/LPA/5") is not None
    assert nomenclatura.check_referencia("EXC2025-16126-1-002-LPA-05") is not None  # separador errado


def test_avisos_documentos_deduplicados():
    docs = [
        {"nombre": "A", "envios": [
            {"referencia": "EXC2025-1-001-LPA-01"},   # nº de projeto curto demais
            {"referencia": "EXC2025-1-001-LPA-01"},   # repetido -> 1 aviso só
            {"referencia": "Anejo 3_v02"},            # terceiro -> sem aviso
        ]},
    ]
    avisos = nomenclatura.avisos_documentos(docs)
    assert len(avisos) == 1


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
