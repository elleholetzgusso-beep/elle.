"""Testes da verificação do ciclo de resposta (verify.py)."""
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import verify  # noqa: E402


def _docx(dest: Path, *paragrafos: str) -> None:
    corpo = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragrafos)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="x"><w:body>{corpo}</w:body></w:document>'
    with zipfile.ZipFile(dest, "w") as z:
        z.writestr("word/document.xml", xml)


def _projeto(estado="Abierto", respuesta="Corregido en el apartado 3.2."):
    return {
        "puntos": [
            {
                "n": 1,
                "documento": "Anejo 27 Estudio Previo Seguridad",
                "valoracion": "Crítico",
                "estado": estado,
                "dialogo": [
                    {"tipo": "Hallazgo", "texto": "Falta la gestión de la seguridad."},
                    {"tipo": "Respuesta UTE (02/02/2026)", "texto": respuesta},
                ],
            }
        ]
    }


def test_verify_encontra_apartado_citado():
    with tempfile.TemporaryDirectory() as d:
        _docx(
            Path(d) / "Anejo 27 Estudio Previo Seguridad_v06.docx",
            "1 Introducción",
            "3.2 Gestión de la seguridad",
            "Se define el plan de seguridad y las medidas mitigadoras.",
        )
        regs = verify.verificar(_projeto(), d)
    assert len(regs) == 1
    r = regs[0]
    assert r["ficheiro"].endswith("_v06.docx")
    assert r["refs"] == ["3.2"]
    assert r["achados"][0]["trecho"] is not None
    assert "Gestión de la seguridad" in r["achados"][0]["trecho"]


def test_verify_sinaliza_apartado_inexistente():
    with tempfile.TemporaryDirectory() as d:
        _docx(Path(d) / "Anejo 27 Estudio Previo Seguridad_v06.docx", "1 Introducción", "2 Alcance")
        regs = verify.verificar(_projeto(respuesta="Corregido en el apartado 9.9."), d)
    r = regs[0]
    assert r["achados"][0]["trecho"] is None
    assert any("9.9" in n for n in r["notas"])


def test_verify_ficheiro_em_falta():
    with tempfile.TemporaryDirectory() as d:
        _docx(Path(d) / "Otro Documento Distinto.docx", "1 Algo")
        regs = verify.verificar(_projeto(), d)
    assert regs[0]["ficheiro"] is None
    assert any("não encontrei o ficheiro" in n for n in regs[0]["notas"])


def test_pasta_inexistente_levanta_erro_claro():
    try:
        verify.ficheiros_legiveis("/caminho/que/nao/existe/xyz")
    except NotADirectoryError:
        pass
    else:
        raise AssertionError("devia ter levantado NotADirectoryError")


def test_verify_ignora_cerrado():
    with tempfile.TemporaryDirectory() as d:
        _docx(Path(d) / "Anejo 27 Estudio Previo Seguridad_v06.docx", "3.2 Gestión")
        regs = verify.verificar(_projeto(estado="Cerrado"), d)
    assert regs == []


def test_verify_diff_entre_versoes():
    with tempfile.TemporaryDirectory() as d:
        _docx(Path(d) / "Anejo 27 Estudio Previo Seguridad_v05.docx",
              "3.2 Gestión de la seguridad", "Texto antiguo sin mitigación.")
        _docx(Path(d) / "Anejo 27 Estudio Previo Seguridad_v06.docx",
              "3.2 Gestión de la seguridad", "Texto NUEVO con la mitigación añadida.")
        regs = verify.verificar(_projeto(), d)
    r = regs[0]
    assert r["ficheiro"].endswith("_v06.docx")  # usa a versão mais nova
    assert any("NUEVO" in m for m in r["mudancas"])


def test_relatorio_nao_rebenta():
    with tempfile.TemporaryDirectory() as d:
        _docx(Path(d) / "Anejo 27 Estudio Previo Seguridad_v06.docx", "3.2 Gestión de la seguridad", "X")
        regs = verify.verificar(_projeto(), d)
        txt = verify.relatorio(regs)
    assert "Punto 1" in txt
    assert "Verificação" in txt


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
