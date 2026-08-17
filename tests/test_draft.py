"""Testes do rascunho determinístico da réplica do avaliador (draft.py)."""
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import draft, model  # noqa: E402


def _docx(dest: Path, *paragrafos: str) -> None:
    corpo = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragrafos)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="x"><w:body>{corpo}</w:body></w:document>'
    with zipfile.ZipFile(dest, "w") as z:
        z.writestr("word/document.xml", xml)


def _projeto(estado="Abierto", resp="Corregido en el apartado 3.2.", exceltic_vazio=True):
    dialogo = [
        {"tipo": "Hallazgo", "texto": "Falta la gestión de la seguridad."},
        {"tipo": "Respuesta ADIF (13/07/2026)", "texto": resp},
        {"tipo": "Respuesta Exceltic (dd/mm/aaaa)", "texto": "" if exceltic_vazio else "ya escrito"},
    ]
    return {"puntos": [{"n": 1, "documento": "Anejo 27 Estudio Previo Seguridad",
                        "valoracion": "Crítico", "estado": estado, "dialogo": dialogo}]}


def test_draft_preenche_exceltic_com_evidencia_e_nao_fecha():
    with tempfile.TemporaryDirectory() as d:
        _docx(Path(d) / "Anejo 27 Estudio Previo Seguridad_v06.docx",
              "1 Introducción", "3.2 Gestión de la seguridad", "Se define el plan y las medidas.")
        proj = _projeto()
        r = draft.elaborar(proj, d)
    pt = proj["puntos"][0]
    assert r["rascunhos"] == 1
    assert pt["estado"] == "Abierto"                 # NÃO fechou
    assert pt["_rascunho"] is True
    exceltic = pt["dialogo"][2]
    assert exceltic["texto"].startswith(draft.MARCA)
    assert "3.2" in exceltic["texto"]
    # É factual, não um juízo de conformidade.
    assert "pendiente de verificación" in exceltic["texto"].lower()


def test_draft_sinaliza_apartado_inexistente():
    with tempfile.TemporaryDirectory() as d:
        _docx(Path(d) / "Anejo 27 Estudio Previo Seguridad_v06.docx", "1 Introducción")
        proj = _projeto(resp="Corregido en el apartado 9.9.")
        draft.elaborar(proj, d)
    texto = proj["puntos"][0]["dialogo"][2]["texto"]
    assert "9.9" in texto and "no se localiza" in texto.lower()


def test_draft_ignora_punto_sem_resposta_do_contratista():
    with tempfile.TemporaryDirectory() as d:
        _docx(Path(d) / "Anejo 27 Estudio Previo Seguridad_v06.docx", "3.2 Gestión")
        proj = _projeto(resp="")   # sem resposta do contratista
        r = draft.elaborar(proj, d)
    assert r["rascunhos"] == 0
    assert r["sem_resposta"] == 1
    assert not proj["puntos"][0].get("_rascunho")


def test_draft_ficheiro_em_falta():
    with tempfile.TemporaryDirectory() as d:
        _docx(Path(d) / "Outro Documento.docx", "algo")
        proj = _projeto()
        draft.elaborar(proj, d)
    assert "no se localiza el documento" in proj["puntos"][0]["dialogo"][2]["texto"].lower()


def test_lint_avisa_enquanto_houver_rascunho():
    proj = _projeto()
    proj["puntos"][0]["dialogo"][2]["texto"] = draft.MARCA + " evidencia..."
    proj["puntos"][0]["_rascunho"] = True
    avisos = model.lint(proj)
    assert any("BORRADOR" in a for a in avisos)


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
