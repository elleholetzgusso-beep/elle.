"""Gera as linhas do Control de Versiones a partir dos envíos do projeto.

O texto segue o padrão real dos LPA:

    Quinta versión de LPA que incluye la evaluación de los siguientes envíos
    realizados por parte de UTE ESTEYCO-ARDANUY:
    - Envío 07 (02/06/2026)

O comando ``rev`` deteta os envíos presentes em ``documentos`` que ainda não
foram mencionados nas descrições das versões anteriores e compõe a linha nova.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any

_ORDINAIS = [
    "Primera", "Segunda", "Tercera", "Cuarta", "Quinta", "Sexta",
    "Séptima", "Octava", "Novena", "Décima", "Undécima", "Duodécima",
]

_ENVIO_MENCION = re.compile(r"env[íi]o\s*0*(\d+)", re.IGNORECASE)


def _fmt_fecha(f: Any) -> str:
    if isinstance(f, (dt.date, dt.datetime)):
        return f.strftime("%d/%m/%Y")
    return str(f) if f else "s/f"


def envios_do_projeto(documentos: list[dict]) -> dict[int, Any]:
    """Mapa nº de envío -> fecha_envio (a primeira não-vazia encontrada)."""
    out: dict[int, Any] = {}
    for doc in documentos or []:
        for env in doc.get("envios") or []:
            num = env.get("envio")
            if num is None:
                continue
            num = int(num)
            if num not in out or (out[num] in (None, "") and env.get("fecha_envio")):
                out[num] = env.get("fecha_envio")
    return out


def envios_mencionados(versiones: list[dict]) -> set[int]:
    """Números de envío já referidos nas descrições das versões existentes."""
    vistos: set[int] = set()
    for v in versiones or []:
        for m in _ENVIO_MENCION.finditer(str(v.get("descripcion") or "")):
            vistos.add(int(m.group(1)))
    return vistos


def _ordinal(n: int) -> str:
    return _ORDINAIS[n - 1] if 1 <= n <= len(_ORDINAIS) else f"{n}ª"


def descripcion(rev: int, envios: dict[int, Any], solicitante: str = "") -> str:
    quem = f" realizados por parte de {solicitante}" if solicitante else ""
    linhas = "\n".join(f"- Envío {num:02d} ({_fmt_fecha(envios[num])})" for num in sorted(envios))
    return (
        f"{_ordinal(rev)} versión de LPA que incluye la evaluación de los "
        f"siguientes envíos{quem}:\n{linhas}"
    )


def nueva_revision(
    projeto: dict, solicitante: str = "", fecha: dt.date | None = None
) -> dict | None:
    """Acrescenta a próxima revisão ao projeto (in place) e devolve-a.

    Devolve None se todos os envíos já estiverem mencionados em versões
    anteriores (nada de novo a registar).
    """
    versiones = projeto.setdefault("versiones", [])
    # Descartar placeholders do merge ainda por preencher.
    versiones[:] = [v for v in versiones if "PREENCHER" not in str(v.get("descripcion") or "")]

    todos = envios_do_projeto(projeto.get("documentos", []))
    novos = {n: f for n, f in todos.items() if n not in envios_mencionados(versiones)}
    if not novos:
        return None

    rev = len(versiones) + 1
    entrada = {
        "rev": rev,
        "fecha": fecha or dt.date.today(),
        "descripcion": descripcion(rev, novos, solicitante),
    }
    versiones.append(entrada)
    return entrada
