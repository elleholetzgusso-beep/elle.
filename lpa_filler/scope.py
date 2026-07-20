"""Deteta a que obra pertence um hallazgo, para evitar contaminação cruzada.

Problema real (observado na base): a planilha-fonte de hallazgos mistura
comentários de vários projetos sob rótulos de documento parecidos. Ex.: o
documento ``[135.0] Perfilado banqueta`` existe tanto em Torre Pacheco/L352 como
num projeto de Lleida-Balaguer; o matching do ``suggest`` casa pelo NOME do
documento (o sinal mais forte) e traz o hallazgo do projeto errado, cujo texto
fala de enclavamentos catalães.

O único sinal fiável de proveniência é o TEXTO do hallazgo: os hallazgos de outra
obra nomeiam explicitamente topónimos/códigos de outra obra (Sueca, Cullera,
Lleida, Balaguer, ...) e nunca nomeiam a obra atual. Este módulo deteta esses
marcadores e classifica cada texto como dentro/fora/indeterminado face às
âncoras da obra atual (``scope``).

Filosofia conservadora: só se marca "fora de escopo" um texto que nomeia
POSITIVAMENTE um lugar/código e não nomeia nenhuma âncora da obra atual. Textos
genéricos (sem topónimos) nunca são penalizados — a maioria dos hallazgos é assim
(falam de tabelas, cláusulas, normas) e é reutilizável entre obras.
"""
from __future__ import annotations

import re
import unicodedata

# Gazetteer de topónimos ferroviários (minúsculas, sem acentos). NÃO é
# exaustivo — serve para DETETAR que um texto nomeia um lugar concreto. A
# decisão de "é a minha obra ou outra" vem das âncoras (scope), não desta lista.
# Estende-o à medida que a base cresce (basta acrescentar tokens).
GAZETTEER: set[str] = {
    # Corredor Torre Pacheco / L352 (Murcia)
    # ("riquelme" NÃO entra: colide com nomes de UTE/consórcio construtor,
    #  que não são topónimos — ver own_code_anchors() para evitar esse tipo
    #  de falso positivo de forma mais geral.)
    "torre pacheco", "balsicas", "murcia", "cartagena", "sutullena",
    "lorca", "totana", "alcantarilla", "beniel",
    # Sinalização Valencia (ENYSE e afins)
    "sueca", "cullera", "elx", "elche", "sagunt", "gandia", "silla", "valencia",
    "xativa", "carcaixent", "algemesi",
    # Corredor Lleida-Balaguer / Pirineus (Catalunya)
    "lleida", "balaguer", "pirineus", "cervera", "manresa", "puigverd",
    "vilanova", "tarrega",
    # Outros nós comuns
    "chamartin", "atocha", "sevilla", "cordoba", "antequera", "granada",
    "zaragoza", "huesca", "tarragona", "castellon",
}

# Códigos que identificam obra/linha: "L352", "L 352", "línea 352", "EXC2025-...".
_CODE_RE = re.compile(r"\b(?:l|linea)\s*\d{2,4}\b|\bexc\s*\d{3,}", re.IGNORECASE)


def _norm(s: str) -> str:
    """Minúsculas, sem acentos, espaços colapsados."""
    s = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


_OWN_CODE_RE = re.compile(r"exc\d+-\d+", re.IGNORECASE)


def own_code_anchors(referencia: str) -> list[str]:
    """Extrai o código da própria obra (ex. 'EXC2026-16883') da referência do
    projeto (portada.referencia), para que citar o PRÓPRIO código nunca seja
    confundido com o marcador de OUTRA obra (a regra de _CODE_RE deteta
    qualquer 'EXCnnnn', incluindo o desta obra, quando o texto cita o seu
    próprio relatório/PES por extenso)."""
    return [m.group(0) for m in _OWN_CODE_RE.finditer(_norm(referencia or ""))]


def parse_anchors(scope: str | list | None) -> list[str]:
    """Aceita 'Torre Pacheco, L352' ou ['Torre Pacheco', 'L352'] -> lista normalizada."""
    if not scope:
        return []
    if isinstance(scope, str):
        partes = re.split(r"[;,]", scope)
    else:
        partes = list(scope)
    return [a for a in (_norm(p) for p in partes) if a]


def find_markers(text: str) -> set[str]:
    """Marcadores de lugar/código presentes no texto (topónimos do gazetteer + códigos)."""
    t = _norm(text)
    if not t:
        return set()
    found = {topo for topo in GAZETTEER if topo in t}
    found.update(m.group(0).strip() for m in _CODE_RE.finditer(t))
    return found


def anchors_present(text: str, anchors: list[str]) -> bool:
    """Alguma âncora da obra atual aparece no texto (substring, sem acentos)?"""
    if not anchors:
        return False
    t = _norm(text)
    return any(a in t for a in anchors)


def classify(text: str, anchors: list[str]) -> str:
    """Classifica o texto do hallazgo face às âncoras da obra atual.

    Devolve:
      "in"      -> nomeia uma âncora da obra atual (fica).
      "out"     -> nomeia lugar(es)/código(s) mas NENHUM é da obra atual (contaminação).
      "unknown" -> não nomeia nenhum lugar/código (genérico; fica sem penalização).
    """
    if not anchors:
        return "unknown"
    if anchors_present(text, anchors):
        return "in"
    if find_markers(text):
        return "out"
    return "unknown"
