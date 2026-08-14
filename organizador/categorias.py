"""Categorias de arquivos usadas na organizacao por tipo."""

from __future__ import annotations

import json
from pathlib import Path

# Mapa: nome da pasta de destino -> extensoes (sempre em minusculas, com ponto).
CATEGORIAS_PADRAO: dict[str, tuple[str, ...]] = {
    "Imagens": (
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp",
        ".svg", ".heic", ".ico", ".raw", ".cr2", ".nef",
    ),
    "Documentos": (
        ".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md", ".tex",
        ".pages", ".epub", ".mobi",
    ),
    "Planilhas": (".xls", ".xlsx", ".xlsm", ".ods", ".csv", ".tsv", ".numbers"),
    "Apresentacoes": (".ppt", ".pptx", ".odp", ".key"),
    "Videos": (
        ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpeg",
        ".mpg", ".m4v", ".3gp",
    ),
    "Audio": (".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"),
    "Compactados": (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz"),
    "Codigo": (
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".h", ".cpp",
        ".cs", ".go", ".rs", ".rb", ".php", ".sh", ".sql", ".html", ".css",
        ".json", ".xml", ".yml", ".yaml", ".toml", ".ipynb",
    ),
    "Programas": (".exe", ".msi", ".apk", ".deb", ".rpm", ".dmg", ".appimage"),
    "Fontes": (".ttf", ".otf", ".woff", ".woff2", ".eot"),
    "Design": (".psd", ".ai", ".xd", ".fig", ".sketch", ".indd", ".cdr"),
}

#: Pasta usada quando a extensao nao pertence a nenhuma categoria.
CATEGORIA_OUTROS = "Outros"

#: Pasta usada para arquivos sem extensao.
CATEGORIA_SEM_EXTENSAO = "Sem extensao"


def indexar(categorias: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """Inverte o mapa de categorias: extensao -> nome da pasta."""
    indice: dict[str, str] = {}
    for pasta, extensoes in categorias.items():
        for extensao in extensoes:
            indice[extensao.lower()] = pasta
    return indice


def carregar_categorias(caminho: str | Path | None = None) -> dict[str, tuple[str, ...]]:
    """Devolve as categorias padrao, opcionalmente mescladas com um JSON.

    O arquivo deve ter o formato ``{"Pasta": [".ext1", ".ext2"]}``. Categorias
    com o mesmo nome do padrao sao substituidas; as demais sao acrescentadas.
    """
    categorias = {nome: tuple(exts) for nome, exts in CATEGORIAS_PADRAO.items()}
    if caminho is None:
        return categorias

    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    if not isinstance(dados, dict):
        raise ValueError("O arquivo de categorias deve conter um objeto JSON.")

    for pasta, extensoes in dados.items():
        if not isinstance(extensoes, list):
            raise ValueError(f"A categoria '{pasta}' deve ser uma lista de extensoes.")
        normalizadas = []
        for extensao in extensoes:
            extensao = str(extensao).lower().strip()
            if not extensao.startswith("."):
                extensao = "." + extensao
            normalizadas.append(extensao)
        categorias[str(pasta)] = tuple(normalizadas)
    return categorias


def categoria_de(nome_arquivo: str, indice: dict[str, str]) -> str:
    """Descobre a pasta de destino de um arquivo pelo nome/extensao."""
    extensao = Path(nome_arquivo).suffix.lower()
    if not extensao:
        return CATEGORIA_SEM_EXTENSAO
    return indice.get(extensao, CATEGORIA_OUTROS)
