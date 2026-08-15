"""Criacao de estruturas de pastas."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .modelos import ErroDeModelo, validar_caminho


class ErroDeCriacao(RuntimeError):
    """Falha ao criar a estrutura de pastas."""


@dataclass
class ResultadoCriacao:
    """Resumo do que foi (ou seria) criado."""

    destino: Path
    criadas: list[Path] = field(default_factory=list)
    existentes: list[Path] = field(default_factory=list)
    simulacao: bool = False

    @property
    def total(self) -> int:
        return len(self.criadas) + len(self.existentes)


def _criar_ancestrais(
    caminho: Path, ja_conhecidos: set[Path], simular: bool
) -> list[Path]:
    """Cria ``caminho`` e os pais que faltarem; devolve o que foi criado."""
    faltando: list[Path] = []
    atual = caminho
    while not atual.exists() and atual not in ja_conhecidos:
        faltando.append(atual)
        pai = atual.parent
        if pai == atual:  # chegou na raiz do sistema de arquivos
            break
        atual = pai

    criadas: list[Path] = []
    for pasta in reversed(faltando):
        if not simular:
            try:
                pasta.mkdir(exist_ok=True)
            except OSError as erro:
                raise ErroDeCriacao(f"No se pudo crear '{pasta}': {erro}") from erro
        ja_conhecidos.add(pasta)
        criadas.append(pasta)
    return criadas


def criar_estrutura(
    destino: str | Path,
    caminhos: list[str],
    *,
    simular: bool = False,
) -> ResultadoCriacao:
    """Cria as pastas de ``caminhos`` dentro de ``destino``.

    Pastas que ja existem sao mantidas intactas. Nada e apagado ou
    sobrescrito. Com ``simular=True`` nenhuma alteracao e feita no disco.
    """
    raiz = Path(destino).expanduser()
    if raiz.exists() and not raiz.is_dir():
        raise ErroDeCriacao(f"El destino '{raiz}' existe y no es una carpeta.")

    resultado = ResultadoCriacao(destino=raiz, simulacao=simular)
    conhecidos: set[Path] = set()

    resultado.criadas.extend(_criar_ancestrais(raiz, conhecidos, simular))

    for bruto in caminhos:
        try:
            relativo = validar_caminho(bruto)
        except ErroDeModelo as erro:
            raise ErroDeCriacao(str(erro)) from erro

        completo = raiz / relativo
        if completo.exists():
            if not completo.is_dir():
                raise ErroDeCriacao(
                    f"Ya existe un archivo con el nombre '{completo}'; cámbiale el nombre antes de continuar."
                )
            resultado.existentes.append(completo)
            continue
        if completo in conhecidos:
            resultado.existentes.append(completo)
            continue

        resultado.criadas.extend(_criar_ancestrais(completo, conhecidos, simular))

    return resultado
