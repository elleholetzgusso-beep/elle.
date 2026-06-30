"""Extrai metadados do relatório de origem (PES/PES .docx) para o YAML.

Do Plan de Evaluación (.docx) retira-se, de forma fiável:
  - evaluadores (tabela "Recurso / Posición / Funciones");
  - documentos-chave (tabela "Id. / Título / Referencia / Versión / Fecha / Autor").

Requer ``python-docx`` (``pip install python-docx``).
"""
from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path
from typing import Any

# Código do tipo EXC2025-16126-1/001/PES/01 ou EXC2024-03868/001/PES/01.
_CODE_RE = re.compile(r"EXC?\d{4}(?:-\d+)+[/-]\d+[/-][A-Z]{3}[/-]\d+", re.I)


def _norm(s: str) -> str:
    return " ".join(s.split()).lower()


def _cover_info(docx_path: str | Path) -> tuple[str | None, str | None]:
    """Lê título e código da CAPA, incluindo texto em caixas de texto (via XML).

    A capa tem, por esta ordem: "PLAN DE EVALUACIÓN INDEPENDIENTE DE SEGURIDAD",
    o título do projeto, e o código (EXC...). O python-docx não lê caixas de
    texto, por isso percorremos os <w:t> do document.xml diretamente.
    """
    try:
        xml = zipfile.ZipFile(docx_path).read("word/document.xml").decode("utf-8", "ignore")
    except Exception:
        return None, None
    frags = [html.unescape(re.sub(r"<[^>]+>", "", m)).strip()
             for m in re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.S)]

    codigo = next((_CODE_RE.search(f).group(0) for f in frags[:40] if _CODE_RE.search(f)), None)

    titulo = None
    start = next((i + 1 for i, f in enumerate(frags[:40]) if "PLAN DE EVALUAC" in f.upper()), None)
    if start is not None:
        parts = []
        for f in frags[start : start + 20]:
            if not f:
                continue
            if _CODE_RE.search(f) or f.upper().startswith(("REDACTADO", "VERSIÓN", "VERSION")):
                break
            parts.append(f)
        if parts:
            titulo = " ".join(parts).strip().strip('"“”«»').strip()
    return titulo, codigo


def _derive_lpa_ref(codigo: str) -> str | None:
    """Do código do PES sugere a referência do LPA.

    'EXC2025-16126-1/001/PES/02' -> 'EXC2025-16126-1/002/LPA/01'
    (substitui o segmento .../001/PES/NN por .../002/LPA/01; aceita / ou - como separador)
    """
    m = re.match(r"(.*?)([/-])0*1[/-]PES[/-]\d+\s*$", codigo, re.I)
    if not m:
        return None
    base, sep = m.group(1), m.group(2)
    return f"{base}{sep}002{sep}LPA{sep}01"


def _find_table(doc, header_keywords: list[str]):
    """Devolve a primeira tabela cuja 1ª linha contém todas as palavras-chave."""
    for t in doc.tables:
        if not t.rows:
            continue
        header = " | ".join(_norm(c.text) for c in t.rows[0].cells)
        if all(k in header for k in header_keywords):
            return t
    return None


def extract(docx_path: str | Path) -> dict[str, Any]:
    import docx  # import tardio para não obrigar a dependência quando não se usa

    doc = docx.Document(str(docx_path))
    out: dict[str, Any] = {"portada": {}, "documentos": []}

    # Título e código da capa (caixas de texto); fallback ao "subject" das propriedades.
    titulo, codigo = _cover_info(docx_path)
    codigo = codigo or (doc.core_properties.subject or "").strip()
    if titulo:
        out["portada"]["titulo"] = titulo
    if codigo:
        out["portada"]["codigo"] = codigo
        ref = _derive_lpa_ref(codigo)
        if ref:
            out["portada"]["referencia"] = ref

    # Evaluadores: tabela Recurso / Posición / Funciones
    t = _find_table(doc, ["recurso", "posición"])
    if t:
        evals = []
        for row in t.rows[1:]:
            cells = [c.text.strip() for c in row.cells]
            if cells and cells[0]:
                evals.append({"nombre": cells[0], "rol": cells[1] if len(cells) > 1 else ""})
        if evals:
            out["portada"]["evaluadores"] = evals

    # Documentos-chave: tabela Id/Título / Referencia / Versión / Fecha / Autor
    t = _find_table(doc, ["título", "referencia", "versión"])
    if t:
        for row in t.rows[1:]:
            cells = [c.text.strip() for c in row.cells]
            if not cells or not cells[0]:
                continue
            nombre = cells[0]
            envio = {
                "referencia": cells[1] if len(cells) > 1 and cells[1] else nombre,
                "version": cells[2] if len(cells) > 2 and cells[2] else None,
                "fecha": cells[3] if len(cells) > 3 and cells[3] else None,
                "autor": cells[4] if len(cells) > 4 and cells[4] else "UTE",
            }
            out["documentos"].append(
                {"nombre": nombre, "firmado": "NA", "estado": "auto", "envios": [envio]}
            )

    return out
