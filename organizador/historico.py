"""Registro das operacoes realizadas, para permitir desfazer."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

#: Local padrao do historico (pode ser trocado pela variavel de ambiente).
VARIAVEL_AMBIENTE = "ORGANIZADOR_HISTORICO"


def caminho_padrao() -> Path:
    """Caminho do arquivo de historico."""
    definido = os.environ.get(VARIAVEL_AMBIENTE)
    if definido:
        return Path(definido).expanduser()
    return Path.home() / ".organizador-pastas" / "historico.json"


class Historico:
    """Le e grava o arquivo JSON com as operacoes executadas."""

    def __init__(self, caminho: str | Path | None = None, limite: int = 100) -> None:
        self.caminho = Path(caminho).expanduser() if caminho else caminho_padrao()
        self.limite = limite

    # ------------------------------------------------------------------ leitura
    def carregar(self) -> list[dict]:
        if not self.caminho.is_file():
            return []
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        operacoes = dados.get("operacoes") if isinstance(dados, dict) else None
        return operacoes if isinstance(operacoes, list) else []

    def listar(self, quantidade: int | None = None) -> list[dict]:
        """Operacoes da mais recente para a mais antiga."""
        operacoes = list(reversed(self.carregar()))
        return operacoes[:quantidade] if quantidade else operacoes

    def obter(self, identificador: str) -> dict | None:
        for operacao in reversed(self.carregar()):
            if operacao.get("id") == identificador:
                return operacao
        return None

    def ultima(self) -> dict | None:
        operacoes = self.carregar()
        return operacoes[-1] if operacoes else None

    # ------------------------------------------------------------------ escrita
    def _gravar(self, operacoes: list[dict]) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        conteudo = {"versao": 1, "operacoes": operacoes[-self.limite :]}
        temporario = self.caminho.with_suffix(self.caminho.suffix + ".tmp")
        temporario.write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporario.replace(self.caminho)

    def registrar(
        self,
        tipo: str,
        base: str | Path,
        *,
        movimentos: list[dict] | None = None,
        pastas_criadas: list[str] | None = None,
        pastas_removidas: list[str] | None = None,
        detalhes: dict | None = None,
    ) -> str:
        """Guarda uma operacao e devolve o identificador gerado."""
        operacoes = self.carregar()
        agora = datetime.now()
        identificador = agora.strftime("%Y%m%d-%H%M%S") + f"-{len(operacoes) + 1:03d}"
        operacoes.append(
            {
                "id": identificador,
                "tipo": tipo,
                "data_hora": agora.isoformat(timespec="seconds"),
                "base": str(base),
                "movimentos": movimentos or [],
                "pastas_criadas": pastas_criadas or [],
                "pastas_removidas": pastas_removidas or [],
                "detalhes": detalhes or {},
            }
        )
        self._gravar(operacoes)
        return identificador

    def remover(self, identificador: str) -> bool:
        operacoes = self.carregar()
        restantes = [op for op in operacoes if op.get("id") != identificador]
        if len(restantes) == len(operacoes):
            return False
        self._gravar(restantes)
        return True

    def limpar(self) -> None:
        self._gravar([])


def resumir(operacao: dict) -> str:
    """Texto curto descrevendo uma operacao do historico."""
    tipo = operacao.get("tipo", "?")
    quantidade_mov = len(operacao.get("movimentos", []))
    quantidade_criadas = len(operacao.get("pastas_criadas", []))
    quantidade_removidas = len(operacao.get("pastas_removidas", []))

    partes = []
    if quantidade_mov:
        partes.append(f"{quantidade_mov} arquivo(s) movido(s)")
    if quantidade_criadas:
        partes.append(f"{quantidade_criadas} pasta(s) criada(s)")
    if quantidade_removidas:
        partes.append(f"{quantidade_removidas} pasta(s) removida(s)")
    detalhe = ", ".join(partes) if partes else "sem alteracoes"

    return (
        f"{operacao.get('id', '?')}  {operacao.get('data_hora', '?')}  "
        f"[{tipo}] {operacao.get('base', '?')} -- {detalhe}"
    )
