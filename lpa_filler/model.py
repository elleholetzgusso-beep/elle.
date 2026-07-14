"""Modelo de dados e carregamento do ficheiro de projeto (YAML/JSON).

A estrutura esperada do ficheiro de dados é:

portada:
  titulo: "PROYECTO DE ..."
  subtitulo: "Listado de Puntos Abiertos (LPA)"
  referencia: "EXC2025-16126-1/002/LPA/05"
  normativa: "Anexo I del Reglamento ..."
  evaluadores:
    - {nombre: "Miriam Romera (MRG)", rol: "Evaluador técnico (supervisada)"}
    - {nombre: "Soukaina Meliani (SM)", rol: "Evaluador técnico"}
    - {nombre: "Roberto Abad (RAM)", rol: "Responsable de Evaluación"}

versiones:                       # aba "Control de versiones"
  - {rev: 1, fecha: 2026-01-12, descripcion: "Primera versión ..."}

documentos:                      # aba "Doc Evaluados"
  - nombre: "Anejo 27. Estudio Previo Seguridad"   # col A (mesclada no documento)
    firmado: "Si"                                  # col H
    estado: auto                                   # col I  (auto => fórmula; ou "Cerrado")
    categoria: null                                # opcional: agrupa vários docs sob 1 nome em A
    envios:                                        # uma linha por envío (cols B..G)
      - {referencia: "Anejo 27..._v06", version: 6, fecha: 2026-02-03,
         autor: "UTE", envio: 2, fecha_envio: 2026-02-16}

puntos:                          # aba "LPA"
  - n: 1
    eval: "SM"
    documento: "Firmas documentación evaluada"     # col C
    ref_documento: "NA"                            # col D ("auto" => VLOOKUP a Doc Evaluados)
    punto: 'pestaña "Doc Evaluados"'               # col E
    valoracion: "Crítico"                          # col F (Crítico/Importante/Informativo/Formal)
    version: "NA"                                  # col H
    estado: "Cerrado"                              # col K (Abierto/Resuelto/Cerrado)
    dialogo:                                       # cols G (tipo) + I (texto), uma linha cada
      - {tipo: "Hallazgo", texto: "Todos los documentos ..."}
      - {tipo: "Respuesta UTE (02/02/2025)", texto: "El anejo ..."}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

VALORACIONES = ["Crítico", "Importante", "Informativo", "Formal"]
ESTADOS = ["Abierto", "Resuelto", "Cerrado"]


def load(path: str | Path) -> dict[str, Any]:
    """Carrega o ficheiro de projeto (.yaml/.yml/.json) e valida o essencial."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"{p}: o ficheiro de dados deve ter um mapeamento no topo.")
    _validate(data)
    return data


def _validate(data: dict[str, Any]) -> None:
    data.setdefault("portada", {})
    data.setdefault("versiones", [])
    data.setdefault("documentos", [])
    data.setdefault("puntos", [])

    for i, doc in enumerate(data["documentos"]):
        doc.setdefault("envios", [])
        if "nombre" not in doc and not doc.get("categoria"):
            raise ValueError(f"documentos[{i}]: falta 'nombre'.")

    for i, pt in enumerate(data["puntos"]):
        pt.setdefault("dialogo", [])
        val = pt.get("valoracion")
        if val and val not in VALORACIONES:
            raise ValueError(
                f"puntos[{i}] (Nº {pt.get('n')}): valoración '{val}' inválida; "
                f"use uma de {VALORACIONES}."
            )
        est = pt.get("estado")
        if est and est not in ESTADOS:
            raise ValueError(
                f"puntos[{i}] (Nº {pt.get('n')}): estado '{est}' inválido; "
                f"use um de {ESTADOS}."
            )
    return None


def lint(data: dict[str, Any]) -> list[str]:
    """Avisos de boas práticas do guia LPA (PE/Inspección/03). Não bloqueiam."""
    avisos: list[str] = []
    for pt in data.get("puntos", []):
        n = pt.get("n", "?")
        if not pt.get("valoracion"):
            avisos.append(f"Punto {n}: sem 'valoracion' (Crítico/Importante/Informativo/Formal).")
        if not pt.get("punto"):
            avisos.append(f"Punto {n}: 'punto' (requisito normativo) vazio — o guia exige referência à norma.")
        if not pt.get("estado"):
            avisos.append(f"Punto {n}: sem 'estado' (Abierto/Resuelto/Cerrado).")
        dialogo = pt.get("dialogo") or []
        if not dialogo or not (dialogo[0].get("texto") or "").strip():
            avisos.append(f"Punto {n}: sem texto de 'Hallazgo' na primeira linha do diálogo.")
        # Regra de ouro: nenhum Crítico pode ficar Abierto num informe positivo.
        if pt.get("valoracion") == "Crítico" and pt.get("estado") == "Abierto":
            avisos.append(f"Punto {n}: CRÍTICO ainda 'Abierto' — bloqueia um informe positivo (regra de ouro).")
    return avisos


def resumen_counts(data: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Conta puntos por valoración e por estado (para a aba 'Resumen Resultados')."""
    counts = {v: {"total": 0, **{e: 0 for e in ESTADOS}} for v in VALORACIONES}
    for pt in data["puntos"]:
        val = pt.get("valoracion")
        if val not in counts:
            continue
        counts[val]["total"] += 1
        est = pt.get("estado")
        if est in ESTADOS:
            counts[val][est] += 1
    return counts
