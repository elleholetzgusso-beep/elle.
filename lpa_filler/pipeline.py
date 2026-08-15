"""Passos do fluxo LPA, para interfaces que não são a linha de comandos.

Constrói as linhas de comando de cada passo **sem as executar**, para que a
janela gráfica possa dizer o que falta antes de correr o que quer que seja —
e para que esta parte se possa testar sem abrir uma janela.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class Config:
    """As escolhas do utilizador. Os caminhos de saída derivam da pasta de trabalho."""

    trabalho: Path = Path(".")
    pes: Path | None = None
    recibida: Path | None = None
    base: Path | None = None
    template: Path | None = None
    solicitante: str = ""
    scope: str = ""
    excluir_obra: str = ""
    min_score: float = 12.0
    skip_lpa: bool = True
    substituir_sugestoes: bool = False

    @property
    def meta(self) -> Path:
        return self.trabalho / "meta.yaml"

    @property
    def documentos(self) -> Path:
        return self.trabalho / "documentos.yaml"

    @property
    def projeto(self) -> Path:
        return self.trabalho / "projeto.yaml"

    @property
    def leitura(self) -> Path:
        return self.trabalho / "leitura.txt"

    @property
    def radar(self) -> Path:
        return self.trabalho / "radar.txt"

    @property
    def lpa(self) -> Path:
        return self.trabalho / "LPA.xlsm"

    @property
    def anejo(self) -> Path:
        return self.trabalho / "anejo_a2.csv"


@dataclass
class Passo:
    chave: str
    titulo: str
    descricao: str
    _comandos: Callable[[Config], list[list[str]]]
    _exige: Callable[[Config], list[str]]

    def comandos(self, cfg: Config) -> list[list[str]]:
        return self._comandos(cfg)

    def em_falta(self, cfg: Config) -> list[str]:
        """O que falta preencher para este passo poder correr."""
        return self._exige(cfg)


def _s(p: Path | None) -> str:
    return str(p) if p else ""


# --------------------------------------------------------------------------- #
# 1. Preparar o projeto: PES + documentos recebidos -> projeto.yaml


def _cmd_preparar(cfg: Config) -> list[list[str]]:
    cmds = [
        ["from-docx", "-i", _s(cfg.pes), "-o", _s(cfg.meta)],
        ["scan", "-r", _s(cfg.recibida), "-o", _s(cfg.documentos)],
    ]
    merge = ["merge", "-m", _s(cfg.meta), "-d", _s(cfg.documentos), "-o", _s(cfg.projeto)]
    if cfg.solicitante:
        merge += ["--solicitante", cfg.solicitante]
    cmds.append(merge)
    return cmds


def _exige_preparar(cfg: Config) -> list[str]:
    falta = []
    if not cfg.pes:
        falta.append("Relatório PES (.docx)")
    if not cfg.recibida:
        falta.append("Pasta dos documentos recebidos")
    return falta


# --------------------------------------------------------------------------- #
# 2. Analisar: o que falta a cada documento + onde procurar erros


def _cmd_analisar(cfg: Config) -> list[list[str]]:
    radar = ["radar", "-r", _s(cfg.recibida), "-b", _s(cfg.base), "-o", _s(cfg.radar)]
    if cfg.excluir_obra:
        radar += ["--excluir-obra", cfg.excluir_obra]
    return [
        ["leer", "-r", _s(cfg.recibida), "-o", _s(cfg.leitura)],
        radar,
    ]


def _exige_analisar(cfg: Config) -> list[str]:
    falta = []
    if not cfg.recibida:
        falta.append("Pasta dos documentos recebidos")
    if not cfg.base:
        falta.append("Base de hallazgos (.csv)")
    return falta


# --------------------------------------------------------------------------- #
# 3. Sugerir hallazgos do histórico


def _cmd_sugerir(cfg: Config) -> list[list[str]]:
    cmd = [
        "suggest",
        "-b", _s(cfg.base),
        "-p", _s(cfg.projeto),
        "-o", _s(cfg.projeto),
        "--min-score", str(cfg.min_score),
    ]
    if cfg.scope:
        cmd += ["--scope", cfg.scope]
    if cfg.substituir_sugestoes:
        cmd.append("--replace")
    return [cmd]


def _exige_sugerir(cfg: Config) -> list[str]:
    falta = []
    if not cfg.base:
        falta.append("Base de hallazgos (.csv)")
    if not cfg.projeto.exists():
        falta.append("projeto.yaml — corre primeiro o passo 1")
    return falta


# --------------------------------------------------------------------------- #
# 4. Gerar o LPA


def _cmd_gerar_lpa(cfg: Config) -> list[list[str]]:
    cmd = ["fill", "-t", _s(cfg.template), "-d", _s(cfg.projeto), "-o", _s(cfg.lpa)]
    if cfg.skip_lpa:
        cmd.append("--skip-lpa")
    return [cmd]


def _exige_gerar_lpa(cfg: Config) -> list[str]:
    falta = []
    if not cfg.template:
        falta.append("Template LPA (.xlsm)")
    if not cfg.projeto.exists():
        falta.append("projeto.yaml — corre primeiro o passo 1")
    return falta


# --------------------------------------------------------------------------- #
# 5. Anejo A.2


def _cmd_anejo(cfg: Config) -> list[list[str]]:
    return [["anejo", "-p", _s(cfg.projeto), "-o", _s(cfg.anejo), "--asignar-ids"]]


def _exige_anejo(cfg: Config) -> list[str]:
    return [] if cfg.projeto.exists() else ["projeto.yaml — corre primeiro o passo 1"]


# --------------------------------------------------------------------------- #

PASSOS: list[Passo] = [
    Passo(
        "preparar",
        "1 · Preparar o projeto",
        "Lê o PES, cataloga os documentos recebidos e monta o projeto.yaml.",
        _cmd_preparar,
        _exige_preparar,
    ),
    Passo(
        "analisar",
        "2 · Analisar os documentos",
        "Checklist estrutural de cada documento e radar de onde procurar erros.",
        _cmd_analisar,
        _exige_analisar,
    ),
    Passo(
        "sugerir",
        "3 · Sugerir hallazgos",
        "Propõe hallazgos parecidos do histórico. Todos precisam de ser revistos.",
        _cmd_sugerir,
        _exige_sugerir,
    ),
    Passo(
        "lpa",
        "4 · Gerar o LPA",
        "Escreve o Excel final a partir do projeto.yaml.",
        _cmd_gerar_lpa,
        _exige_gerar_lpa,
    ),
    Passo(
        "anejo",
        "5 · Gerar o Anejo A.2",
        "Base de No Conformidades em CSV, indexada pelo ID estável.",
        _cmd_anejo,
        _exige_anejo,
    ),
]


def passo(chave: str) -> Passo:
    for p in PASSOS:
        if p.chave == chave:
            return p
    raise KeyError(chave)


def projeto_tem_puntos(cfg: Config) -> int:
    """Quantos puntos já existem no projeto.yaml (0 se não existir).

    O passo 1 apaga-os ao voltar a correr, por isso a interface avisa antes.
    """
    if not cfg.projeto.exists():
        return 0
    import yaml

    try:
        dados = yaml.safe_load(cfg.projeto.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return 0
    return len(dados.get("puntos") or [])
