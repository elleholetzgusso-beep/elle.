"""Estrutura de projetos de obra no padrao ``AAAA-CODIGO-NOME``.

Reproduz a organizacao usada nos projetos::

    2026-16883-ESTACION DE TORRE PACHECO (APEADERO)
        1_Oferta
        2_Doc Recebida
            Envio 1 20260702
            mails
        3_Doc Trabajo
        4_Doc Generada
            Doc
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .criador import ErroDeCriacao, ResultadoCriacao, criar_estrutura
from .modelos import MODELOS

#: Subpastas criadas em cada projeto novo (mesma lista do modelo "proyecto").
ESTRUTURA_PROJETO: tuple[str, ...] = MODELOS["proyecto"][1]

#: Pasta que recebe os envios do cliente.
PASTA_RECEBIDA = "2_Doc Recebida"

#: Caracteres que o Windows nao aceita em nomes de pasta.
CARACTERES_PROIBIDOS = r'<>:"/\|?*'

PADRAO_ENVIO = re.compile(r"^Env[ií]o\s+(\d+)\b", re.IGNORECASE)


class ErroDeProjeto(RuntimeError):
    """Falha ao criar um projeto ou um envio."""


@dataclass
class ResultadoProjeto:
    pasta: Path
    criacao: ResultadoCriacao


def limpar_nome(texto: str) -> str:
    """Remove caracteres proibidos e espacos sobrando de um nome de pasta."""
    limpo = "".join(" " if letra in CARACTERES_PROIBIDOS else letra for letra in texto)
    limpo = re.sub(r"\s+", " ", limpo).strip(" .")
    if not limpo:
        raise ErroDeProjeto("El nombre indicado quedó vacío después de la limpieza.")
    return limpo


def nome_projeto(ano: int | str, codigo: str, nome: str) -> str:
    """Monta ``2026-16883-ESTACION DE TORRE PACHECO (APEADERO)``."""
    ano_texto = str(ano).strip()
    if not re.fullmatch(r"\d{4}", ano_texto):
        raise ErroDeProjeto(f"Año inválido: '{ano}'. Usa cuatro dígitos, ej.: 2026.")
    codigo_limpo = limpar_nome(str(codigo)).replace(" ", "")
    if not codigo_limpo:
        raise ErroDeProjeto("Indica el código del proyecto, ej.: 16883.")
    return f"{ano_texto}-{codigo_limpo}-{limpar_nome(nome).upper()}"


def criar_projeto(
    destino: str | Path,
    ano: int | str,
    codigo: str,
    nome: str,
    *,
    estrutura: tuple[str, ...] | list[str] = ESTRUTURA_PROJETO,
    simular: bool = False,
) -> ResultadoProjeto:
    """Cria a pasta do projeto e todas as subpastas do padrao."""
    pasta = Path(destino).expanduser() / nome_projeto(ano, codigo, nome)
    try:
        criacao = criar_estrutura(pasta, list(estrutura), simular=simular)
    except ErroDeCriacao as erro:
        raise ErroDeProjeto(str(erro)) from erro
    return ResultadoProjeto(pasta=pasta, criacao=criacao)


def pasta_recebida(projeto: str | Path) -> Path:
    """Descobre a pasta ``2_Doc Recebida`` a partir da pasta do projeto."""
    caminho = Path(projeto).expanduser()
    if not caminho.is_dir():
        raise ErroDeProjeto(f"La carpeta '{caminho}' no existe.")

    if caminho.name.lower().startswith("2_"):
        return caminho

    exata = caminho / PASTA_RECEBIDA
    if exata.is_dir():
        return exata

    for item in sorted(caminho.iterdir()):
        if item.is_dir() and item.name.lower().startswith("2_"):
            return item
    return exata


def proximo_numero_envio(pasta: str | Path) -> int:
    """Devolve o proximo numero de ``Envio N`` dentro da pasta informada."""
    caminho = Path(pasta).expanduser()
    if not caminho.is_dir():
        return 1
    maior = 0
    for item in caminho.iterdir():
        if not item.is_dir():
            continue
        encontrado = PADRAO_ENVIO.match(item.name)
        if encontrado:
            maior = max(maior, int(encontrado.group(1)))
    return maior + 1


def nome_envio(numero: int, quando: date, observacao: str | None = None) -> str:
    """Monta ``Envío 10 20260807 sin revisar``."""
    partes = [f"Envío {numero}", quando.strftime("%Y%m%d")]
    if observacao:
        partes.append(limpar_nome(observacao))
    return " ".join(partes)


def criar_envio(
    projeto: str | Path,
    *,
    data_envio: date | str | None = None,
    numero: int | None = None,
    observacao: str | None = None,
    simular: bool = False,
) -> Path:
    """Cria a proxima pasta ``Envío N AAAAMMDD`` da documentacao recebida."""
    destino_base = pasta_recebida(projeto)

    if isinstance(data_envio, str):
        texto = data_envio.strip()
        for formato in ("%Y%m%d", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                quando = datetime.strptime(texto, formato).date()
                break
            except ValueError:
                continue
        else:
            raise ErroDeProjeto(
                f"Fecha inválida: '{data_envio}'. Usa AAAAMMDD, AAAA-MM-DD o DD/MM/AAAA."
            )
    else:
        quando = data_envio or date.today()

    if numero is None:
        numero = proximo_numero_envio(destino_base)
    elif numero < 1:
        raise ErroDeProjeto("El número de envío debe ser 1 o mayor.")

    pasta = destino_base / nome_envio(numero, quando, observacao)
    if pasta.exists():
        raise ErroDeProjeto(f"La carpeta '{pasta}' ya existe.")
    if not simular:
        pasta.mkdir(parents=True)
    return pasta
