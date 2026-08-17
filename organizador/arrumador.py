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
    mais recente."""
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


def maior_numero_envio(pasta: str | Path) -> int:
    """Maior ``N`` usado nas pastas ``Envío N ...`` que ja existem (0 se nenhuma)."""
    base = Path(pasta).expanduser()
    if not base.is_dir():
        return 0
    maior = 0
    for item in base.iterdir():
        if not item.is_dir():
            continue
        achado = PADRAO_PASTA_ENVIO.match(item.name)
        if achado:
            maior = max(maior, int(achado.group("numero")))
    return maior


def data_do_arquivo(caminho: Path) -> date:
    """Data pela qual o arquivo e agrupado: a de modificacao."""
    return datetime.fromtimestamp(caminho.stat().st_mtime).date()


def planear_envios(arquivos: list[Path], base: str | Path) -> dict[date, str]:
    """Decide que pasta de envio corresponde a cada data encontrada.

    Uma pasta por cada data distinta dos arquivos. Se ja existir um envio
    com essa data, reutiliza-o em vez de criar um repetido; as datas novas
    recebem numeros seguidos a partir do maior ja usado, **por ordem
    cronologica** — o envio mais antigo fica com o numero mais baixo, que e
    como a numeracao de envios funciona.
    """
    caminho_base = Path(base).expanduser()
    ja_existem = {quando: nome for quando, nome in envios_existentes(caminho_base)}
    proximo = maior_numero_envio(caminho_base) + 1

    datas = set()
    for arquivo in arquivos:
        try:
            datas.add(data_do_arquivo(arquivo))
        except OSError:
            continue  # o motivo fica registado no laco principal

    plano: dict[date, str] = {}
    for quando in sorted(datas):
        if quando in ja_existem:
            plano[quando] = ja_existem[quando]
            continue
        plano[quando] = f"Envío {proximo} {quando.strftime('%Y%m%d')}"
        proximo += 1
    return plano


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
    plano_envios: dict[date, str] | None = None,
) -> str:
    if criterio == "envio":
        return (plano_envios or {})[data_do_arquivo(caminho)]

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

    arquivos = _listar_arquivos(base, recursivo, incluir_ocultos)
    a_organizar = [
        arquivo for arquivo in arquivos
        if not any(fnmatch(arquivo.name, padrao) for padrao in ignorar)
    ]
    # O criterio 'envio' precisa de ver todas as datas antes de mover o
    # primeiro arquivo: os numeros dos envios novos atribuem-se por ordem
    # cronologica sobre o conjunto todo, nao arquivo a arquivo.
    plano_envios = planear_envios(a_organizar, base) if criterio == "envio" else {}

    for arquivo in arquivos:
        if any(fnmatch(arquivo.name, padrao) for padrao in ignorar):
            resultado.ignorados.append((arquivo, "excluido por el patrón indicado"))
            continue

        try:
            nome_subpasta = _subpasta(arquivo, criterio, indice, formato_data, plano_envios)
        except OSError as erro:
            resultado.ignorados.append((arquivo, f"no se pudo leer: {erro}"))
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
