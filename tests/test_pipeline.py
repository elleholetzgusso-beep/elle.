"""A janela gráfica constrói as mesmas linhas de comando que se escreveriam à mão.

Estes testes não abrem janela nenhuma: o que se verifica é o `pipeline`, que
decide o que correr e o que exigir. O desenho vive no `gui.py` e não é testado
aqui.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lpa_filler import cli, pipeline
from lpa_filler.pipeline import Config


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    return Config(
        trabalho=tmp_path,
        pes=tmp_path / "PES.docx",
        recibida=tmp_path / "recibida",
        base=tmp_path / "base.csv",
        template=tmp_path / "template.xlsm",
    )


def _argv_de(chave: str, cfg: Config) -> list[list[str]]:
    return pipeline.passo(chave).comandos(cfg)


# --------------------------------------------------------------- as entradas


def test_passo_diz_o_que_falta_em_vez_de_correr_incompleto():
    vazio = Config()
    falta = pipeline.passo("preparar").em_falta(vazio)
    assert "Relatório PES (.docx)" in falta
    assert "Pasta dos documentos recebidos" in falta


def test_sugerir_exige_o_projeto_ja_criado(cfg: Config):
    assert any("projeto.yaml" in m for m in pipeline.passo("sugerir").em_falta(cfg))
    cfg.projeto.write_text("puntos: []\n", encoding="utf-8")
    assert pipeline.passo("sugerir").em_falta(cfg) == []


def test_com_tudo_preenchido_nao_falta_nada(cfg: Config):
    cfg.projeto.write_text("puntos: []\n", encoding="utf-8")
    for chave in ("preparar", "analisar", "sugerir", "lpa", "anejo"):
        assert pipeline.passo(chave).em_falta(cfg) == [], chave


# ------------------------------------------------------ os comandos gerados


def test_preparar_encadeia_pes_documentos_e_projeto(cfg: Config):
    cmds = _argv_de("preparar", cfg)
    assert [c[0] for c in cmds] == ["from-docx", "scan", "merge"]
    assert str(cfg.projeto) in cmds[2]


def test_solicitante_so_entra_quando_preenchido(cfg: Config):
    assert "--solicitante" not in _argv_de("preparar", cfg)[2]
    cfg.solicitante = "ADIF"
    merge = _argv_de("preparar", cfg)[2]
    assert merge[merge.index("--solicitante") + 1] == "ADIF"


def test_excluir_obra_so_entra_quando_preenchido(cfg: Config):
    assert "--excluir-obra" not in _argv_de("analisar", cfg)[1]
    cfg.excluir_obra = "EXC2026-18042"
    radar = _argv_de("analisar", cfg)[1]
    assert radar[radar.index("--excluir-obra") + 1] == "EXC2026-18042"


def test_scope_vai_para_o_suggest_e_nao_para_o_radar(cfg: Config):
    cfg.scope = "Sant Vicenç de Calders, TRAMO 2"
    assert "--scope" not in _argv_de("analisar", cfg)[1]
    sugerir = _argv_de("sugerir", cfg)[0]
    assert sugerir[sugerir.index("--scope") + 1] == "Sant Vicenç de Calders, TRAMO 2"


def test_exigencia_das_sugestoes_chega_ao_comando(cfg: Config):
    cfg.min_score = 24
    cmd = _argv_de("sugerir", cfg)[0]
    assert cmd[cmd.index("--min-score") + 1] == "24"


def test_substituir_sugestoes_e_opcional(cfg: Config):
    assert "--replace" not in _argv_de("sugerir", cfg)[0]
    cfg.substituir_sugestoes = True
    assert "--replace" in _argv_de("sugerir", cfg)[0]


def test_a_caixa_da_aba_vazia_manda_no_skip_lpa(cfg: Config):
    cfg.skip_lpa = True
    assert "--skip-lpa" in _argv_de("lpa", cfg)[0]
    cfg.skip_lpa = False
    assert "--skip-lpa" not in _argv_de("lpa", cfg)[0]


def test_anejo_grava_os_ids_para_serem_estaveis(cfg: Config):
    # Um ID só serve para seguir o hallazgo entre revisões se ficar no projeto.
    assert "--asignar-ids" in _argv_de("anejo", cfg)[0]


# ----------------------------------------------- os comandos existem mesmo


def test_todos_os_comandos_gerados_sao_aceites_pelo_cli(cfg: Config):
    # Impede que a janela ofereça uma opção que o CLI não tem — foi o que
    # aconteceu com o --scope no radar.
    analisador = cli.build_parser()
    for passo in pipeline.PASSOS:
        for argv in passo.comandos(cfg):
            analisador.parse_args(argv)


# ------------------------------------------------------- proteger o trabalho


def test_conta_os_puntos_para_avisar_antes_de_apagar(cfg: Config):
    assert pipeline.projeto_tem_puntos(cfg) == 0
    cfg.projeto.write_text(
        yaml.safe_dump({"puntos": [{"id": "H-001"}, {"id": "H-002"}]}), encoding="utf-8"
    )
    assert pipeline.projeto_tem_puntos(cfg) == 2


def test_projeto_ilegivel_nao_rebenta_a_janela(cfg: Config):
    cfg.projeto.write_text("isto: [nao é: yaml", encoding="utf-8")
    assert pipeline.projeto_tem_puntos(cfg) == 0


def test_saidas_ficam_todas_na_pasta_de_trabalho(cfg: Config):
    for saida in (cfg.meta, cfg.documentos, cfg.projeto, cfg.leitura,
                  cfg.radar, cfg.lpa, cfg.anejo):
        assert saida.parent == cfg.trabalho


# ---------------------------------------------------------------- empacotamento

EMPACOTAR = Path(__file__).resolve().parent.parent / "empacotar"


def test_o_executavel_arranca_pelo_lancador_e_nao_pelo_gui():
    # O PyInstaller corre o script de entrada como '__main__'. Apontá-lo a
    # lpa_filler/gui.py faz rebentar os imports relativos ('from . import
    # pipeline') com ImportError logo no arranque — e só se vê depois de
    # empacotar. O lançador importa o pacote pelo nome e evita isso.
    spec = (EMPACOTAR / "LPA.spec").read_text(encoding="utf-8")
    assert "arranque.py" in spec
    assert '"lpa_filler", "gui.py"' not in spec

    arranque = (EMPACOTAR / "arranque.py").read_text(encoding="utf-8")
    assert "from lpa_filler.gui import main" in arranque


def test_a_receita_nao_exige_logotipo_para_construir():
    # A marca chega depois do programa funcionar; até lá o build tem de correr.
    spec = (EMPACOTAR / "LPA.spec").read_text(encoding="utf-8")
    assert "_se_existir" in spec
