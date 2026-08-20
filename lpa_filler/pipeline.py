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
    skip_lpa: bool = False        # o normal é querer os puntos na folha
    substituir_sugestoes: bool = False
    revisao: bool = False
    lpa_existente: Path | None = None

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

    def _referencia_projeto(self) -> str:
        """A 'portada.referencia' do projeto.yaml atual, ou "" se não houver.

        Lida do disco a cada acesso (não em cache): quando este método corre,
        o projeto já foi escrito pelo passo 1, com a referência que o avaliador
        confirmou — é essa, não uma guardada à parte, que tem de nomear o ficheiro.
        """
        if not self.projeto.exists():
            return ""
        import yaml

        try:
            dados = yaml.safe_load(self.projeto.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return ""
        return (dados.get("portada") or {}).get("referencia") or ""

    @property
    def lpa(self) -> Path:
        from . import nomenclatura

        nome = nomenclatura.nome_ficheiro(self._referencia_projeto(), ".xlsm")
        return self.trabalho / (nome or "LPA.xlsm")

    @property
    def anejo(self) -> Path:
        from . import nomenclatura

        # O Anejo A.2 não tem sigla própria no PE/05 — fica preso ao nome do LPA
        # da mesma revisão, para os dois ficheiros se reconhecerem como o par
        # que são, em vez de "anejo_a2.csv" genérico e sem ligação a nada.
        p = nomenclatura.partes(self._referencia_projeto())
        if p:
            obra, seq, tipo, rev = p
            return self.trabalho / f"{obra}-{seq}-{tipo}-{rev:02d}_Anejo-A2.csv"
        return self.trabalho / "anejo_a2.csv"


@dataclass
class Passo:
    chave: str
    titulo: str
    descricao: str
    _comandos: Callable[[Config], list[list[str]]]
    _exige: Callable[[Config], list[str]]
    _opcional: Callable[[Config], bool] = lambda cfg: False

    def comandos(self, cfg: Config) -> list[list[str]]:
        return self._comandos(cfg)

    def em_falta(self, cfg: Config) -> list[str]:
        """O que falta preencher para este passo poder correr."""
        return self._exige(cfg)

    def opcional(self, cfg: Config) -> bool:
        """Se este passo pode ser saltado com a configuração atual.

        Não é "nunca corre" — é "não é preciso para se chegar ao fim": os
        cartões continuam clicáveis, só deixa de ser o próximo passo por
        omissão."""
        return self._opcional(cfg)


def _s(p: Path | None) -> str:
    return str(p) if p else ""


# --------------------------------------------------------------------------- #
# 1. Preparar o projeto
#
# Dois modos, conforme cfg.revisao:
#   - Projeto novo: PES + documentos recebidos -> projeto.yaml (from-docx, scan, merge).
#   - Revisão: acrescenta o novo envío a um projeto que já tem puntos, e regista
#     a versão nova (scan, update, rev). Se ainda não houver projeto.yaml nesta
#     pasta de trabalho, arranca de um LPA .xlsm já emitido (extract).


def _cmd_preparar(cfg: Config) -> list[list[str]]:
    if cfg.revisao:
        return _cmd_preparar_revisao(cfg)
    cmds = [
        ["from-docx", "-i", _s(cfg.pes), "-o", _s(cfg.meta)],
        ["scan", "-r", _s(cfg.recibida), "-o", _s(cfg.documentos)],
    ]
    merge = ["merge", "-m", _s(cfg.meta), "-d", _s(cfg.documentos), "-o", _s(cfg.projeto)]
    if cfg.solicitante:
        merge += ["--solicitante", cfg.solicitante]
    cmds.append(merge)
    return cmds


def _cmd_preparar_revisao(cfg: Config) -> list[list[str]]:
    cmds: list[list[str]] = []
    if not cfg.projeto.exists() and cfg.lpa_existente:
        cmds.append(["extract", "-i", _s(cfg.lpa_existente), "-o", _s(cfg.projeto)])
    cmds.append(["scan", "-r", _s(cfg.recibida), "-o", _s(cfg.documentos)])
    cmds.append(["update", "-p", _s(cfg.projeto), "-d", _s(cfg.documentos)])
    rev = ["rev", "-p", _s(cfg.projeto)]
    if cfg.solicitante:
        rev += ["--solicitante", cfg.solicitante]
    cmds.append(rev)
    return cmds


def _exige_preparar(cfg: Config) -> list[str]:
    if cfg.revisao:
        falta = []
        if not cfg.recibida:
            falta.append("Carpeta de los documentos recibidos (del nuevo envío)")
        if not cfg.projeto.exists() and not cfg.lpa_existente:
            falta.append("projeto.yaml de esta obra ya existente, o un LPA .xlsm del que arrancar (extract)")
        return falta
    falta = []
    if not cfg.pes:
        falta.append("Informe PES (.docx)")
    if not cfg.recibida:
        falta.append("Carpeta de los documentos recibidos")
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
        falta.append("Carpeta de los documentos recibidos")
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
        falta.append("projeto.yaml — ejecuta primero el paso 1")
    return falta


# --------------------------------------------------------------------------- #
# 4. Gerar o LPA


def _cmd_gerar_lpa(cfg: Config) -> list[list[str]]:
    cmd = ["fill", "-t", _s(cfg.template), "-d", _s(cfg.projeto), "-o", _s(cfg.lpa)]
    if cfg.skip_lpa:
        cmd.append("--skip-lpa")
    if cfg.revisao and cfg.lpa_existente:
        # É o que faz o novo desde a última vez sair a azul no Excel. Vale
        # mesmo sem ter corrido o extract nesta sessão (projeto já existente).
        cmd += ["--anterior", _s(cfg.lpa_existente)]
    return [cmd]


def _exige_gerar_lpa(cfg: Config) -> list[str]:
    falta = []
    if not cfg.template:
        falta.append("Plantilla LPA (.xlsm)")
    if not cfg.projeto.exists():
        falta.append("projeto.yaml — ejecuta primero el paso 1")
    return falta


# --------------------------------------------------------------------------- #
# 5. Anejo A.2


def _cmd_anejo(cfg: Config) -> list[list[str]]:
    return [["anejo", "-p", _s(cfg.projeto), "-o", _s(cfg.anejo), "--asignar-ids"]]


def _exige_anejo(cfg: Config) -> list[str]:
    return [] if cfg.projeto.exists() else ["projeto.yaml — ejecuta primero el paso 1"]


# --------------------------------------------------------------------------- #

PASSOS: list[Passo] = [
    Passo(
        "preparar",
        "1 · Preparar el proyecto",
        "Lee el PES, cataloga los documentos recibidos y monta el projeto.yaml.",
        _cmd_preparar,
        _exige_preparar,
    ),
    Passo(
        "analisar",
        "2 · Analizar los documentos",
        "Checklist estructural de cada documento y radar de dónde buscar errores. "
        "Prescindible si la pestaña LPA va a quedar vacía para escribirla a mano.",
        _cmd_analisar,
        _exige_analisar,
        lambda cfg: cfg.skip_lpa,
    ),
    Passo(
        "sugerir",
        "3 · Sugerir hallazgos",
        "Propone hallazgos parecidos del histórico. Todos necesitan revisión. "
        "Prescindible si la pestaña LPA va a quedar vacía para escribirla a mano.",
        _cmd_sugerir,
        _exige_sugerir,
        lambda cfg: cfg.skip_lpa,
    ),
    Passo(
        "lpa",
        "4 · Generar el LPA",
        "Escribe el Excel final a partir del projeto.yaml.",
        _cmd_gerar_lpa,
        _exige_gerar_lpa,
    ),
    Passo(
        "anejo",
        "5 · Generar el Anejo A.2",
        "Base de No Conformidades en CSV, indexada por el ID estable.",
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

    Só interessa no modo projeto novo: aí o passo 1 apaga-os ao voltar a correr,
    e a interface avisa antes. Numa revisão o `update` preserva-os, por isso não
    há nada a avisar — ver ``preparar_apaga_puntos``.
    """
    if not cfg.projeto.exists():
        return 0
    import yaml

    try:
        dados = yaml.safe_load(cfg.projeto.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return 0
    return len(dados.get("puntos") or [])


def preparar_apaga_puntos(cfg: Config) -> int:
    """Quantos puntos o passo 1 apagaria agora (0 se nenhum, ou se for revisão)."""
    return 0 if cfg.revisao else projeto_tem_puntos(cfg)
