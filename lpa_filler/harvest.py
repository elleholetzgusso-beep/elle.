"""Constrói uma base de dados de hallazgos a partir de LPAs já preenchidos.

Lê um ou mais ``.xlsm`` de LPA, extrai todos os puntos e escreve/acrescenta um
CSV (abrível no Excel) com uma linha por hallazgo. Serve de "base de erros"
reutilizável para, mais tarde, sugerir hallazgos em novos LPAs — Python, sem IA.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from . import extract

FIELDS = ["fuente", "n", "eval", "documento", "punto", "valoracion", "estado", "hallazgo", "discusion"]


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
    return {
        "fuente": fuente,
        "n": pt.get("n"),
        "eval": pt.get("eval"),
        "documento": pt.get("documento"),
        "punto": pt.get("punto"),
        "valoracion": pt.get("valoracion"),
        "estado": pt.get("estado"),
        "hallazgo": hallazgo,
        "discusion": "\n".join(discusion),
    }


def find_lpa_files(folder: str | Path) -> list[Path]:
    """Procura ficheiros de LPA (.xlsm com 'LPA' no nome) numa pasta, recursivamente."""
    root = Path(folder)
    return sorted(p for p in root.rglob("*.xls[mx]") if "lpa" in p.name.lower())


def harvest(lpa_paths: Iterable[str | Path], out_csv: str | Path, append: bool = True) -> tuple[int, int]:
    """Extrai os hallazgos dos LPAs para o CSV. Devolve (novos, total)."""
    out = Path(out_csv)
    rows: list[dict] = []
    seen: set = set()

    if append and out.exists():
        with out.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                rows.append(r)
                seen.add((r.get("documento"), r.get("punto"), r.get("hallazgo")))

    novos = 0
    for p in lpa_paths:
        data = extract.extract(p)
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
    return novos, len(rows)
