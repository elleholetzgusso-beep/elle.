"""Percorre as pastas de documentos recebidos e gera a secção `documentos`.

Estrutura esperada (ver capturas do projeto)::

    1_Doc Recibida/
        Envío 1 20251126/.../  Anejo 01...pdf, Apéndice 1_REP.xlsx, ...
        Envío 2 20260216/.../  ...

O nome da pasta de cada envío dá o número e a data (``Envío <n> <AAAAMMDD>``).
Cada ficheiro de documento (pdf/docx/xlsx/...) vira uma entrada; o mesmo
documento (mesmo nome) é agrupado pelos vários envíos em que aparece.
"""
from __future__ import annotations

import datetime as dt
import re
import zipfile
from pathlib import Path
from typing import Any

from . import filtro

DEFAULT_EXTS = (".pdf", ".docx", ".doc", ".xlsx", ".xlsm", ".xls", ".dwg")
_ENVIO_RE = re.compile(r"env[íi]o\s*0*(\d+)\D*(\d{8})?", re.IGNORECASE)


def _parse_envio(folder_name: str) -> tuple[int | None, dt.date | None]:
    m = _ENVIO_RE.search(folder_name)
    if not m:
        return None, None
    num = int(m.group(1))
    date = None
    if m.group(2):
        try:
            date = dt.datetime.strptime(m.group(2), "%Y%m%d").date()
        except ValueError:
            date = None
    return num, date


# A "Fecha" da aba Doc Evaluados é a data *do documento* (a da versão que o
# cliente emitiu), não a do envío nem a do ficheiro em disco. Não está em lado
# nenhum de forma fiável — a data de modificação do ficheiro passa a ser a da
# cópia assim que alguém o descarrega — mas está muitas vezes no próprio nome.
#
# Sem data no nome fica por preencher, de propósito: uma data errada num registo
# de conformidade é pior do que uma célula vazia, porque parece verdadeira.
_MESES = {
    "ENE": 1, "JAN": 1, "FEB": 2, "MAR": 3, "ABR": 4, "APR": 4, "MAY": 5,
    "JUN": 6, "JUL": 7, "AGO": 8, "AUG": 8, "SEP": 9, "SET": 9, "OCT": 10,
    "OUT": 10, "NOV": 11, "DIC": 12, "DEC": 12,
}
# Ano a dois dígitos só conta neste intervalo: evita ler "000105" (de um código
# como CZE-000105) como uma data do ano 2000.
_ANO_MIN, _ANO_MAX = 15, 35

