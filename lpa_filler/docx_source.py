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

def _norm(s: str) -> str:
    return " ".join(s.split()).lower()


def _title_from_cover(docx_path: str | Path) -> str | None:
    """Lê o título do projeto da capa (caixas de texto, via XML em bruto).

    O título é o fragmento que começa por (aspas +) "PROYECTO". O python-docx
    não lê caixas de texto, por isso percorremos os <w:t> do document.xml.
    """
    try:
        xml = zipfile.ZipFile(docx_path).read("word/document.xml").decode("utf-8", "ignore")
    except Exception:
        return None
    frags = [html.unescape(re.sub(r"<[^>]+>", "", m)).strip()
             for m in re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.S)]
    for f in frags[:60]:
        if re.match(r'^["“”«»\s]*PROYECTO\b', f, re.I) and len(f) > 25:
            return f.strip().strip('"“”«»').strip()
    return None


def _code_from_filename(docx_path: str | Path) -> tuple[str | None, str | None]:
    """Deriva (código, referência LPA) do NOME do ficheiro do PES (fiável).

    'EXC2024-03868-001-PES-01' -> ('EXC2024-03868/001/PES/01', 'EXC2024-03868/002/LPA/01')
    'EXC2025-16126-1-001-PES-02' -> ('EXC2025-16126-1/001/PES/02', 'EXC2025-16126-1/002/LPA/01')
    """
    stem = Path(docx_path).stem
    m = re.match(r"(.+?)-(\d+)-([A-Za-z]{2,4})-(\d+)$", stem)
    if not m:
        return None, None
    base, num, typ, ver = m.groups()
    codigo = f"{base}/{num}/{typ.upper()}/{ver}"
    referencia = f"{base}/002/LPA/01"
    return codigo, referencia




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

    # Título da capa; código/referência do NOME do ficheiro (mais fiável que a capa).
    titulo = _title_from_cover(docx_path)
    codigo, referencia = _code_from_filename(docx_path)
    if titulo:
        out["portada"]["titulo"] = titulo
    if codigo:
        out["portada"]["codigo"] = codigo
    if referencia:
        out["portada"]["referencia"] = referencia

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
