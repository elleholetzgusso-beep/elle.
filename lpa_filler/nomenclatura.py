"""Validação da nomenclatura documental Exceltic (Mudança 5 — base PE/05).

O PE/05 exige controlo de documentos conforme a ISO/IEC 17020. O padrão é

    EXCaaaa-nnnnn[-s]-ddd-TIPO-vv        (nome de ficheiro; ex. EXC2025-00001-001-LPA-01)
    EXCaaaa-nnnnn[-s]/ddd/TIPO/vv        (referência interna; ex. EXC2025-16126-1/002/LPA/05)

onde aaaa = ano, nnnnn = nº de projeto (com sub-nº opcional -s), ddd = nº do
documento, TIPO = sigla (PES/LPA/IES/...), vv = versão a dois dígitos (a versão
inicial é sempre 01).

Só se valida o que PARECE Exceltic (começa por "EXC"): documentos de terceiros
(UTE, projetista) têm as suas próprias nomenclaturas e não geram aviso. Um
desvio produz aviso, nunca erro fatal — legados podem não seguir o padrão.
"""
from __future__ import annotations

import re
from typing import Any

_BASE = r"EXC\d{4}-\d{3,5}(?:-\d{1,2})?"
_FILE_RE = re.compile(rf"^{_BASE}-\d{{3}}-[A-Z]{{2,4}}-\d{{2}}$")
_REF_RE = re.compile(rf"^{_BASE}/\d{{3}}/[A-Z]{{2,4}}/\d{{2}}$")


def parece_exceltic(texto: str) -> bool:
    return bool(re.match(r"^\s*EXC", str(texto or ""), re.IGNORECASE))


def check_filename(stem: str) -> str | None:
    """None se OK (ou não-Exceltic); senão o motivo do aviso."""
    s = str(stem or "").strip()
    if not parece_exceltic(s):
        return None
    if _FILE_RE.match(s):
        return None
    return (
        f"'{s}' não segue o padrão EXCaaaa-nnnnn-ddd-TIPO-vv "
        f"(ex. EXC2025-00001-001-LPA-01) — PE/05 / ISO 17020"
    )


def check_referencia(ref: str) -> str | None:
    """None se OK (ou não-Exceltic); senão o motivo do aviso."""
    s = str(ref or "").strip()
    if not parece_exceltic(s):
        return None
    if _REF_RE.match(s):
        return None
    return (
        f"'{s}' não segue o padrão EXCaaaa-nnnnn/ddd/TIPO/vv "
        f"(ex. EXC2025-16126-1/002/LPA/05) — PE/05 / ISO 17020"
    )


def avisos_documentos(documentos: list[dict[str, Any]]) -> list[str]:
    """Avisos de nomenclatura para as referências de envíos que parecem Exceltic."""
    avisos: list[str] = []
    vistos: set[str] = set()
    for doc in documentos or []:
        for env in doc.get("envios") or []:
            ref = str(env.get("referencia") or "")
            if ref in vistos:
                continue
            vistos.add(ref)
            motivo = check_filename(ref)
            if motivo:
                avisos.append(motivo)
    return avisos
