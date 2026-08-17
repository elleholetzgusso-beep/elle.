"""Organizacao de arquivos em subpastas."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from fnmatch import fnmatch
from pathlib import Path

from .categorias import (
    CATEGORIA_SEM_EXTENSAO,
    carregar_categorias,
    categoria_de,
    indexar,
)

#: Criterios aceitos pelo comando ``organizar``.
CRITERIOS = ("tipo", "extensao", "data", "alfabetico", "documento", "envio")

#: Nombres de mes visibles al usuario final (se usan como nombre de carpeta real).
MESES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)

#: Codigo de documento no padrao ``EXC2026-16883-001-PES-01`` (com ou sem
#: prefixo de letras e com sufixos de revisao como ``_R``/``_RR``/``_borrador``).
PADRAO_DOCUMENTO = re.compile(
    r"^(?P<prefixo>[A-Za-z]{2,4})?(?P<ano>\d{4})-(?P<obra>[A-Za-z0-9]{4,10})-"
    r"(?P<numero>\d{2,4})-(?P<tipo>[A-Za-z]{2,4})(?:-(?P<versao>\d{2,3}))?"
)

PASTA_SEM_CODIGO = "Sin código"

#: Pasta de envio ja existente, no padrao ``Envío 29 20260107`` (o resto do
#: nome, como ``sin revisar``, e ignorado na leitura mas mantido no destino).
PADRAO_PASTA_ENVIO = re.compile(r"^Env[ií]o\s+(?P<numero>\d+)\s+(?P<data>\d{8})", re.IGNORECASE)


class ErroDeOrganizacao(RuntimeError):
    """Falha ao organizar os arquivos."""


@dataclass
class Movimento:
    origem: Path
    destino: Path


@dataclass
class ResultadoOrganizacao:
    base: Path
    criterio: str
    movimentos: list[Movimento] = field(default_factory=list)
    pastas_criadas: list[Path] = field(default_factory=list)
    ignorados: list[tuple[Path, str]] = field(default_factory=list)
    simulacao: bool = False


# ------------------------------------------------------------------------ envios
def envios_existentes(pasta: str | Path) -> list[tuple[date, str]]:
    """Le as pastas ``Envío N AAAAMMDD`` que ja existem, da mais antiga para a
    mais recente. Nao cria nenhuma: este criterio so distribui pelos envios
    que o Roberto ja registou."""
    base = Path(pasta).expanduser()
    if not base.is_dir():
        return []
    encontrados: list[tuple[date, str]] = []
    for item in base.iterdir():
        if not item.is_dir():
            continue
        achado = PADRAO_PASTA_ENVIO.match(item.name)
        if not achado:
            continue
        try:
            quando = datetime.strptime(achado.group("data"), "%Y%m%d").date()
        except ValueError:
            continue  # 20261356: nome parecido, data impossivel
        encontrados.append((quando, item.name))
    # Pela data e, em caso de empate, pelo nome: assim dois envios no mesmo
    # dia entram numa ordem estavel em vez de depender do sistema de ficheiros.
    return sorted(encontrados)


def envio_para(quando: date, envios: list[tuple[date, str]]) -> str | None:
    """Devolve o envio a que pertence um arquivo com a data ``quando``.

    A regra e uma so: **o ultimo envio cuja data seja igual ou anterior a do
    arquivo** — ou seja, o envio que estava aberto quando o arquivo chegou.
    Um arquivo anterior ao primeiro envio nao tem onde entrar e devolve
    ``None``, para ser deixado onde esta em vez de adivinhar.
    """
    escolhido = None
    for data_envio, nome in envios:
        if data_envio <= quando:
            escolhido = nome
        else:
            break
    return escolhido


# --------------------------------------------------------------------- criterios
def codigo_documento(nome: str) -> str | None:
    """Extrai o codigo do documento (ex.: ``001-PES``) do nome do arquivo."""
    encontrado = PADRAO_DOCUMENTO.match(Path(nome).stem)
    if not encontrado:
        return None
    return f"{encontrado.group('numero')}-{encontrado.group('tipo').upper()}"


def _subpasta(
    caminho: Path,
    criterio: str,
    indice: dict[str, str],
    formato_data: str | None,
    envios: list[tuple[date, str]] | None = None,
) -> str | None:
    """Nome da subpasta de destino, ou ``None`` se o arquivo nao tem destino
    (so acontece no criterio ``envio``, quando nao ha nenhum envio anterior)."""
    if criterio == "envio":
        momento = datetime.fromtimestamp(caminho.stat().st_mtime).date()
        return envio_para(momento, envios or [])

    if criterio == "tipo":
        return categoria_de(caminho.name, indice)

    if criterio == "extensao":
        extensao = caminho.suffix.lower().lstrip(".")
        return extensao.upper() if extensao else CATEGORIA_SEM_EXTENSAO

    if criterio == "data":
        momento = datetime.fromtimestamp(caminho.stat().st_mtime)
        if formato_data:
            return momento.strftime(formato_data)
        return f"{momento.year}/{momento.month:02d}-{MESES[momento.month - 1]}"

    if criterio == "alfabetico":
        for letra in caminho.stem:
            if letra.isalpha():
                return letra.upper()
            if letra.isdigit():
                return "0-9"
        return "#"

    if criterio == "documento":
        return codigo_documento(caminho.name) or PASTA_SEM_CODIGO

    raise ErroDeOrganizacao(
        f"Criterio '{criterio}' desconocido. Usa: {', '.join(CRITERIOS)}."
    )


# ------------------------------------------------------------------- utilitarios
def _nome_livre(destino: Path, reservados: set[Path]) -> Path:
    """Evita sobrescrever: acrescenta ' (1)', ' (2)'... quando preciso."""
    if not destino.exists() and destino not in reservados:
        return destino
    base, sufixo = destino.stem, destino.suffix
    contador = 1
    while True:
        candidato = destino.with_name(f"{base} ({contador}){sufixo}")
        if not candidato.exists() and candidato not in reservados:
            return candidato
        contador += 1


def _listar_arquivos(base: Path, recursivo: bool, incluir_ocultos: bool) -> list[Path]:
    if recursivo:
        itens = sorted(p for p in base.rglob("*") if p.is_file())
    else:
        itens = sorted(p for p in base.iterdir() if p.is_file())

    if incluir_ocultos:
        return itens
    return [
        item
        for item in itens
        if not item.name.startswith(".")
        and not any(parte.startswith(".") for parte in item.relative_to(base).parts[:-1])
    ]


# --------------------------------------------------------------------- principal
def organizar(
    pasta: str | Path,
    criterio: str = "tipo",
    *,
    recursivo: bool = False,
    incluir_ocultos: bool = False,
    simular: bool = False,
    ignorar: tuple[str, ...] = (),
    arquivo_categorias: str | Path | None = None,
    formato_data: str | None = None,
) -> ResultadoOrganizacao:
    """Move os arquivos de ``pasta`` para subpastas conforme o ``criterio``.

    Nada e sobrescrito: em caso de nome repetido o arquivo recebe um sufixo
    numerico. Com ``simular=True`` o disco nao e alterado.
    """
    base = Path(pasta).expanduser()
    if not base.is_dir():
        raise ErroDeOrganizacao(f"La carpeta '{base}' no existe.")
    if criterio not in CRITERIOS:
        raise ErroDeOrganizacao(
            f"Criterio '{criterio}' desconocido. Usa: {', '.join(CRITERIOS)}."
        )

    indice = indexar(carregar_categorias(arquivo_categorias))
    resultado = ResultadoOrganizacao(base=base, criterio=criterio, simulacao=simular)
    reservados: set[Path] = set()
    pastas_conhecidas: set[Path] = set()

    envios = envios_existentes(base) if criterio == "envio" else []
    if criterio == "envio" and not envios:
        raise ErroDeOrganizacao(
            f"En '{base}' no hay ninguna carpeta de envío (Envío N AAAAMMDD). "
            "Registra primero el envío y vuelve a organizar."
        )

    for arquivo in _listar_arquivos(base, recursivo, incluir_ocultos):
        if any(fnmatch(arquivo.name, padrao) for padrao in ignorar):
            resultado.ignorados.append((arquivo, "excluido por el patrón indicado"))
            continue

        try:
            nome_subpasta = _subpasta(arquivo, criterio, indice, formato_data, envios)
        except OSError as erro:
            resultado.ignorados.append((arquivo, f"no se pudo leer: {erro}"))
            continue

        if nome_subpasta is None:
            # Solo en el criterio 'envio': el archivo es anterior al primer
            # envío registrado. No se inventa una carpeta: se deja donde está.
            resultado.ignorados.append(
                (arquivo, f"es anterior al primer envío ({envios[0][1]})")
            )
            continue

        destino_pasta = base.joinpath(*nome_subpasta.split("/"))
        if arquivo.parent == destino_pasta:
            resultado.ignorados.append((arquivo, "ya estaba en su carpeta"))
            continue

        destino = _nome_livre(destino_pasta / arquivo.name, reservados)
        reservados.add(destino)

        if not simular:
            novas = _criar_pastas(destino_pasta, pastas_conhecidas)
            resultado.pastas_criadas.extend(novas)
            try:
                shutil.move(str(arquivo), str(destino))
            except (OSError, shutil.Error) as erro:
                resultado.ignorados.append((arquivo, f"fallo al mover: {erro}"))
                continue
        else:
            resultado.pastas_criadas.extend(_prever_pastas(destino_pasta, pastas_conhecidas))

        resultado.movimentos.append(Movimento(origem=arquivo, destino=destino))

    return resultado


def _prever_pastas(destino: Path, conhecidas: set[Path]) -> list[Path]:
    faltando: list[Path] = []
    atual = destino
    while not atual.exists() and atual not in conhecidas:
        faltando.append(atual)
        if atual.parent == atual:
            break
        atual = atual.parent
    for pasta in faltando:
        conhecidas.add(pasta)
    return list(reversed(faltando))


def _criar_pastas(destino: Path, conhecidas: set[Path]) -> list[Path]:
    novas = _prever_pastas(destino, conhecidas)
    destino.mkdir(parents=True, exist_ok=True)
    return novas


# ------------------------------------------------------------------ pastas vazias
def limpar_vazias(
    pasta: str | Path, *, simular: bool = False, manter_raiz: bool = True
) -> list[Path]:
    """Remove subpastas vazias, das mais profundas para as mais rasas."""
    base = Path(pasta).expanduser()
    if not base.is_dir():
        raise ErroDeOrganizacao(f"La carpeta '{base}' no existe.")

    removidas: list[Path] = []
    virtualmente_vazias: set[Path] = set()

    for atual in sorted((p for p in base.rglob("*") if p.is_dir()), reverse=True):
        if manter_raiz and atual == base:
            continue
        conteudo = [
            item for item in atual.iterdir() if item not in virtualmente_vazias
        ]
        if conteudo:
            continue
        if not simular:
            try:
                atual.rmdir()
            except OSError:
                continue
        virtualmente_vazias.add(atual)
        removidas.append(atual)

    return removidas
