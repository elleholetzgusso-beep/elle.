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


# O mesmo código, com "-" (ficheiro) ou "/" (referência): obra, sequencial, tipo
# e revisão. Serve para reconhecer o LPA da própria obra entre os recebidos.
_PARTES_RE = re.compile(rf"^({_BASE})[-/](\d{{3}})[-/]([A-Z]{{2,4}})[-/](\d{{2}})$")


def partes(texto: str) -> tuple[str, str, str, int] | None:
    """(obra, sequencial, tipo, revisão) de um código Exceltic. None se não for um."""
    m = _PARTES_RE.match((texto or "").strip())
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3), int(m.group(4))


def aviso_revisao_anterior(referencia: str, documentos: list[dict[str, Any]]) -> str | None:
    """Se entre os documentos recebidos vem um LPA desta obra mais recente que a portada.

    É o sinal de que isto é uma revisão, e não um projeto novo. Sem o aviso, o
    'merge' monta o projeto de raiz e os puntos das revisões anteriores
    desaparecem sem que nada o diga — o LPA sai como se fosse a primeira vez.
    """
    minha = partes(referencia)
    if not minha:
        return None
    obra, seq, tipo, rev = minha
    maior, achado = rev, ""
    for doc in documentos or []:
        candidatos = [doc.get("nombre") or ""]
        candidatos += [str(e.get("referencia") or "") for e in (doc.get("envios") or [])]
        for c in candidatos:
            outra = partes(c)
            if outra and (outra[0], outra[1], outra[2]) == (obra, seq, tipo) and outra[3] > maior:
                maior, achado = outra[3], c.strip()
    if not achado:
        return None
    return (
        f"entre los documentos recibidos viene '{achado}', posterior a la referencia de "
        f"la portada ({referencia}, rev. {rev:02d}). Si esto es una revisión, marca "
        f"«Revisión de un LPA ya existente»: el 'merge' monta el proyecto de cero y "
        f"pierde los puntos de las revisiones anteriores."
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
