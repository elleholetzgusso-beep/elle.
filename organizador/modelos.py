"""Modelos de estrutura de pastas e leitura de arquivos de definicao."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

#: Modelos prontos: nome -> (descricao, lista de pastas)
MODELOS: dict[str, tuple[str, tuple[str, ...]]] = {
    "proyecto": (
        "Projeto de obra no padrao AAAA-CODIGO-NOME",
        (
            "1_Oferta",
            "2_Doc Recebida",
            "2_Doc Recebida/mails",
            "3_Doc Trabajo",
            "4_Doc Generada",
            "4_Doc Generada/Doc",
        ),
    ),
    "projeto": (
        "Projeto de trabalho generico",
        (
            "01-Documentos",
            "02-Planilhas",
            "03-Imagens",
            "04-Apresentacoes",
            "05-Contratos",
            "06-Financeiro/Notas fiscais",
            "06-Financeiro/Orcamentos",
            "07-Entregas",
            "99-Arquivo morto",
        ),
    ),
    "pessoal": (
        "Organizacao de documentos pessoais",
        (
            "Documentos/Identificacao",
            "Documentos/Saude",
            "Documentos/Trabalho",
            "Financeiro/Comprovantes",
            "Financeiro/Impostos",
            "Financeiro/Recibos",
            "Casa/Contas",
            "Casa/Manuais",
            "Fotos",
            "Diversos",
        ),
    ),
    "estudos": (
        "Materiais de curso ou faculdade",
        (
            "Aulas",
            "Exercicios",
            "Provas/Simulados",
            "Provas/Gabaritos",
            "Resumos",
            "Bibliografia",
            "Trabalhos/Entregues",
            "Trabalhos/Rascunhos",
        ),
    ),
    "freelancer": (
        "Atendimento a clientes",
        (
            "Clientes",
            "Propostas",
            "Contratos",
            "Financeiro/A receber",
            "Financeiro/Recebido",
            "Financeiro/Despesas",
            "Marketing/Portfolio",
            "Marketing/Redes sociais",
            "Modelos",
        ),
    ),
    "fotografia": (
        "Fluxo de trabalho de fotos",
        (
            "01-Importado",
            "02-Selecao",
            "03-Edicao",
            "04-Finalizado/JPG",
            "04-Finalizado/PNG",
            "05-Entregue",
            "Presets",
            "Backup",
        ),
    ),
    "midia": (
        "Biblioteca de arquivos de midia",
        (
            "Imagens",
            "Videos",
            "Audio",
            "Documentos",
            "Compactados",
            "Outros",
        ),
    ),
    "codigo": (
        "Estrutura basica de um repositorio",
        (
            "src",
            "tests",
            "docs",
            "scripts",
            "assets",
            "config",
        ),
    ),
}


class ErroDeModelo(ValueError):
    """Erro de leitura ou validacao de uma estrutura de pastas."""


def listar_modelos() -> list[tuple[str, str, int]]:
    """Devolve ``(nome, descricao, quantidade de pastas)`` de cada modelo."""
    return [(nome, desc, len(pastas)) for nome, (desc, pastas) in sorted(MODELOS.items())]


def obter_modelo(nome: str) -> list[str]:
    """Devolve as pastas de um modelo pronto."""
    chave = nome.strip().lower()
    if chave not in MODELOS:
        disponiveis = ", ".join(sorted(MODELOS))
        raise ErroDeModelo(f"Modelo '{nome}' nao existe. Disponiveis: {disponiveis}.")
    return list(MODELOS[chave][1])


def validar_caminho(caminho: str) -> str:
    """Valida um caminho relativo de pasta e devolve-o normalizado."""
    original = caminho.strip().replace("\\", "/")
    if original.startswith("/") or re.match(r"^[A-Za-z]:/", original):
        raise ErroDeModelo(f"Use caminhos relativos, nao absolutos: '{caminho}'.")

    bruto = original.strip("/")
    if not bruto:
        raise ErroDeModelo("Nome de pasta vazio.")
    partes = [p for p in PurePosixPath(bruto).parts if p not in (".",)]
    if not partes:
        raise ErroDeModelo(f"Caminho invalido: '{caminho}'.")
    if any(parte == ".." for parte in partes):
        raise ErroDeModelo(f"Caminho invalido (usa '..'): '{caminho}'.")
    return "/".join(partes)


def analisar_texto(texto: str) -> list[str]:
    """Le uma estrutura em texto simples.

    Aceita um caminho por linha (``docs/imagens``) e tambem indentacao para
    representar a hierarquia::

        Projeto
            Documentos
            Imagens

    Linhas em branco e trechos apos ``#`` sao ignorados.
    """
    pilha: list[tuple[int, str]] = []
    caminhos: list[str] = []

    for numero, linha_original in enumerate(texto.splitlines(), start=1):
        linha = linha_original.split("#", 1)[0].rstrip()
        if not linha.strip():
            continue

        expandida = linha.replace("\t", "    ")
        recuo = len(expandida) - len(expandida.lstrip(" "))
        nome = expandida.strip().lstrip("-").strip()
        if not nome:
            continue

        while pilha and pilha[-1][0] >= recuo:
            pilha.pop()
        if recuo > 0 and not pilha:
            raise ErroDeModelo(f"Linha {numero}: indentacao sem pasta acima.")

        try:
            relativo = validar_caminho(nome)
        except ErroDeModelo as erro:
            raise ErroDeModelo(f"Linha {numero}: {erro}") from erro

        prefixo = "/".join(parte for _, parte in pilha)
        completo = f"{prefixo}/{relativo}" if prefixo else relativo
        caminhos.append(completo)
        pilha.append((recuo, relativo))

    if not caminhos:
        raise ErroDeModelo("Nenhuma pasta encontrada na definicao.")
    return caminhos


def analisar_json(dados: object, prefixo: str = "") -> list[str]:
    """Le uma estrutura vinda de JSON (lista de caminhos ou objeto aninhado)."""
    caminhos: list[str] = []

    if isinstance(dados, list):
        for item in dados:
            if isinstance(item, str):
                relativo = validar_caminho(item)
                caminhos.append(f"{prefixo}/{relativo}" if prefixo else relativo)
            elif isinstance(item, (dict, list)):
                caminhos.extend(analisar_json(item, prefixo))
            else:
                raise ErroDeModelo(f"Item invalido na estrutura: {item!r}")
        return caminhos

    if isinstance(dados, dict):
        for chave, valor in dados.items():
            relativo = validar_caminho(str(chave))
            atual = f"{prefixo}/{relativo}" if prefixo else relativo
            caminhos.append(atual)
            if valor in (None, {}, []):
                continue
            caminhos.extend(analisar_json(valor, atual))
        return caminhos

    raise ErroDeModelo("A estrutura JSON deve ser uma lista ou um objeto.")


def carregar_arquivo(caminho: str | Path) -> list[str]:
    """Le a estrutura de pastas de um arquivo ``.json`` ou de texto."""
    arquivo = Path(caminho)
    if not arquivo.is_file():
        raise ErroDeModelo(f"Arquivo de estrutura nao encontrado: {arquivo}")

    conteudo = arquivo.read_text(encoding="utf-8")
    if arquivo.suffix.lower() == ".json":
        try:
            dados = json.loads(conteudo)
        except json.JSONDecodeError as erro:
            raise ErroDeModelo(f"JSON invalido em {arquivo}: {erro}") from erro
        caminhos = analisar_json(dados)
    else:
        caminhos = analisar_texto(conteudo)

    if not caminhos:
        raise ErroDeModelo(f"Nenhuma pasta definida em {arquivo}.")
    return caminhos
