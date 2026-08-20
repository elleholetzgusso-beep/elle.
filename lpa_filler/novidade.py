"""O que mudou entre o LPA anterior e o projeto atual — para destacar no Excel.

Compara duas árvores de dados (o ``projeto.yaml`` a emitir e o LPA anterior, já
extraído para a mesma forma) e devolve o que é novo: puntos inteiros, linhas de
diálogo dentro de puntos que já existiam, envíos novos em documentos que já
existiam, e revisões novas no Control de versiones.

Sem ``anterior`` (o LPA-01, primeira vez — não há com que comparar), nada é
novo. É a mesma regra em todo o módulo: **novo é sempre relativo a um ficheiro
concreto**, nunca "tudo o que o avaliador escreveu" — isso confundiria conteúdo
carregado de uma revisão anterior (via ``extract``) com conteúdo desta.
"""
from __future__ import annotations

from typing import Any


def vazio() -> dict[str, Any]:
    """A novidade de quem não tem LPA anterior: nada destacado."""
    return {
        "puntos_novos": set(),
        "dialogos_novos": {},
        "documentos_novos": set(),
        "envios_novos": {},
        "versiones_novas": set(),
    }


def _chave_envio(env: dict) -> tuple:
    return (env.get("envio"), env.get("referencia"), env.get("version"))


def _chave_dialogo(d: dict) -> tuple:
    return (str(d.get("tipo") or ""), str(d.get("texto") or ""))


def calcular(data: dict[str, Any], anterior: dict[str, Any] | None) -> dict[str, Any]:
    """A novidade de ``data`` face a ``anterior``. Ver ``vazio()`` para a forma."""
    if not anterior:
        return vazio()

    # --- puntos: por 'id' estável, não por 'n' (que renumera) ---
    ids_antigos = {pt.get("id") for pt in anterior.get("puntos", []) if pt.get("id")}
    puntos_novos = {
        pt["id"] for pt in data.get("puntos", [])
        if pt.get("id") and pt["id"] not in ids_antigos
    }

    # --- diálogo dentro de puntos que já existiam: por (tipo, texto) ---
    dialogo_antigo: dict[str, set[tuple]] = {}
    for pt in anterior.get("puntos", []):
        pid = pt.get("id")
        if pid:
            dialogo_antigo[pid] = {_chave_dialogo(d) for d in (pt.get("dialogo") or [])}

    dialogos_novos: dict[str, set[int]] = {}
    for pt in data.get("puntos", []):
        pid = pt.get("id")
        if not pid or pid in puntos_novos:
            continue  # o punto inteiro já fica marcado — não precisa de granularidade
        vistos = dialogo_antigo.get(pid, set())
        novos = {
            i for i, d in enumerate(pt.get("dialogo") or [])
            if _chave_dialogo(d) not in vistos
        }
        if novos:
            dialogos_novos[pid] = novos

    # --- documentos: por 'nombre' ---
    nomes_antigos = {d.get("nombre") for d in anterior.get("documentos", []) if d.get("nombre")}
    documentos_novos = {
        d["nombre"] for d in data.get("documentos", [])
        if d.get("nombre") and d["nombre"] not in nomes_antigos
    }

    # --- envíos dentro de documentos que já existiam ---
    envios_antigos: dict[str, set[tuple]] = {}
    for d in anterior.get("documentos", []):
        nome = d.get("nombre")
        if nome:
            envios_antigos[nome] = {_chave_envio(e) for e in (d.get("envios") or [])}

    envios_novos: dict[str, set[int]] = {}
    for d in data.get("documentos", []):
        nome = d.get("nombre")
        if not nome or nome in documentos_novos:
            continue
        vistos = envios_antigos.get(nome, set())
        novos = {
            i for i, e in enumerate(d.get("envios") or [])
            if _chave_envio(e) not in vistos
        }
        if novos:
            envios_novos[nome] = novos

    # --- versiones: por 'rev' ---
    revs_antigas = {v.get("rev") for v in anterior.get("versiones", []) if v.get("rev") is not None}
    versiones_novas = {
        v["rev"] for v in data.get("versiones", [])
        if v.get("rev") is not None and v["rev"] not in revs_antigas
    }

    return {
        "puntos_novos": puntos_novos,
        "dialogos_novos": dialogos_novos,
        "documentos_novos": documentos_novos,
        "envios_novos": envios_novos,
        "versiones_novas": versiones_novas,
    }
