"""Reversao de operacoes registradas no historico."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .arrumador import _nome_livre


@dataclass
class ResultadoDesfazer:
    identificador: str
    restaurados: list[tuple[Path, Path]] = field(default_factory=list)
    pastas_removidas: list[Path] = field(default_factory=list)
    pastas_recriadas: list[Path] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)
    simulacao: bool = False


def desfazer_operacao(operacao: dict, *, simular: bool = False) -> ResultadoDesfazer:
    """Reverte uma operacao: devolve arquivos e apaga pastas criadas vazias."""
    resultado = ResultadoDesfazer(
        identificador=operacao.get("id", "?"), simulacao=simular
    )
    reservados: set[Path] = set()

    # 1. Arquivos voltam para o lugar de origem.
    for movimento in reversed(operacao.get("movimentos", [])):
        origem = Path(movimento["de"])
        destino_atual = Path(movimento["para"])

        if not destino_atual.exists():
            resultado.problemas.append(f"nao encontrado: {destino_atual}")
            continue

        alvo = _nome_livre(origem, reservados)
        reservados.add(alvo)
        if alvo != origem:
            resultado.problemas.append(
                f"'{origem}' ja existe; restaurado como '{alvo.name}'"
            )

        if not simular:
            try:
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destino_atual), str(alvo))
            except (OSError, shutil.Error) as erro:
                resultado.problemas.append(f"falha ao restaurar {destino_atual}: {erro}")
                continue
        resultado.restaurados.append((destino_atual, alvo))

    # 2. Pastas criadas pela operacao saem, se estiverem vazias.
    criadas = sorted(
        (Path(p) for p in operacao.get("pastas_criadas", [])),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for pasta in criadas:
        if not pasta.is_dir():
            continue
        if any(pasta.iterdir()):
            resultado.problemas.append(f"pasta nao esta vazia, mantida: {pasta}")
            continue
        if not simular:
            try:
                pasta.rmdir()
            except OSError as erro:
                resultado.problemas.append(f"falha ao remover {pasta}: {erro}")
                continue
        resultado.pastas_removidas.append(pasta)

    # 3. Pastas apagadas pela operacao (limpeza de vazias) voltam.
    removidas = sorted(
        (Path(p) for p in operacao.get("pastas_removidas", [])),
        key=lambda p: len(p.parts),
    )
    for pasta in removidas:
        if pasta.exists():
            continue
        if not simular:
            try:
                pasta.mkdir(parents=True, exist_ok=True)
            except OSError as erro:
                resultado.problemas.append(f"falha ao recriar {pasta}: {erro}")
                continue
        resultado.pastas_recriadas.append(pasta)

    return resultado
