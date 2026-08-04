"""Testes leves do lpa_filler (não exigem o template real).

Corre com:  python -m pytest tests/  (ou)  python tests/test_lpa_filler.py
"""
import datetime as dt
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import model, scan, scope, suggest  # noqa: E402

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


def test_scope_classify_in_out_unknown():
    anchors = scope.parse_anchors("Torre Pacheco, L352, Balsicas")
    # Nomeia a obra atual -> dentro.
    assert scope.classify("Revisar el paso a nivel en Torre Pacheco", anchors) == "in"
    assert scope.classify("Velocidades de la línea L352", anchors) == "in"
    # Nomeia outra obra e não a atual -> fora (contaminação).
    assert scope.classify("Bloqueo entre Lleida Pirineus y Balaguer", anchors) == "out"
    assert scope.classify("Enclavamiento de Sueca y Cullera (ENYSE)", anchors) == "out"
    # Genérico, sem topónimos -> indeterminado (não penalizar).
    assert scope.classify("La tabla 3 no indica el valor de cálculo", anchors) == "unknown"
    # Sem âncoras -> nunca marca fora de escopo.
    assert scope.classify("Bloqueo entre Lleida y Balaguer", []) == "unknown"


def test_scope_find_markers_codes_and_places():
    m = scope.find_markers("Estudio de la línea L352 en Balsicas y también Sueca")
    assert "balsicas" in m and "sueca" in m
    assert any("352" in x for x in m)  # código de linha detetado


def test_suggest_marks_out_of_scope():
    base = [
        {"documento": "[135.0] Perfilado banqueta", "punto": "1.1",
         "hallazgo": "Perfilado de banqueta en Torre Pacheco correcto", "valoracion": "Importante",
         "estado": "Cerrado", "fuente": "LPA-A"},
        {"documento": "[135.0] Perfilado banqueta", "punto": "1.2",
         "hallazgo": "Bloqueo entre enclavamientos de Lleida Pirineus y Balaguer", "valoracion": "Importante",
         "estado": "Cerrado", "fuente": "LPA-B"},
    ]
    projeto = {"documentos": [{"nombre": "[135.0] Perfilado banqueta", "envios": []}]}
    anchors = scope.parse_anchors("Torre Pacheco, L352, Balsicas")
    puntos = suggest.suggest_for_projeto(base, projeto, n_per_doc=5, min_score=0, anchors=anchors)
    by_txt = {p["dialogo"][0]["texto"]: p for p in puntos}
    dentro = by_txt["Perfilado de banqueta en Torre Pacheco correcto"]
    fora = by_txt["Bloqueo entre enclavamientos de Lleida Pirineus y Balaguer"]
    assert not dentro.get("_fora_escopo")
    assert fora.get("_fora_escopo") is True
    assert "lleida" in (fora.get("_marcadores") or "")
    # O fora de escopo deve vir ordenado DEPOIS do dentro (afundado).
    assert puntos.index(dentro) < puntos.index(fora)


def test_skip_texts_nao_gasta_as_vagas_dos_n_melhores():
    """Regressão (obra EXC2026-16883): numa revisão, o `suggest` devolvia 0 de 862.

    Os puntos já no projeto eram os melhores matches, mas só eram excluídos DEPOIS
    do corte aos `n_per_doc` melhores — gastavam as vagas e não sobrava nada para
    propor. Numa revisão, que é quando o comando serve, dava sempre zero.
    """
    base = [
        {"documento": "Plan de Seguridad", "punto": f"1.{i}", "estado": "Cerrado",
         "hallazgo": f"Hallazgo {i} del plan de seguridad.", "valoracion": "Importante",
         "fuente": "LPA-A"}
        for i in range(1, 11)
    ]
    projeto = {"documentos": [{"nombre": "Plan de Seguridad", "envios": []}]}

    primeira = suggest.suggest_for_projeto(base, projeto, n_per_doc=3, min_score=1)
    assert len(primeira) == 3

    # Segunda passagem: as 3 já estão no projeto. Sobram 7 na base, igualmente boas.
    skip = {suggest.chave_texto(p["dialogo"][0]["texto"]) for p in primeira}
    segunda = suggest.suggest_for_projeto(base, projeto, n_per_doc=3, min_score=1, skip_texts=skip)
    assert len(segunda) == 3, "as vagas foram gastas pelos puntos já existentes"
    assert not {suggest.chave_texto(p["dialogo"][0]["texto"]) for p in segunda} & skip


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
