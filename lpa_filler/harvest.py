"""Constrói uma base de dados de hallazgos a partir de LPAs já preenchidos.

Lê um ou mais ``.xlsm`` de LPA, extrai todos os puntos e escreve/acrescenta um
CSV (abrível no Excel) com uma linha por hallazgo. Serve de "base de erros"
reutilizável para, mais tarde, sugerir hallazgos em novos LPAs — Python, sem IA.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path
from typing import Iterable

from . import extract, scope

FIELDS = [
    "fuente", "n", "eval", "documento", "punto", "valoracion", "estado",
    "hallazgo", "discusion", "obra", "marcadores",
]

# Código de obra no nome do ficheiro-fonte (ex. "EXC2025-16126"), quando existe.
_OBRA_RE = re.compile(r"EXC\s*\d{3,}[-\d]*", re.IGNORECASE)


def _obra_de_fuente(fuente: str) -> str:
    """Proveniência grosseira a partir do nome do LPA (código EXC, senão vazio).

    Nota: um mesmo LPA-fonte pode misturar hallazgos de várias obras, por isso
    ``obra`` (do nome do ficheiro) não separa a contaminação interna — para isso
    servem os ``marcadores`` do texto. Fica como pista de triagem.
    """
    m = _OBRA_RE.search(fuente or "")
    return re.sub(r"\s+", "", m.group(0)).upper() if m else ""

# Normalização de variantes (acentos/maiúsculas/género) para a forma canónica.
_VAL_CANON = {
    "critico": "Crítico", "critica": "Crítico",
    "importante": "Importante",
    "informativo": "Informativo", "informacion": "Informativo", "informacional": "Informativo",
    "formal": "Formal",
}
_EST_CANON = {"abierto": "Abierto", "resuelto": "Resuelto", "cerrado": "Cerrado"}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _canon(value, table: dict):
    if not value or not isinstance(value, str):
        return value
    return table.get(_strip_accents(value).strip().lower(), value.strip())


def _punto_to_row(pt: dict, fuente: str) -> dict:
    dialogo = pt.get("dialogo") or []
    hallazgo = ""
    discusion = []
    for i, d in enumerate(dialogo):
        tipo = (d.get("tipo") or "").strip()
        texto = (d.get("texto") or "").strip()
        if i == 0:
            hallazgo = texto
        elif texto:
            discusion.append(f"{tipo}: {texto}" if tipo else texto)
    texto_completo = " ".join([hallazgo, *discusion, str(pt.get("documento") or "")])
    return {
        "fuente": fuente,
        "n": pt.get("n"),
        "eval": pt.get("eval"),
        "documento": pt.get("documento"),
        "punto": pt.get("punto"),
        "valoracion": _canon(pt.get("valoracion"), _VAL_CANON),
        "estado": _canon(pt.get("estado"), _EST_CANON),
        "hallazgo": hallazgo,
        "discusion": "\n".join(discusion),
        "obra": _obra_de_fuente(fuente),
        "marcadores": ", ".join(sorted(scope.find_markers(texto_completo))),
    }


def find_lpa_files(folder: str | Path) -> list[Path]:
    """Procura ficheiros de LPA (.xlsm/.xlsx com 'LPA' no nome), recursivamente."""
    root = Path(folder)
    return sorted(
        p for p in root.rglob("*.xls[mx]")
        if "lpa" in p.name.lower() and not p.name.startswith("~$")
    )


def harvest(lpa_paths: Iterable[str | Path], out_csv: str | Path, append: bool = True) -> tuple[int, int, list[str]]:
    """Extrai os hallazgos dos LPAs para o CSV.

    Ficheiros sem a estrutura de LPA (ex.: sem aba 'Portada'/'LPA') são saltados.
    Devolve (novos, total, saltados).
    """
    out = Path(out_csv)
    rows: list[dict] = []
    seen: set = set()
    saltados: list[str] = []

    if append and out.exists():
        with out.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                rows.append(r)
                seen.add((r.get("documento"), r.get("punto"), r.get("hallazgo")))

    novos = 0
    for p in lpa_paths:
        try:
            data = extract.extract(p)
        except Exception as e:  # ficheiro não é um LPA no formato esperado
            saltados.append(f"{Path(p).name}: {type(e).__name__}")
            continue
        fuente = Path(p).stem
        for pt in data.get("puntos", []):
            row = _punto_to_row(pt, fuente)
            key = (row["documento"], row["punto"], row["hallazgo"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
            novos += 1

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    return novos, len(rows), saltados
