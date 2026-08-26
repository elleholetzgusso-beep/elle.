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


def test_novidade_sai_azul_no_xlsm_de_verdade():
    """Ponta a ponta: uma resposta nova (num punto que já existia) e um punto
    inteiramente novo, contra o template real — não a mock nenhum de openpyxl."""
    if not TEMPLATE.exists():
        print("SKIP: template não presente (examples/template_exemplo.xlsm)")
        return
    from lpa_filler import filler

    anterior = {
        "portada": {"referencia": "REF"},
        "versiones": [{"rev": 1, "fecha": dt.date(2026, 1, 1), "descripcion": "v1"}],
        "documentos": [{"nombre": "Doc A", "envios": [{"referencia": "Doc A", "version": 1, "envio": 1}]}],
        "puntos": [{
            "id": "H-001", "n": 1, "eval": "SM", "documento": "Doc A", "ref_documento": "auto",
            "valoracion": "Crítico", "estado": "Abierto",
            "dialogo": [{"tipo": "Hallazgo", "texto": "achado original"}],
        }],
    }
    atual = {
        "portada": anterior["portada"],
        "versiones": anterior["versiones"],
        "documentos": anterior["documentos"],
        "puntos": [
            dict(anterior["puntos"][0], estado="Resuelto", dialogo=[
                {"tipo": "Hallazgo", "texto": "achado original"},
                {"tipo": "Respuesta ADIF", "texto": "corregido"},   # nova
            ]),
            {
                "id": "H-002", "n": 2, "eval": "SM", "documento": "Doc A", "ref_documento": "auto",
                "valoracion": "Formal", "estado": "Abierto",
                "dialogo": [{"tipo": "Hallazgo", "texto": "achado novo"}],   # punto inteiro novo
            },
        ],
    }
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out.xlsm"
        filler.fill(TEMPLATE, atual, out, anterior=anterior)

        import openpyxl
        ws = openpyxl.load_workbook(out)["LPA"]

        def cor(ref: str) -> str | None:
            c = ws[ref].font.color
            return c.rgb if c and getattr(c, "type", None) == "rgb" else None

        assert cor("I2") is None                     # hallazgo original: sem cor
        assert cor("I3") == filler.COR_NOVO           # resposta nova
        assert cor("A2") is None                      # metadados do punto velho: sem cor
        assert cor("I4") == filler.COR_NOVO            # punto H-002 inteiro é novo
        assert cor("A4") == filler.COR_NOVO


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


def test_scan_apontado_a_uma_pasta_de_envio(tmp_path):
    """Apontar o scan diretamente a 'Envío 44 ...' tem de encontrar os ficheiros.

    O scan tratava as subpastas como envíos, por isso uma pasta de envío (cujos
    ficheiros estão à vista) dava 0 documentos — enquanto o leer e o radar, que
    varrem recursivamente, encontravam os mesmos ficheiros. O LPA saía com 0
    puntos sem um único erro na consola.
    """
    envio = tmp_path / "Envío 44 20260727"
    envio.mkdir()
    (envio / "PRF_CS-2026-046-A0.pdf").write_bytes(b"%PDF-1.4")
    (envio / "Informe de pruebas_v10.docx").write_bytes(b"PK")

    docs = scan.scan(envio)
    assert len(docs) == 2
    # O número e a data do envío saem do nome da própria pasta.
    envios = [e for d in docs for e in d["envios"]]
    assert all(e["envio"] == 44 for e in envios)


def test_scan_pasta_sem_subpastas_mas_com_documentos(tmp_path):
    # Sem 'Envío' no nome e sem subpastas: continua a ser um envío só.
    solta = tmp_path / "Documentos recibidos"
    solta.mkdir()
    (solta / "Anejo 27.pdf").write_bytes(b"%PDF-1.4")
    assert len(scan.scan(solta)) == 1