_D8 = re.compile(r"(?<!\d)(\d{8})(?!\d)")
_D6 = re.compile(r"(?<!\d)(\d{6})(?!\d)")
_DMY = re.compile(r"(?<!\d)(\d{1,2})[._\-](\d{1,2})[._\-](\d{4}|\d{2})(?!\d)")
# `\w` inclui o sublinhado, e os nomes destes ficheiros estão cheios deles
# ("Hito 4_08SEP25"). A âncora tem de excluir letras e dígitos, não o separador.
_DMONY = re.compile(
    r"(?<![A-Za-z0-9])(\d{1,2})\s*([A-Za-z]{3})\s*(\d{4}|\d{2})(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def _data_valida(ano: int, mes: int, dia: int) -> dt.date | None:
    try:
        return dt.date(ano, mes, dia)
    except ValueError:
        return None


def _ano_completo(bruto: str) -> int | None:
    n = int(bruto)
    if len(bruto) == 4:
        return n if 1990 <= n <= 2099 else None
    return 2000 + n if _ANO_MIN <= n <= _ANO_MAX else None


_CREATED_RE = re.compile(r"<dcterms:created[^>]*>(\d{4})-(\d{2})-(\d{2})")


def _data_do_docx(path: Path) -> dt.date | None:
    """A data de criação gravada dentro do próprio .docx (docProps/core.xml).

    Ao contrário da data do ficheiro em disco, esta viaja com o documento: não
    muda ao copiar nem ao descarregar. É só uma leitura de um XML pequeno dentro
    do zip, por isso não abranda o scan.

    Os .pdf ficam de fora de propósito: ler-lhes os metadados obriga a abrir e
    interpretar a estrutura do ficheiro, e um .pdf mal formado pode prender-se
    lá dentro — o `scan` percorre a árvore inteira dos recebidos e tem de
    continuar a ser rápido e a não bloquear.
    """
    if path.suffix.lower() != ".docx":
        return None
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("docProps/core.xml").decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001  (não é .docx válido, ou não tem core.xml)
        return None
    m = _CREATED_RE.search(xml)
    if not m:
        return None
    return _data_valida(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def data_do_documento(path: Path) -> dt.date | None:
    """A data do documento: primeiro o nome, depois o que o ficheiro traz dentro.

    O nome tem prioridade porque é onde quem emite costuma pôr a data da versão;
    os metadados dizem quando o ficheiro foi criado, que é próximo mas não é a
    mesma coisa. Sem nenhum dos dois, fica por preencher.
    """
    return _data_do_nome(path.stem) or _data_do_docx(path)


def _data_do_nome(stem: str) -> dt.date | None:
    """A data que o nome do ficheiro carrega, se carregar alguma.

    Reconhece 20260202, 250810 (AAMMDD), 16062025 (DDMMAAAA), 03_02_2026 e
    08SEP25. Devolve None se não houver nada que se pareça com uma data — não
    se inventa nem se cai na data do ficheiro em disco.
    """
    for m in _DMONY.finditer(stem):
        mes = _MESES.get(m.group(2).upper())
        ano = _ano_completo(m.group(3))
        if mes and ano:
            d = _data_valida(ano, mes, int(m.group(1)))
            if d:
                return d

    for m in _DMY.finditer(stem):
        ano = _ano_completo(m.group(3))
        if ano:
            d = _data_valida(ano, int(m.group(2)), int(m.group(1)))
            if d:
                return d

    for m in _D8.finditer(stem):
        s = m.group(1)
        # 8 dígitos são ambíguos: 20260202 é AAAAMMDD, 16062025 é DDMMAAAA.
        # Decide-se por qual das pontas parece um ano.
        if 1990 <= int(s[:4]) <= 2099:
            d = _data_valida(int(s[:4]), int(s[4:6]), int(s[6:]))
            if d:
                return d
        if 1990 <= int(s[4:]) <= 2099:
            d = _data_valida(int(s[4:]), int(s[2:4]), int(s[:2]))
            if d:
                return d

    for m in _D6.finditer(stem):
        s = m.group(1)
        # Também ambíguos: 250810 é AAMMDD, 080925 é DDMMAA. Não colidem, porque
        # só uma das pontas cai no intervalo de anos aceite.
        ano = _ano_completo(s[:2])
        if ano:
            d = _data_valida(ano, int(s[2:4]), int(s[4:]))
            if d:
                return d
        ano = _ano_completo(s[4:])
        if ano:
            d = _data_valida(ano, int(s[2:4]), int(s[:2]))
            if d:
                return d
    return None


# Marcador de versão no fim do nome: "_v06", " v8", "-V8.0", "_v 7" ...
_VERSION_RE = re.compile(r"[\s_\-]+v\.?\s*(\d+(?:\.\d+)?)\s*$", re.IGNORECASE)


def _clean_name_version(stem: str) -> tuple[str, object]:
    """Separa o nome do documento da versão, quando o nome termina em 'vNN'.

    'Apéndice 1_REP 1_v06' -> ('Apéndice 1_REP 1', 6)
    'Anejo 27. Estudio Previo Seguridad' -> ('Anejo 27. Estudio Previo Seguridad', None)
    (O '27' de 'Anejo 27' não é confundido: exige o prefixo 'v'.)
    """
    m = _VERSION_RE.search(stem)
    if not m:
        return stem.strip(), None
    raw = m.group(1)
    version: object = float(raw) if "." in raw else int(raw)
    return stem[: m.start()].strip(), version


def _pastas_de_envio(root: Path, exts: tuple[str, ...]) -> list[Path]:
    """As pastas a percorrer como envíos.

    O normal é ``Doc Recibida/Envío N .../ficheiros``, e cada subpasta é um
    envío. Mas apontar diretamente a **uma** pasta de envío é igualmente
    natural, e aí os ficheiros estão à vista, sem subpasta nenhuma.

    Sem este caso, o ``scan`` devolvia 0 documentos e ninguém percebia porquê:
    o ``leer`` e o ``radar``, que varrem recursivamente, encontravam os mesmos
    ficheiros na mesma — e o LPA saía com 0 puntos sem um único erro.
    """
    subpastas = sorted(
        (d for d in root.iterdir() if d.is_dir()),
        key=lambda d: (_parse_envio(d.name)[0] or 9999, d.name),
    )
    # A própria pasta é um envío? ('Envío 44 20260727')
    if _parse_envio(root.name)[0] is not None:
        return [root]
    # Sem subpastas, mas com documentos à vista: trata-se de um envío só.
    soltos = any(
        f.is_file() and f.suffix.lower() in exts and not f.name.startswith(("~$", "."))
        for f in root.iterdir()
    )
    if soltos and not subpastas:
        return [root]
    return subpastas


def scan(
    recibida_dir: str | Path,
    exts: tuple[str, ...] = DEFAULT_EXTS,
    autor: str = "",
    group_by: str = "file",
    estado: str = "auto",
    triage: bool = True,
) -> list[dict[str, Any]]:
    """Devolve uma lista `documentos` pronta a colocar no YAML.

    group_by="file"   -> nombre = nome do ficheiro (1 documento por ficheiro,
                         agrupado pelos vários envíos em que aparece).
    group_by="folder" -> nombre = nome da pasta que contém o ficheiro,
                         referencia = nome do ficheiro (vários ficheiros da mesma
                         pasta ficam como linhas do mesmo documento).
    triage=True       -> classifica documentos não avaliativos (PE/01): os
                         "desviado" ficam em Doc Evaluados mas o suggest não
                         lhes gera puntos; os "incerto" são listados p/ revisão.
                         O motivo fica em '_triage_motivo' (registo auditável).
    """
    root = Path(recibida_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"Pasta não encontrada: {root}")

    # chave de agrupamento -> {nombre, envios}  (preservando ordem de descoberta)
    docs: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    envio_dirs = _pastas_de_envio(root, exts)
    for ed in envio_dirs:
        envio_num, envio_date = _parse_envio(ed.name)
        for f in sorted(ed.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in exts:
                continue
            if f.name.startswith("~$") or f.name.startswith("."):
                continue  # ficheiro de bloqueio temporário do Word/Excel, ou oculto
            name, version = _clean_name_version(f.stem)
            referencia = f.stem.strip()
            # "folder" só faz sentido se houver uma subpasta de documento entre o
            # envío e o ficheiro; se o ficheiro está direto na pasta do envío
            # (f.parent == ed), cair para o modo "file" (nome = nome do ficheiro).
            if group_by == "folder" and f.parent != ed:
                key = str(f.parent)          # único por pasta
                nombre = f.parent.name        # nome da pasta como nombre
            else:
                key = name                    # 1 documento por nome de ficheiro
                nombre = name
            if key not in docs:
                docs[key] = {"nombre": nombre, "envios": [], "_path": f}
                order.append(key)
            docs[key]["envios"].append(
                {
                    "referencia": referencia,
                    "version": version,
                    "fecha": data_do_documento(f),
                    "autor": autor or None,
                    "envio": envio_num,
                    "fecha_envio": envio_date,
                }
            )

    out: list[dict[str, Any]] = []
    for k in order:
        doc: dict[str, Any] = {
            "nombre": docs[k]["nombre"],
            "firmado": "NA",
            "estado": estado,
            "envios": docs[k]["envios"],
        }
        if triage:
            cat, motivo = filtro.classify_file(docs[k]["_path"], docs[k]["nombre"])
            if cat != "avaliar":
                doc["_triage"] = cat
                doc["_triage_motivo"] = motivo
        out.append(doc)
    return out
