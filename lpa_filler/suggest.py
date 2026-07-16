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


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    t = _strip_accents(str(text)).lower()
    palavras = re.findall(r"[a-z0-9]+", t)
    return {w for w in palavras if len(w) > 2 and not w.isdigit() and w not in _STOP}


def load_base(csv_path: str | Path) -> list[dict]:
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _overlap(q: set[str], field: str) -> int:
    return len(q & _tokens(field))


def score(query_tokens: set[str], row: dict, doc_hint: str = "") -> float:
    """Pontua um hallazgo da base face à consulta (+ dica de documento).

    Hallazgos com estado 'Cerrado' pesam mais (foram validados na prática: o
    avaliador confirmou a não conformidade e o fecho); 'Resuelto' um pouco
    menos; 'Abierto' não tem esse reforço (ainda não confirmado).
    """
    if not query_tokens:
        return 0.0
    doc_q = _tokens(doc_hint) or query_tokens
    base = (
        3 * _overlap(doc_q, row.get("documento", ""))
        + 2 * _overlap(query_tokens, row.get("punto", ""))
        + 1 * _overlap(query_tokens, row.get("hallazgo", ""))
    )
    peso_estado = {"cerrado": 1.15, "resuelto": 1.05}.get(
        _strip_accents((row.get("estado") or "")).strip().lower(), 1.0
    )
    return base * peso_estado


def search(
    base: list[dict],
    query: str,
    doc_hint: str = "",
    n: int = 8,
    min_score: float = 1,
    valoracion: str | None = None,
) -> list[tuple[float, dict]]:
    """valoracion: se indicado (Crítico/Importante/Informativo/Formal), filtra a base antes de pontuar."""
    pool = base
    if valoracion:
        alvo = _strip_accents(valoracion).strip().lower()
        pool = [r for r in base if _strip_accents((r.get("valoracion") or "")).strip().lower() == alvo]
    q = _tokens(query) | _tokens(doc_hint)
    scored = [(score(q, r, doc_hint or query), r) for r in pool]
    scored = [(s, r) for s, r in scored if s >= min_score]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:n]


def _row_to_punto(n: int, documento: str, row: dict, sc: float) -> dict:
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
        "_score": round(sc, 1),
    }


def suggest_for_projeto(base: list[dict], projeto: dict, n_per_doc: int = 5, min_score: float = 1) -> list[dict]:
    """Para cada documento do projeto, gera puntos candidatos a partir da base.

    Cada punto leva ``_score`` (força do match) e ``_sugerido_de`` (LPA de origem)
    para triagem — ambos são ignorados pelo ``fill``. Fica ordenado por _score.
    """
    from collections import defaultdict

    documentos = projeto.get("documentos", [])
    # 1. Para cada hallazgo, guardar o documento onde pontua MAIS ALTO (evita que um
    #    documento anterior com nome parecido "roube" hallazgos de outro melhor).
    melhor: dict = {}
    for doc in documentos:
        nombre = doc.get("nombre") or ""
        for sc, row in search(base, nombre, doc_hint=nombre, n=n_per_doc, min_score=min_score):
            # Deduplicar pelo TEXTO do hallazgo (o mesmo achado surge em vários
            # LPAs com 'punto' ligeiramente diferente) — fica o de maior score.
            chave = " ".join((row.get("hallazgo") or "").split()).lower()
            if not chave:
                continue
            if chave not in melhor or sc > melhor[chave][0]:
                melhor[chave] = (sc, nombre, row)

    # 2. Agrupar por documento, mantendo a ordem dos documentos (estrutura do LPA).
    por_doc: dict = defaultdict(list)
    for sc, nombre, row in melhor.values():
        por_doc[nombre].append((sc, row))

    puntos: list[dict] = []
    n = 1
    for doc in documentos:
        nombre = doc.get("nombre") or ""
        for sc, row in sorted(por_doc.get(nombre, []), key=lambda x: x[0], reverse=True):
            puntos.append(_row_to_punto(n, nombre, row, sc))
            n += 1
    return puntos
