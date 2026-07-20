"""Testes da triagem de documentos não avaliativos (PE/01)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import filtro, scan, suggest  # noqa: E402


def test_classify_name_desviado():
    casos = [
        "Oferta de Definición de Servicios EXC2025-16126",
        "Acuse de recibo Envío 3",
        "Respuesta a comentarios del LPA v02",
        "Carta de la UTE al RE",
        "Nota de envío documentación",
    ]
    for nome in casos:
        cat, motivo = filtro.classify_name(nome)
        assert cat == "desviado", f"{nome} -> {cat}"
        assert motivo, "todo desvio tem motivo registado"


def test_classify_name_avaliar_documentos_tecnicos():
    casos = [
        "Anejo 27. Estudio Previo Seguridad",
        "Apéndice 1_REP",
        "Plan de Gestión de la Seguridad",
        "Memoria de cálculo de estructuras",
    ]
    for nome in casos:
        cat, _ = filtro.classify_name(nome)
        assert cat == "avaliar", f"{nome} -> {cat}"


def test_classify_name_incerto_sinal_fraco():
    cat, motivo = filtro.classify_name("Acta reunión seguimiento 05")
    assert cat == "incerto"
    assert "confirmar" in motivo.lower()


def test_actas_de_pruebas_sao_tecnicas():
    # Calibrado com a base real: actas de pruebas FAT/internas geram hallazgos.
    for nome in [
        "ACTA DE INICIO DE PRUEBAS EN FÁBRICA (FAT)",
        "Acta de Pruebas Internas de Vicálvaro",
        "Acta de pruebas internas y NC de la versión K1.0",
    ]:
        cat, _ = filtro.classify_name(nome)
        assert cat == "avaliar", nome


def test_nome_tecnico_nunca_desviado_pelo_conteudo():
    # Um Anejo nunca é desviado pelo conteúdo, mesmo que cite condições económicas.
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "Anejo 3. Presupuesto.docx"
        p.write_bytes(b"nao e um docx real")
        cat, _ = filtro.classify_file(p)
        assert cat == "avaliar"


def test_scan_marca_desviados_e_mantem_no_doc_evaluados():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        sub = root / "Envío 1 20251126" / "wt"
        sub.mkdir(parents=True)
        (sub / "Anejo 27. Estudio Previo Seguridad.pdf").write_text("x")
        (sub / "Oferta de Definición de Servicios.pdf").write_text("x")
        docs = scan.scan(root)
        by_name = {x["nombre"]: x for x in docs}
        assert len(docs) == 2, "o desviado continua catalogado (vai a Doc Evaluados)"
        oferta = by_name["Oferta de Definición de Servicios"]
        assert oferta["_triage"] == "desviado"
        assert "PE/01" in oferta["_triage_motivo"]
        assert "_triage" not in by_name["Anejo 27. Estudio Previo Seguridad"]
        # E com triage desligada, nada é marcado.
        docs2 = scan.scan(root, triage=False)
        assert all("_triage" not in x for x in docs2)


def test_suggest_ignora_documentos_desviados():
    base = [
        {"documento": "Oferta de Definición de Servicios", "punto": "1.1",
         "hallazgo": "Texto de oferta servicios definición", "valoracion": "Formal",
         "estado": "Cerrado", "fuente": "LPA-X"},
    ]
    projeto = {
        "documentos": [
            {"nombre": "Oferta de Definición de Servicios", "envios": [],
             "_triage": "desviado", "_triage_motivo": "PE/01"},
        ]
    }
    puntos = suggest.suggest_for_projeto(base, projeto, n_per_doc=5, min_score=0)
    assert puntos == [], "documento desviado não gera puntos de LPA"


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
