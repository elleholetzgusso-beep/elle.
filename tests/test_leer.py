"""Testes da leitura estrutural do 1º LPA (leer.py)."""
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import leer  # noqa: E402


def _docx(dest: Path, *paragrafos: str) -> None:
    corpo = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragrafos)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="x"><w:body>{corpo}</w:body></w:document>'
    with zipfile.ZipFile(dest, "w") as z:
        z.writestr("word/document.xml", xml)


def test_safety_case_deteta_partes_presentes_e_ausentes():
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "Safety Case del sistema_v01.docx"
        _docx(
            dest,
            "Definición del Sistema: alcance y límites.",
            "Gestión de la Seguridad: plan y organización.",
            "Seguridad Técnica: análisis. Referencia a EN 50129 y EN 50126.",
            "Conclusión: el sistema es seguro.",
        )
        reg = leer.revisar_ficheiro(dest)
    presentes = {rotulo for rotulo, ok in reg["checklist"] if ok}
    ausentes = {rotulo for rotulo, ok in reg["checklist"] if not ok}
    assert "1. Definición del Sistema" in presentes
    assert "3. Gestión de la Seguridad" in presentes
    assert "6. Conclusión" in presentes
    # Gestión de la Calidad não foi mencionada -> assinalada como ausente.
    assert "2. Gestión de la Calidad" in ausentes
    assert "EN 50129" in reg["normas"] and "EN 50126" in reg["normas"]


def test_rep_checklist():
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "Apendice REP registro de peligros_v03.docx"
        _docx(dest, "Peligro P1. Medida mitigadora asociada. Estado: Abierto.")
        reg = leer.revisar_ficheiro(dest)
    rotulos_ok = {r for r, ok in reg["checklist"] if ok}
    assert "Identificação de perigos" in rotulos_ok
    assert "Medidas mitigadoras" in rotulos_ok
    assert "Estado do perigo" in rotulos_ok


def test_documento_sem_checklist_ainda_le():
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "Presupuesto general.docx"
        _docx(dest, "Capítulo 1. Movimiento de tierras. Importe total.")
        reg = leer.revisar_ficheiro(dest)
    assert reg["caracteres"] > 0
    assert reg["checklist"] == []
    assert any("sem checklist" in n for n in reg["notas"])


def test_ficheiro_ilegivel_nao_rebenta():
    reg = leer.revisar_ficheiro("nao_existe.pdf")
    assert reg["caracteres"] == 0
    assert reg["notas"]


def test_relatorio_pasta():
    with tempfile.TemporaryDirectory() as d:
        _docx(Path(d) / "Safety Case_v01.docx", "Definición del Sistema.", "Conclusión.")
        _docx(Path(d) / "Presupuesto.docx", "Importe.")
        regs = leer.revisar_pasta(d)
        txt = leer.relatorio(regs)
    assert len(regs) == 2
    assert "Leitura estrutural" in txt


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
