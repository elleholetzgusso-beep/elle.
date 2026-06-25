"""Testes leves do lpa_filler (não exigem o template real).

Corre com:  python -m pytest tests/  (ou)  python tests/test_lpa_filler.py
"""
import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import model, scan  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "examples" / "template_exemplo.xlsm"


def test_resumen_counts():
    data = {
        "puntos": [
            {"valoracion": "Crítico", "estado": "Cerrado"},
            {"valoracion": "Crítico", "estado": "Abierto"},
            {"valoracion": "Formal", "estado": "Cerrado"},
        ]
    }
    c = model.resumen_counts(data)
    assert c["Crítico"]["total"] == 2
    assert c["Crítico"]["Abierto"] == 1
    assert c["Formal"]["total"] == 1
    assert c["Informativo"]["total"] == 0


def test_model_validation_rejects_bad_valoracion():
    try:
        model._validate({"puntos": [{"n": 1, "valoracion": "Urgente"}]})
    except ValueError:
        return
    raise AssertionError("deveria rejeitar valoración inválida")


def test_scan_groups_by_document_and_parses_envio():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for env, name in [
            ("Envío 1 20251126", "Anejo 27. Estudio Previo Seguridad"),
            ("Envío 2 20260216", "Anejo 27. Estudio Previo Seguridad"),
            ("Envío 1 20251126", "Apéndice 1_REP"),
        ]:
            sub = root / env / "wt"
            sub.mkdir(parents=True, exist_ok=True)
            (sub / f"{name}.pdf").write_text("x")
        docs = scan.scan(root)
        by_name = {x["nombre"]: x for x in docs}
        assert "Anejo 27. Estudio Previo Seguridad" in by_name
        anejo = by_name["Anejo 27. Estudio Previo Seguridad"]
        assert len(anejo["envios"]) == 2
        envios = sorted(e["envio"] for e in anejo["envios"])
        assert envios == [1, 2]
        e1 = next(e for e in anejo["envios"] if e["envio"] == 1)
        assert e1["fecha_envio"] == dt.date(2025, 11, 26)


def test_fill_roundtrip_if_template_present():
    if not TEMPLATE.exists():
        print("SKIP: template não presente (examples/template_exemplo.xlsm)")
        return
    import zipfile

    from lpa_filler import extract, filler

    data = {
        "portada": {"titulo": "T", "referencia": "REF"},
        "versiones": [{"rev": 1, "fecha": dt.date(2026, 1, 1), "descripcion": "v1"}],
        "documentos": [
            {
                "nombre": "Doc A",
                "firmado": "Si",
                "estado": "Cerrado",
                "envios": [{"referencia": "Doc A", "version": 1, "envio": 1}],
            }
        ],
        "puntos": [
            {
                "n": 1,
                "eval": "SM",
                "documento": "Doc A",
                "ref_documento": "auto",
                "valoracion": "Crítico",
                "estado": "Cerrado",
                "dialogo": [
                    {"tipo": "Hallazgo", "texto": "achado"},
                    {"tipo": "Respuesta", "texto": "resp"},
                ],
            }
        ],
    }
    model._validate(data)
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out.xlsm"
        filler.fill(TEMPLATE, data, out)
        assert out.exists()
        names = zipfile.ZipFile(out).namelist()
        assert any("vbaProject" in n for n in names), "macros preservadas"
        assert any("pivot" in n.lower() for n in names), "pivot preservada"
        back = extract.extract(out)
        assert back["puntos"][0]["n"] == 1
        assert back["puntos"][0]["valoracion"] == "Crítico"
        assert len(back["puntos"][0]["dialogo"]) == 2


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
