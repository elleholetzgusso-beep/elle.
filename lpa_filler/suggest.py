"""Sugere hallazgos para um novo LPA a partir da base de dados (harvest).

Matching determinístico (sem IA): compara o documento/requisito/texto-alvo com
os hallazgos históricos por sobreposição de palavras, dando mais peso ao
documento (o tipo de documento é o sinal mais forte) e ao requisito.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path
from typing import Any

# Palavras muito comuns (ES) e ruído que não ajudam a distinguir hallazgos.
_STOP = set("""
de la el en y a los las del se que por con un una para es al lo como mas o su sus
este esta estas estos no ni e le su da do na the of anejo anexo apartado apendice
apéndice documento pagina página pag pág punto apto ver segun según debe deben
""".split())


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    t = unicodedata.normalize("NFD", str(text))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    palavras = re.findall(r"[a-z0-9]+", t)
    return {w for w in palavras if len(w) > 2 and not w.isdigit() and w not in _STOP}


def load_base(csv_path: str | Path) -> list[dict]:
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _overlap(q: set[str], field: str) -> int:
    return len(q & _tokens(field))


def score(query_tokens: set[str], row: dict, doc_hint: str = "") -> float:
    """Pontua um hallazgo da base face à consulta (+ dica de documento)."""
    if not query_tokens:
        return 0.0
    doc_q = _tokens(doc_hint) or query_tokens
    return (
        3 * _overlap(doc_q, row.get("documento", ""))
        + 2 * _overlap(query_tokens, row.get("punto", ""))
        + 1 * _overlap(query_tokens, row.get("hallazgo", ""))
    )


def search(base: list[dict], query: str, doc_hint: str = "", n: int = 8, min_score: float = 1) -> list[tuple[float, dict]]:
    q = _tokens(query) | _tokens(doc_hint)
    scored = [(score(q, r, doc_hint or query), r) for r in base]
    scored = [(s, r) for s, r in scored if s >= min_score]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:n]


def _row_to_punto(n: int, documento: str, row: dict) -> dict:
    return {
        "n": n,
        "eval": row.get("eval") or "",
        "documento": documento,
        "ref_documento": "auto",
        "punto": row.get("punto") or "",
        "valoracion": row.get("valoracion") or "Importante",
        "version": None,
        "estado": "Abierto",
        "dialogo": [{"tipo": "Hallazgo", "texto": row.get("hallazgo") or ""}],
        "_sugerido_de": row.get("fuente") or "",
    }


def suggest_for_projeto(base: list[dict], projeto: dict, n_per_doc: int = 5) -> list[dict]:
    """Para cada documento do projeto, gera puntos candidatos a partir da base."""
    puntos: list[dict] = []
    vistos: set = set()
    n = 1
    for doc in projeto.get("documentos", []):
        nombre = doc.get("nombre") or ""
        for s, row in search(base, nombre, doc_hint=nombre, n=n_per_doc):
            chave = (row.get("hallazgo"), row.get("punto"))
            if chave in vistos:
                continue
            vistos.add(chave)
            puntos.append(_row_to_punto(n, nombre, row))
            n += 1
    return puntos
