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
from pathlib import Path
from typing import Any

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


def _file_date(path: Path) -> dt.date:
    return dt.date.fromtimestamp(path.stat().st_mtime)


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


def scan(
    recibida_dir: str | Path,
    exts: tuple[str, ...] = DEFAULT_EXTS,
    autor: str = "",
    group_by: str = "file",
    estado: str = "auto",
) -> list[dict[str, Any]]:
    """Devolve uma lista `documentos` pronta a colocar no YAML.

    group_by="file"   -> nombre = nome do ficheiro (1 documento por ficheiro,
                         agrupado pelos vários envíos em que aparece).
    group_by="folder" -> nombre = nome da pasta que contém o ficheiro,
                         referencia = nome do ficheiro (vários ficheiros da mesma
                         pasta ficam como linhas do mesmo documento).
    """
    root = Path(recibida_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"Pasta não encontrada: {root}")

    # chave de agrupamento -> {nombre, envios}  (preservando ordem de descoberta)
    docs: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    envio_dirs = sorted(
        (d for d in root.iterdir() if d.is_dir()),
        key=lambda d: (_parse_envio(d.name)[0] or 9999, d.name),
    )
    for ed in envio_dirs:
        envio_num, envio_date = _parse_envio(ed.name)
        for f in sorted(ed.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in exts:
                continue
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
                docs[key] = {"nombre": nombre, "envios": []}
                order.append(key)
            docs[key]["envios"].append(
                {
                    "referencia": referencia,
                    "version": version,
                    "fecha": _file_date(f),
                    "autor": autor or None,
                    "envio": envio_num,
                    "fecha_envio": envio_date,
                }
            )

    return [
        {"nombre": docs[k]["nombre"], "firmado": "NA", "estado": estado, "envios": docs[k]["envios"]}
        for k in order
    ]
