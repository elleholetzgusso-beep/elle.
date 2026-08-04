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

from . import scope

# Palavras muito comuns (ES) e ruído que não ajudam a distinguir hallazgos.
_STOP = set("""
de la el en y a los las del se que por con un una para es al lo como mas o su sus
este esta estas estos no ni e le su da do na the of anejo anexo apartado apendice
apéndice documento pagina página pag pág punto apto ver segun según debe deben
""".split())


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# Abreviaturas comuns em nomes de pastas de obra -> termos por extenso.
_ABREV = {
    "estruc": ["estructuras"],
    "ssaa": ["servicios", "afectados"],
    "pptp": ["pliego", "prescripciones", "tecnicas"],
    "presup": ["presupuesto"],
    "sit": ["situaciones"],
    "prov": ["provisionales"],
    "inst": ["instalaciones"],
    "ferr": ["ferroviarias"],
    "seg": ["seguridad"],
    "rep": ["registro", "peligros"],
    "iiff": ["instalaciones", "ferroviarias"],
    "obr": ["obras"],
    "com": ["complementarias"],
    "dren": ["drenaje"],
    "tun": ["tunel", "tuneles"],
}


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    t = _strip_accents(str(text)).lower()
    palavras = re.findall(r"[a-z0-9]+", t)
    out = {w for w in palavras if len(w) > 2 and not w.isdigit() and w not in _STOP}
    for w in list(out):
        out.update(_ABREV.get(w, []))
    return out


def load_base(csv_path: str | Path) -> list[dict]:
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _overlap(q: set[str], field: str) -> int:
    """Sobreposição com matching por prefixo: 'estruc' casa com 'estructuras'
    (>=4 letras iniciais em comum), para nomes de pastas abreviados."""
    ft = _tokens(field)
    hits = len(q & ft)
    resto_q = q - ft
    resto_f = ft - q
    for a in resto_q:
        if len(a) >= 4 and any(
            (b.startswith(a) or a.startswith(b)) and min(len(a), len(b)) >= 4 for b in resto_f
        ):
            hits += 1
    return hits


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


# Multiplicador do score quando o hallazgo parece ser de outra obra (não apaga:
# só o afunda na ordenação para que o avaliador o veja por último).
_PENAL_FORA_ESCOPO = 0.3


def _texto_do_row(row: dict) -> str:
    """Junta o texto relevante do hallazgo para deteção de escopo/marcadores."""
    return " ".join(
        str(row.get(k) or "") for k in ("hallazgo", "discusion", "documento", "punto")
    )


def _row_to_punto(n: int, documento: str, row: dict, sc: float, fora_escopo: bool = False) -> dict:
    pt = {
        "n": n,
        "eval": "",  # a atribuir pelo avaliador DESTA obra (o eval de origem induzia em erro)
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
    if fora_escopo:
        # Sinaliza contaminação provável de outra obra; o avaliador confirma/remove.
        pt["_fora_escopo"] = True
        marc = row.get("marcadores") or ", ".join(sorted(scope.find_markers(_texto_do_row(row))))
        if marc:
            pt["_marcadores"] = marc
    return pt


def suggest_for_projeto(
    base: list[dict],
    projeto: dict,
    n_per_doc: int = 5,
    min_score: float = 1,
    skip_texts: set | None = None,
    anchors: list[str] | None = None,
) -> list[dict]:
    """Para cada documento do projeto, gera puntos candidatos a partir da base.

    Cada punto leva ``_score`` (força do match) e ``_sugerido_de`` (LPA de origem)
    para triagem — ambos são ignorados pelo ``fill``. Fica ordenado por _score.

    ``anchors`` (âncoras da obra, ex. ["torre pacheco", "l352"]): se indicadas,
    os hallazgos cujo texto nomeia outra obra (e nenhuma âncora) ficam marcados
    com ``_fora_escopo`` e afundados na ordenação — não são apagados. O código
    da própria obra (portada.referencia, ex. "EXC2026-16883") é sempre acrescentado
    às âncoras automaticamente, para citar o próprio relatório nunca ser confundido
    com o marcador de outra obra.
    """
    from collections import defaultdict

    anchors = list(anchors or [])
    if anchors:
        referencia = (projeto.get("portada") or {}).get("referencia") or ""
        for a in scope.own_code_anchors(referencia):
            if a not in anchors:
                anchors.append(a)

    # Documentos desviados na triagem do scan (não avaliativos, PE/01) ficam em
    # Doc Evaluados mas não recebem sugestões de puntos.
    documentos = [
        d for d in projeto.get("documentos", []) if d.get("_triage") != "desviado"
    ]
    # 1. Para cada hallazgo, guardar o documento onde pontua MAIS ALTO (evita que um
    #    documento anterior com nome parecido "roube" hallazgos de outro melhor).
    melhor: dict = {}
    for doc in documentos:
        nombre = doc.get("nombre") or ""
        for sc, row in search(base, nombre, doc_hint=nombre, n=n_per_doc, min_score=min_score):
            # Deduplicar pelo TEXTO do hallazgo (o mesmo achado surge em vários
            # LPAs com 'punto' ligeiramente diferente) — fica o de maior score.
            chave = " ".join((row.get("hallazgo") or "").split()).lower()
            if not chave or (skip_texts and chave in skip_texts):
                continue
            if chave not in melhor or sc > melhor[chave][0]:
                melhor[chave] = (sc, nombre, row)

    # 2. Agrupar por documento, mantendo a ordem dos documentos (estrutura do LPA).
    por_doc: dict = defaultdict(list)
    for sc, nombre, row in melhor.values():
        por_doc[nombre].append((sc, row))

    puntos: list[dict] = []
    n = 1
    emitidos: set = set()
    for doc in documentos:
        nombre = doc.get("nombre") or ""
        if nombre in emitidos:  # o mesmo documento pode surgir em vários envíos
            continue
        emitidos.add(nombre)
        # Ordena por: primeiro os dentro/indeterminados, depois os fora de escopo;
        # dentro de cada grupo por score decrescente.
        candidatos = []
        for sc, row in por_doc.get(nombre, []):
            fora = anchors and scope.classify(_texto_do_row(row), anchors) == "out"
            candidatos.append((bool(fora), sc, row))
        candidatos.sort(key=lambda x: (x[0], -x[1]))
        for fora, sc, row in candidatos:
            puntos.append(_row_to_punto(n, nombre, row, sc, fora_escopo=fora))
            n += 1
    return puntos
