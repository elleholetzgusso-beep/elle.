"""Leitura e checklist estrutural dos documentos do 1º LPA.

Para cada documento recebido, extrai o texto e verifica se as *partes esperadas*
do seu tipo estão lá (Safety Case → 6 partes da EN 50129; REP → perigo/medida/
estado; Plan de Seguridad → gestión/ciclo de vida...). Também assinala as normas
CENELEC citadas.

IMPORTANTE — isto é um **radar, não um veredito**. Uma parte "não encontrada" só
diz "o avaliador que olhe aqui": pode estar escrita com outras palavras, num
anexo, ou ser uma digitalização (sem texto). A ausência de uma palavra-chave
nunca é, por si, uma não conformidade. Determinístico, sem IA, sem julgar.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from . import lector


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


# Tipo de documento (regex sobre o nome normalizado) -> partes esperadas.
# Cada parte: (rótulo legível, [palavras-chave; basta uma aparecer no texto]).
CHECKLISTS: list[tuple[str, list[tuple[str, list[str]]]]] = [
    (r"safety case|caso de seguridad|dossier de seguridad|dossier de segurida", [
        ("1. Definición del Sistema", ["definicion del sistema", "definicion de sistema"]),
        ("2. Gestión de la Calidad", ["gestion de la calidad", "gestion de calidad"]),
        ("3. Gestión de la Seguridad", ["gestion de la seguridad", "gestion de seguridad"]),
        ("4. Seguridad Técnica", ["seguridad tecnica"]),
        ("5. Safety Cases relacionados", ["safety case relacionado", "casos de seguridad relacionado", "safety cases relacionados"]),
        ("6. Conclusión", ["conclusion"]),
    ]),
    (r"\brep\b|registro de peligros|hazard log", [
        ("Identificação de perigos", ["peligro", "hazard", "amenaza"]),
        ("Medidas mitigadoras", ["mitigac", "medida"]),
        ("Estado do perigo", ["estado", "abierto", "cerrado", "controlado"]),
        ("SRAC / condiciones de aplicación", ["srac", "condiciones de aplicacion"]),
    ]),
    (r"plan de seguridad|plan de gestion de la seguridad", [
        ("Gestión de la seguridad", ["gestion de la seguridad"]),
        ("Ciclo de vida", ["ciclo de vida"]),
        ("Análisis/evaluación de riesgos", ["analisis de riesgo", "evaluacion de riesgo", "analisis de riesgos"]),
        ("Organización / responsabilidades", ["responsabilidad", "organizacion", "roles"]),
    ]),
    (r"estudio previo|estudio de seguridad|analisis de riesgo", [
        ("Identificação de perigos", ["peligro", "amenaza", "hazard"]),
        ("Análisis / evaluación de riesgos", ["analisis de riesgo", "evaluacion de riesgo", "matriz de riesgo"]),
        ("Medidas de seguridad", ["medida", "mitigac"]),
    ]),
    (r"verificacion|validacion|\bv&v\b|plan de v", [
        ("Verificación", ["verificacion"]),
        ("Validación", ["validacion"]),
        ("Requisitos cobertos", ["requisito", "trazabilidad"]),
    ]),
]

# Normas CENELEC — só para assinalar quais o documento cita.
_NORMAS = {
    "EN 50126": r"50126",
    "EN 50128": r"50128",
    "EN 50129": r"50129",
    "EN 50159": r"50159",
}


def _checklist_para(nombre: str) -> list[tuple[str, list[str]]] | None:
    n = _norm(nombre)
    for padrao, partes in CHECKLISTS:
        if re.search(padrao, n):
            return partes
    return None


def revisar_ficheiro(path: str | Path) -> dict[str, Any]:
    """Extrai o texto de um ficheiro e corre o checklist do seu tipo (se houver)."""
    p = Path(path)
    texto = lector.extract_text(p)
    reg: dict[str, Any] = {
        "ficheiro": p.name,
        "caracteres": len(texto),
        "texto_curto": False,  # extração deu quase nada (provável digitalização)
        "checklist": [],       # [(rótulo, presente?)]
        "normas": [],
        "notas": [],
    }
    if not texto:
        reg["notas"].append(f"sem texto — {lector.motivo_vazio(p)}")
        return reg

    # Quase sem texto: o checklist abaixo daria tudo por ausente, o que se leria
    # como "faltam estas partes" quando o que falta é a leitura do ficheiro.
    curto = lector.aviso_texto_curto(texto)
    if curto:
        reg["texto_curto"] = True
        reg["notas"].append(curto)

    t = _norm(texto)
    reg["normas"] = [nome for nome, rx in _NORMAS.items() if re.search(rx, t)]

    partes = _checklist_para(p.stem)
    if partes is None:
        reg["notas"].append("sem checklist específico para este tipo (texto extraído na mesma)")
        return reg
    for rotulo, chaves in partes:
        presente = any(_norm(c) in t for c in chaves)
        reg["checklist"].append((rotulo, presente))
    return reg


def revisar_pasta(recibida_dir: str | Path, on_file=None) -> list[dict[str, Any]]:
    """``on_file(indice, total, path)``, se indicado, é chamado antes de cada
    ficheiro — serve para o chamador (CLI) mostrar progresso em ficheiros
    grandes/lentos (ex. PDFs), onde a extração pode demorar."""
    from . import verify  # reutiliza a busca de ficheiros legíveis

    ficheiros = verify.ficheiros_legiveis(recibida_dir)
    registos = []
    for i, p in enumerate(ficheiros, 1):
        if on_file:
            on_file(i, len(ficheiros), p)
        registos.append(revisar_ficheiro(p))
    return registos


def relatorio(registos: list[dict[str, Any]]) -> str:
    linhas: list[str] = [
        f"# Leitura estrutural de {len(registos)} documentos",
        "# Partes 'não encontradas' são pistas para o avaliador olhar — não são não conformidades.\n",
    ]
    for r in registos:
        linhas.append(f"── {r['ficheiro']}  ({r['caracteres']} caracteres)")
        if r["normas"]:
            linhas.append(f"   normas citadas: {', '.join(r['normas'])}")
        for rotulo, presente in r["checklist"]:
            linhas.append(f"   {'✓' if presente else '✗'} {rotulo}")
        for nota in r["notas"]:
            linhas.append(f"   ! {nota}")
        linhas.append("")
    return "\n".join(linhas)
