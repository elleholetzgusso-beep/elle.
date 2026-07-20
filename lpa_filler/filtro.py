"""Triagem de documentos não avaliativos (Mudança 4 — base PE/Inspección/01).

O PE/01 classifica certos documentos recebidos como registos do sistema de
gestão (marco contratual, comunicações administrativas), fora do escopo da
avaliação técnica do produto. Este módulo classifica cada documento do ``scan``
em três categorias:

  "avaliar"  -> documento técnico normal: segue o fluxo (suggest gera candidatos).
  "desviado" -> claramente não avaliativo (oferta, acuse, resposta, carta):
                fica em Doc Evaluados mas não gera puntos de LPA.
  "incerto"  -> sinal fraco (acta, correo, ...): fica no fluxo normal, mas é
                listado para o avaliador decidir.

Filosofia conservadora (a mesma do ``scope``): só se desvia um documento com
evidência POSITIVA e forte no nome ou no conteúdo; na dúvida, "incerto" — nunca
se apaga nada, e todo desvio regista o motivo (auditável, PE/05 exige registo).
"""
from __future__ import annotations

import html
import re
import unicodedata
import zipfile
from pathlib import Path


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s_\-\.]+", " ", s).strip().lower()


# Padrões FORTES -> "desviado". Cada entrada: (regex sobre o nome normalizado,
# motivo citável no log/YAML). Regexes ancoradas em palavras completas para não
# apanhar substrings de termos técnicos.
_DESVIO = [
    (r"\boferta\b.*\bdefinicion de servicios\b", "Oferta de Definición de Servicios — registo do sistema de gestão (PE/01), fora do escopo da avaliação técnica"),
    (r"\bdefinicion de servicios\b", "Definición de Servicios — marco contratual (PE/01), não avaliativo"),
    (r"\bacuse\b.*\brecibo\b", "Acuse de recibo — comunicação administrativa, não avaliativa (PE/01)"),
    (r"\brespuesta(s)?\b.*\b(comentario|lpa|hallazgo|punto)", "Resposta a comentários/LPA — diálogo de avaliação, não documento a avaliar"),
    (r"\bcontestacion\b", "Contestación — comunicação de resposta, não documento a avaliar"),
    (r"\bcarta\b", "Carta — comunicação administrativa (PE/01)"),
    (r"\bcomunicado\b|\bcomunicacion\b", "Comunicado/comunicación — comunicação administrativa (PE/01)"),
    (r"\boficio\b", "Oficio — comunicação administrativa (PE/01)"),
    (r"\bnota de envio\b|\btransmittal\b|\balbaran\b", "Nota de envío/transmittal — registo de entrega, não avaliativo"),
    (r"\baviso\b", "Aviso — comunicação administrativa (PE/01)"),
    (r"\bconvocatoria\b", "Convocatoria — comunicação administrativa (PE/01)"),
]

# Padrões FRACOS -> "incerto" (fica no fluxo, mas listado para revisão humana).
_INCERTO = [
    (r"\bacta\b", "Acta (de reunião?) — confirmar se é objeto de avaliação"),
    (r"\bminuta\b", "Minuta — confirmar se é objeto de avaliação"),
    (r"\bcorreo\b|\be ?mail\b", "Correio eletrónico — confirmar se é objeto de avaliação"),
    (r"\bagenda\b", "Agenda — confirmar se é objeto de avaliação"),
    (r"\brespuesta(s)?\b", "Contém 'respuesta' — confirmar se é documento a avaliar ou comunicação"),
]

# Exceções técnicas aos padrões fracos, verificadas ANTES de _INCERTO: nomes
# que contêm um termo fraco mas são evidência técnica avaliada. Calibrado com a
# base real de 625 hallazgos: 9 dos 10 "incertos" eram actas de pruebas
# (FAT/SAT/internas) de projetos de sinalização — documentos que geram
# hallazgos, não atas de reunião.
_TECNICO_EXCECAO = [
    r"\bacta\b.*\bpruebas?\b",   # acta de pruebas FAT/SAT/internas
    r"\bpruebas?\b.*\bacta\b",
]

# Termos de conteúdo (primeiras linhas de um .docx) que confirmam oferta/marco
# contratual mesmo quando o nome do ficheiro não o diz.
_DESVIO_CONTEUDO = [
    (r"\boferta\b.{0,80}\bdefinicion de servicios\b", "Conteúdo identifica Oferta de Definición de Servicios (PE/01)"),
    (r"\bcondiciones economicas\b", "Conteúdo de âmbito contratual (condiciones económicas) — PE/01"),
    (r"\balcance contractual\b", "Conteúdo de âmbito contratual (alcance contractual) — PE/01"),
]


def _match(name_norm: str, patterns: list[tuple[str, str]]) -> str | None:
    for rx, motivo in patterns:
        if re.search(rx, name_norm):
            return motivo
    return None


def _docx_head(path: Path, max_frags: int = 80) -> str:
    """Primeiros fragmentos de texto de um .docx (via XML, sem python-docx).
    Devolve "" se o ficheiro não for legível — a triagem cai para o nome."""
    try:
        xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "ignore")
    except Exception:
        return ""
    frags = re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.S)[:max_frags]
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", f)) for f in frags)


def classify_name(nombre: str) -> tuple[str, str]:
    """Classifica pelo nome. Devolve (categoria, motivo). Motivo vazio = avaliar."""
    n = _norm(nombre)
    motivo = _match(n, _DESVIO)
    if motivo:
        return "desviado", motivo
    if any(re.search(rx, n) for rx in _TECNICO_EXCECAO):
        return "avaliar", ""
    motivo = _match(n, _INCERTO)
    if motivo:
        return "incerto", motivo
    return "avaliar", ""


def classify_file(path: str | Path, nombre: str | None = None) -> tuple[str, str]:
    """Classifica pelo nome e, para .docx, também pelo início do conteúdo.

    O conteúdo só é usado para PROMOVER a "desviado" (evidência positiva extra);
    nunca para desviar um documento cujo nome indica documento técnico avaliável
    com estrutura conhecida (Anejo/Apéndice/Plan/Informe/Estudio/Proyecto).
    """
    p = Path(path)
    cat, motivo = classify_name(nombre or p.stem)
    if cat == "desviado":
        return cat, motivo
    n = _norm(nombre or p.stem)
    tecnico = re.search(r"\b(anejo|anexo|apendice|plan|informe|estudio|proyecto|memoria|pliego|calculo|registro)\b", n)
    if not tecnico and p.suffix.lower() == ".docx" and p.exists():
        head = _norm(_docx_head(p))
        m = _match(head, _DESVIO_CONTEUDO)
        if m:
            return "desviado", m
    return cat, motivo
