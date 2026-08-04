"""Gera a estrutura do Anejo A.2 — Base de Datos de No Conformidades y Acciones
(Mudança 6 — base PE/05, requisito do sistema de gestão ISO/IEC 17020).

O PE/05 exige um registo de não conformidades com estas colunas:

    Nº | Aspecto detectado | Fecha detección | Acción a implantar |
    Responsable | Resultado verificación | Fecha cierre

Este módulo deriva essas colunas dos ``puntos`` já existentes no projeto, sem
inventar dados: o que não é derivável fica como ``(a preencher)`` (nunca um valor
fabricado, porque isto é um registo de compliance auditável). As datas e o
responsável saem dos ``tipo`` do diálogo, que seguem o padrão real
"Respuesta <PARTE> (dd/mm/aaaa)".

O resultado da verificação mapeia o estado PE/03:
    Cerrado  -> "Verificada y cerrada"      (ação executada e comprovada)
    Resuelto -> "Aceptada, pendiente de evidencia"
    Abierto  -> "Pendiente"
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

# A coluna "Nº" do PE/05 é a chave do registo, por isso é o ``id`` estável que a
# ocupa: uma Base de No Conformidades tem de referir a mesma não conformidade da
# mesma maneira em todas as revisões. O ``n`` fica ao lado como referência cruzada
# para a folha do LPA, onde é por ele que o punto aparece — mas renumera-se, por
# isso não serve de chave.
CAMPOS = [
    "id", "n", "aspecto_detectado", "fecha_deteccion", "accion_a_implantar",
    "responsable", "resultado_verificacion", "fecha_cierre",
]

A_PREENCHER = "(a preencher)"

_RESULTADO = {
    "Cerrado": "Verificada y cerrada",
    "Resuelto": "Aceptada, pendiente de evidencia",
    "Abierto": "Pendiente",
}

# "Respuesta ENYSE (03/06/2026)" -> parte="ENYSE", fecha="03/06/2026".
_TIPO_RE = re.compile(r"^\s*respuesta\s+(.+?)\s*\((\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\)", re.IGNORECASE)
# Data isolada num tipo/hallazgo sem "Respuesta".
_FECHA_RE = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})")


def _partes_e_fechas(dialogo: list[dict]) -> tuple[list[str], list[str], str | None, str | None]:
    """Percorre o diálogo e devolve (respostas, responsaveis, primeira_fecha, ultima_fecha)."""
    respostas: list[str] = []
    responsaveis: list[str] = []
    fechas: list[str] = []
    for d in dialogo or []:
        tipo = (d.get("tipo") or "").strip()
        texto = (d.get("texto") or "").strip()
        m = _TIPO_RE.match(tipo)
        if m:
            parte, fecha = m.group(1).strip(), m.group(2)
            if "dd/mm" not in fecha.lower():  # ignora o placeholder "(dd/mm/aaaa)"
                fechas.append(fecha)
            if texto:
                respostas.append(texto)
            responsaveis.append(parte)
        else:
            fm = _FECHA_RE.search(tipo)
            if fm and "dd/mm" not in tipo.lower():
                fechas.append(fm.group(1))
    primeira = fechas[0] if fechas else None
    ultima = fechas[-1] if fechas else None
    return respostas, responsaveis, primeira, ultima


def punto_to_anejo(pt: dict) -> dict[str, Any]:
    dialogo = pt.get("dialogo") or []
    hallazgo = (dialogo[0].get("texto") if dialogo else "") or ""
    respostas, responsaveis, primeira_fecha, ultima_fecha = _partes_e_fechas(dialogo)
    estado = pt.get("estado") or "Abierto"
    cerrado = estado == "Cerrado"
    return {
        "id": pt.get("id") or A_PREENCHER,
        "n": pt.get("n"),
        "aspecto_detectado": hallazgo.strip() or A_PREENCHER,
        # Fecha de detección: não há campo próprio; o hallazgo raramente traz data.
        "fecha_deteccion": A_PREENCHER,
        "accion_a_implantar": (respostas[0] if respostas else A_PREENCHER),
        # Responsable da ação = a parte que respondeu (solicitante), não o avaliador.
        "responsable": (responsaveis[0] if responsaveis else A_PREENCHER),
        "resultado_verificacion": _RESULTADO.get(estado, estado),
        # Só há fecha de cierre real se o ponto está fechado.
        "fecha_cierre": (ultima_fecha if cerrado and ultima_fecha else (A_PREENCHER if cerrado else "")),
    }


class IdDesconhecido(ValueError):
    """Pediu-se ao filtro um ID que não existe no projeto."""


def build(data: dict[str, Any], solo: list[str] | None = None) -> list[dict[str, Any]]:
    """Gera as linhas do Anejo A.2 a partir dos puntos do projeto.

    ``solo``: se indicado, restringe aos puntos com esses IDs estáveis (ex. os
    novos ou alterados nesta revisão). Aceita as formas que o ``normalize_id``
    reconhece — ``H-007``, ``h-7``, ``7``. Sem isto, gera todos.

    Um ID pedido que não exista é erro, não uma linha em falta: num registo de
    não conformidades, um Anejo incompleto por engano de escrita é pior do que
    um comando que se recusa a correr.
    """
    from . import model

    filtro: set[str] | None = None
    if solo is not None:
        filtro = set()
        maus = []
        for v in solo:
            norm = model.normalize_id(v)
            (filtro.add(norm) if norm else maus.append(str(v)))
        if maus:
            raise IdDesconhecido(f"IDs ilegíveis: {', '.join(maus)} (esperado H-001, 1, …)")

    linhas = []
    vistos: set[str] = set()
    for pt in data.get("puntos", []):
        pid = model.normalize_id(pt.get("id") or "")
        if filtro is not None:
            if pid not in filtro:
                continue
            vistos.add(pid)
        linhas.append(punto_to_anejo(pt))

    if filtro is not None and (ausentes := sorted(filtro - vistos)):
        raise IdDesconhecido(
            f"IDs não encontrados no projeto: {', '.join(ausentes)}. "
            f"O Anejo não foi gerado — verifica os IDs pedidos."
        )
    return linhas


def to_csv(linhas: list[dict[str, Any]], out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for linha in linhas:
            w.writerow(linha)
    return out