def test_scan_estrutura_normal_nao_muda(tmp_path):
    # A estrutura de sempre continua a agrupar por envío, sem contar duas vezes.
    raiz = tmp_path / "1_Doc Recibida"
    for n, nome in ((1, "Envío 1 20251126"), (2, "Envío 2 20260216")):
        d = raiz / nome
        d.mkdir(parents=True)
        (d / "Anejo 27.pdf").write_bytes(b"%PDF-1.4")

    docs = scan.scan(raiz)
    assert len(docs) == 1                      # mesmo nome nos dois envíos
    assert [e["envio"] for e in docs[0]["envios"]] == [1, 2]


def test_fecha_sai_do_nome_do_documento_e_nao_do_ficheiro_em_disco(tmp_path):
    """A 'Fecha' de Doc Evaluados é a data do documento, não a do envío nem a
    do ficheiro em disco — essa passa a ser a da cópia assim que se descarrega.
    """
    from lpa_filler.scan import _data_do_nome
    import datetime as _dt

    assert _data_do_nome("20260202_Esq_Elec_SVC") == _dt.date(2026, 2, 2)
    assert _data_do_nome("250810_ER DMMDH-G-60") == _dt.date(2025, 8, 10)
    assert _data_do_nome("Esquema eléctrico SVC 03_02_2026") == _dt.date(2026, 2, 3)
    assert _data_do_nome("CZE-000105_001.V1.0_16062025") == _dt.date(2025, 6, 16)
    assert _data_do_nome("SEÑALES LTV_Hito 4_08SEP25") == _dt.date(2025, 9, 8)
    assert _data_do_nome("Telefonema PES 080925") == _dt.date(2025, 9, 8)


def test_codigos_sem_data_ficam_por_preencher():
    """Uma data errada num registo de conformidade é pior que uma célula vazia."""
    from lpa_filler.scan import _data_do_nome

    # 000105 é um sequencial, não o ano 2000; 213461 daria mês 34.
    assert _data_do_nome("CZE-000105 - ESSADF18630D820_001") is None
    assert _data_do_nome("213461-CV-INECO-FT-V04-A0_SUJEC") is None
    assert _data_do_nome("GEN-83PO00107-S0045_v10.0") is None
    assert _data_do_nome("24-30-V-F09A-REP-VLC-SUD-V1.0") is None


def test_scan_separa_a_data_do_documento_da_data_do_envio(tmp_path):
    envio = tmp_path / "Envío 44 20260727"
    envio.mkdir()
    (envio / "20260202_Esq_Elec_SVC.pdf").write_bytes(b"%PDF-1.4")

    env = scan.scan(envio, autor="FGV")[0]["envios"][0]
    assert env["fecha"] == dt.date(2026, 2, 2)        # do nome do documento
    assert env["fecha_envio"] == dt.date(2026, 7, 27)  # da pasta do envío
    assert env["autor"] == "FGV"


def test_data_interna_do_docx_quando_o_nome_nao_a_traz(tmp_path):
    """Segunda fonte da 'Fecha': o que o .docx traz dentro (docProps/core.xml).

    Ao contrário da data do ficheiro em disco, esta viaja com o documento — não
    muda ao copiar nem ao descarregar.
    """
    import zipfile

    core = ('<?xml version="1.0"?><cp:coreProperties xmlns:cp="x" xmlns:dcterms="y">'
            "<dcterms:created>2026-05-14T08:30:00Z</dcterms:created></cp:coreProperties>")
    envio = tmp_path / "Envío 44 20260727"
    envio.mkdir()
    for nome in ("Informe sin fecha en el nombre.docx", "20260202_Con fecha.docx"):
        with zipfile.ZipFile(envio / nome, "w") as z:
            z.writestr("docProps/core.xml", core)
            z.writestr("word/document.xml", "<w:document/>")

    por_nome = {d["nombre"]: d["envios"][0] for d in scan.scan(envio)}
    assert por_nome["Informe sin fecha en el nombre"]["fecha"] == dt.date(2026, 5, 14)
    # O nome ganha aos metadados: é lá que quem emite põe a data da versão.
    assert por_nome["20260202_Con fecha"]["fecha"] == dt.date(2026, 2, 2)
