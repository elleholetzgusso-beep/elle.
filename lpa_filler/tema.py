"""Classificação temática de hallazgos segundo o marco RAMS/CENELEC.

Etiqueta cada hallazgo com as áreas técnicas de segurança que menciona (Hazard
Log, Safety Case, SRAC, análise RAM, software/SIL, V&V, ciclo de vida,
interfaces). Determinístico, por palavras-chave — sem IA, no mesmo estilo do
``scope`` e do ``filtro``.

Serve para:
  - enriquecer a base do ``harvest`` (coluna ``tema``), afinando o retrieval;
  - dar uma leitura temática do conjunto de hallazgos.

Filosofia: um hallazgo pode ter vários temas (ou nenhum — muitos são sobre
assinaturas, erratas ou aclarações genéricas, que não têm área RAMS). Não se
força um tema: sem palavra-chave, fica sem etiqueta. As palavras-chave foram
calibradas contra a base real de 625 hallazgos (ver docs/GUIA.md).
"""
from __future__ import annotations

import re
import unicodedata

# Ordem = prioridade de apresentação. Cada tema: lista de padrões (regex sobre o
# texto normalizado, minúsculas sem acentos).
TEMAS: dict[str, list[str]] = {
    "Hazard Log / REP": [
        r"\bhazard log\b", r"registro de peligros", r"\brep\b", r"\bpeligro",
        r"\bamenaza", r"\briesgo", r"mitigac", r"medida.{0,15}seguridad",
    ],
    "V&V": [r"verificacion", r"validacion", r"\bv&v\b"],
    "Safety Case": [
        r"safety case", r"dossier de seguridad", r"caso de seguridad",
        r"definicion del sistema", r"definicion de sistema",
    ],
    "Interfaces": [r"\binterfaz", r"\binterfaces\b"],
    "SRAC": [
        r"\bsrac\b", r"condiciones de aplicacion", r"application conditions",
        r"condiciones.{0,20}seguridad.{0,20}export",
    ],
    "Software / SIL": [
        r"\bsoftware\b", r"\bsil\b", r"50128", r"integridad de seguridad",
        r"codigo fuente",
    ],
    "Ciclo de vida / Gestión (EN 50126)": [
        r"ciclo de vida", r"50126", r"plan de seguridad", r"gestion de la seguridad",
    ],
    "Análisis RAM": [
        r"fiabilidad", r"disponibilidad", r"mantenibilidad", r"\bfmea\b",
        r"\bamfe\b", r"\bfta\b", r"arbol de fallo", r"tasa de fallo",
        r"\bmtbf\b", r"\bmttr\b",
    ],
}

_COMPILED = {tema: [re.compile(p) for p in pats] for tema, pats in TEMAS.items()}


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


def classify(text: str) -> list[str]:
    """Temas RAMS presentes no texto, por ordem de prioridade. [] se nenhum."""
    t = _norm(text)
    if not t:
        return []
    return [tema for tema, pats in _COMPILED.items() if any(p.search(t) for p in pats)]


def as_field(text: str) -> str:
    """Temas juntos numa string para a coluna ``tema`` do CSV (ou vazio)."""
    return ", ".join(classify(text))
