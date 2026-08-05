#!/usr/bin/env python3
"""Extrai todos os arquivos de uma arvore de pastas para uma unica pasta.

Exemplos:
    python extrair_arquivos.py fotos/ tudo_junto/
    python extrair_arquivos.py fotos/ tudo_junto/ --mover --limpar-vazias
    python extrair_arquivos.py docs/ so_pdfs/ --ext .pdf .docx
    python extrair_arquivos.py docs/ saida/ --simular
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def coletar_arquivos(origem: Path, destino: Path, extensoes: set[str] | None,
                     incluir_ocultos: bool) -> list[Path]:
    """Lista os arquivos da arvore de `origem`, ignorando o que esta em `destino`."""
    arquivos = []
    for caminho in sorted(origem.rglob("*")):
        if not caminho.is_file():
            continue
        # Nao reprocessa o que ja foi colocado na pasta de destino.
        if destino == caminho.parent or destino in caminho.parents:
            continue
        partes = caminho.relative_to(origem).parts
        if not incluir_ocultos and any(p.startswith(".") for p in partes):
            continue
        if extensoes and caminho.suffix.lower() not in extensoes:
            continue
        arquivos.append(caminho)
    return arquivos


def nome_com_prefixo(arquivo: Path, origem: Path, separador: str) -> str:
    """Transforma sub/pasta/foto.jpg em sub_pasta_foto.jpg."""
    return separador.join(arquivo.relative_to(origem).parts)


def nome_livre(destino: Path, nome: str, reservados: set[str]) -> Path:
    """Devolve um caminho ainda nao usado, somando _1, _2, ... quando preciso."""
    base = Path(nome).stem
    sufixo = Path(nome).suffix
    candidato = nome
    contador = 1
    while candidato.lower() in reservados or (destino / candidato).exists():
        candidato = f"{base}_{contador}{sufixo}"
        contador += 1
    reservados.add(candidato.lower())
    return destino / candidato


def extrair(origem: Path, destino: Path, mover: bool, conflito: str,
            extensoes: set[str] | None, incluir_ocultos: bool,
            usar_prefixo: bool, separador: str, simular: bool,
            limpar_vazias: bool) -> int:
    if not origem.is_dir():
        print(f"erro: pasta de origem nao encontrada: {origem}", file=sys.stderr)
        return 1

    arquivos = coletar_arquivos(origem, destino, extensoes, incluir_ocultos)
    if not arquivos:
        print("Nenhum arquivo encontrado com esses filtros.")
        return 0

    if not simular:
        destino.mkdir(parents=True, exist_ok=True)

    reservados: set[str] = set()
    copiados = pulados = sobrescritos = 0

    for arquivo in arquivos:
        nome = nome_com_prefixo(arquivo, origem, separador) if usar_prefixo else arquivo.name

        if conflito == "renomear":
            alvo = nome_livre(destino, nome, reservados)
        else:
            alvo = destino / nome
            existe = alvo.exists() or nome.lower() in reservados
            if existe and conflito == "pular":
                print(f"  pulado (ja existe): {nome}")
                pulados += 1
                continue
            if existe:
                sobrescritos += 1
            reservados.add(nome.lower())

        acao = "mover" if mover else "copiar"
        print(f"  {acao}: {arquivo.relative_to(origem)} -> {alvo.name}")

        if not simular:
            if mover:
                shutil.move(str(arquivo), str(alvo))
            else:
                shutil.copy2(arquivo, alvo)
        copiados += 1

    if mover and limpar_vazias and not simular:
        remover_pastas_vazias(origem, destino)

    print()
    print(f"Arquivos processados: {copiados}")
    if pulados:
        print(f"Pulados: {pulados}")
    if sobrescritos:
        print(f"Sobrescritos: {sobrescritos}")
    if simular:
        print("(simulacao: nada foi alterado no disco)")
    return 0


def remover_pastas_vazias(origem: Path, destino: Path) -> None:
    """Apaga as subpastas que ficaram vazias depois de mover os arquivos."""
    for pasta in sorted(origem.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not pasta.is_dir() or pasta == destino or destino in pasta.parents:
            continue
        try:
            pasta.rmdir()
            print(f"  pasta vazia removida: {pasta.relative_to(origem)}")
        except OSError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extrai todos os arquivos das subpastas para uma unica pasta.")
    parser.add_argument("origem", type=Path, help="pasta com as subpastas")
    parser.add_argument("destino", type=Path, help="pasta onde tudo sera juntado")
    parser.add_argument("--mover", action="store_true",
                        help="mover os arquivos em vez de copiar")
    parser.add_argument("--conflito", choices=["renomear", "pular", "sobrescrever"],
                        default="renomear",
                        help="o que fazer com nomes repetidos (padrao: renomear)")
    parser.add_argument("--ext", nargs="+", metavar="EXT",
                        help="extensoes a incluir, ex: --ext .jpg .png")
    parser.add_argument("--incluir-ocultos", action="store_true",
                        help="tambem processa arquivos e pastas que comecam com ponto")
    parser.add_argument("--prefixo-pasta", action="store_true",
                        help="usa o caminho no nome final, ex: sub_pasta_foto.jpg")
    parser.add_argument("--separador", default="_",
                        help="separador usado com --prefixo-pasta (padrao: _)")
    parser.add_argument("--simular", action="store_true",
                        help="mostra o que seria feito sem mexer nos arquivos")
    parser.add_argument("--limpar-vazias", action="store_true",
                        help="remove as subpastas vazias depois de mover")
    args = parser.parse_args(argv)

    extensoes = None
    if args.ext:
        extensoes = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in args.ext}

    return extrair(
        origem=args.origem.expanduser().resolve(),
        destino=args.destino.expanduser().resolve(),
        mover=args.mover,
        conflito=args.conflito,
        extensoes=extensoes,
        incluir_ocultos=args.incluir_ocultos,
        usar_prefixo=args.prefixo_pasta,
        separador=args.separador,
        simular=args.simular,
        limpar_vazias=args.limpar_vazias,
    )


if __name__ == "__main__":
    raise SystemExit(main())
