"""Verificação do ciclo de resposta: a UTE respondeu — o que mandou cumpre?

Para cada punto ainda ABERTO (não Cerrado), o ``verify``:

  1. lê a última *Respuesta* do diálogo e os apartados/páginas que ela cita;
  2. localiza o ficheiro do documento na pasta de resposta (a versão mais nova);
  3. abre o ficheiro e extrai o trecho real de cada apartado citado;
  4. se houver duas versões, resume o que MUDOU entre elas;
  5. sinaliza o que não encontrou (apartado inexistente, ficheiro em falta).

O resultado é **evidência para o avaliador decidir** — nunca um veredito. O
``verify`` não fecha hallazgos nem altera estados: só traz o conteúdo dos
ficheiros à superfície, lado a lado com o que a resposta alega (ISO 17020).
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from . import lector

_STOP = set("de la el en y a los las del al lo un una para".split())


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")
    return s.lower()


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", _norm(s)) if len(w) > 2 and w not in _STOP}


# Marcador de versão no fim do nome (reaproveita a ideia do scan): "_v06", " v8".
_VERSION_RE = re.compile(r"[\s_\-]+v\.?\s*(\d+(?:\.\d+)?)\s*$", re.IGNORECASE)


def _version_de(stem: str) -> float:
    m = _VERSION_RE.search(stem)
    return float(m.group(1)) if m else -1.0


def ficheiros_legiveis(recibida_dir: str | Path) -> list[Path]:
    """Todos os ficheiros de tipo legível na pasta (recursivo), ignora temporários."""
    root = Path(recibida_dir)
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in lector.LEGIVEIS
        and not p.name.startswith(("~$", "."))
    )


def _versoes_do_documento(documento: str, ficheiros: list[Path], min_hits: int = 2) -> list[Path]:
    """Ficheiros que correspondem ao nome do documento, ordenados por versão.

    Casamento por sobreposição de tokens do nome (>= ``min_hits`` em comum).
    Ordena da versão mais antiga para a mais nova (a última é a atual).
    """
    q = _tokens(documento)
    if not q:
        return []
    casados = [(p, len(q & _tokens(p.stem))) for p in ficheiros]
    casados = [(p, h) for p, h in casados if h >= min_hits]
    # Ordena por versão (a marca _vNN); empate desfaz-se pelo nome.
    casados.sort(key=lambda ph: (_version_de(ph[0].stem), ph[0].name))
    return [p for p, _ in casados]


def _ultima_respuesta(dialogo: list[dict]) -> dict | None:
    """Última entrada do diálogo que seja uma resposta (não o Hallazgo inicial)."""
    for d in reversed(dialogo or []):
        tipo = _norm(d.get("tipo") or "")
        if tipo.startswith("respuesta") or tipo.startswith("contest") or "respost" in tipo:
            return d
    return None


def verificar(projeto: dict[str, Any], recibida_dir: str | Path) -> list[dict[str, Any]]:
    """Devolve um registo de verificação por cada punto ainda aberto.

    Cada registo: n, documento, valoracion, estado, respuesta, refs (apartados
    citados), ficheiro (o usado), achados [{ref, trecho|None}], mudancas
    (diff resumido entre as duas últimas versões) e notas (o que falhou).
    """
    ficheiros = ficheiros_legiveis(recibida_dir)
    registos: list[dict[str, Any]] = []

    for pt in projeto.get("puntos", []):
        if (pt.get("estado") or "Abierto") == "Cerrado":
            continue  # já fechado — não precisa de verificação
        dialogo = pt.get("dialogo") or []
        resp = _ultima_respuesta(dialogo)
        reg: dict[str, Any] = {
            "n": pt.get("n"),
            "documento": pt.get("documento") or "",
            "valoracion": pt.get("valoracion") or "",
            "estado": pt.get("estado") or "Abierto",
            "respuesta": (resp.get("texto") or "").strip() if resp else "",
            "refs": [],
            "ficheiro": None,
            "achados": [],
            "mudancas": [],
            "notas": [],
        }

        if not resp:
            reg["notas"].append("sem resposta da UTE no diálogo — nada a verificar ainda")
            registos.append(reg)
            continue

        reg["refs"] = lector.referencias_citadas(reg["respuesta"])
        versoes = _versoes_do_documento(reg["documento"], ficheiros)
        if not versoes:
            reg["notas"].append(
                f"não encontrei o ficheiro de '{reg['documento']}' na pasta de resposta"
            )
            registos.append(reg)
            continue

        atual = versoes[-1]
        reg["ficheiro"] = atual.name
        texto = lector.extract_text(atual)
        if not texto:
            reg["notas"].append(f"ficheiro ilegível: {lector.motivo_vazio(atual)}")
            registos.append(reg)
            continue

        # Trecho real de cada apartado citado na resposta.
        for ref in reg["refs"]:
            trecho = lector.localizar_seccion(texto, ref)
            reg["achados"].append({"ref": ref, "trecho": trecho})
            if trecho is None:
                reg["notas"].append(f"a resposta cita '{ref}' mas não o encontrei no ficheiro")
        if not reg["refs"]:
            reg["notas"].append(
                "a resposta não cita apartado/página — abrir o ficheiro à mão para conferir"
            )

        # O que mudou entre as duas últimas versões (evidência direta de alteração).
        if len(versoes) >= 2:
            texto_ant = lector.extract_text(versoes[-2])
            if texto_ant:
                reg["mudancas"] = lector.diff_versoes(texto_ant, texto)

        registos.append(reg)

    return registos


def relatorio(registos: list[dict[str, Any]], max_diff: int = 8) -> str:
    """Formata os registos num relatório de texto legível para o avaliador."""
    linhas: list[str] = []
    abertos = len(registos)
    com_ficheiro = sum(1 for r in registos if r["ficheiro"])
    linhas.append(f"# Verificação de {abertos} puntos abertos "
                  f"({com_ficheiro} com ficheiro localizado)")
    linhas.append("# O programa traz a evidência; a decisão de fechar é do avaliador.\n")

    for r in registos:
        linhas.append(f"── Punto {r['n']} [{r['valoracion']}/{r['estado']}] — {r['documento']}")
        if r["respuesta"]:
            resp = r["respuesta"]
            linhas.append(f"   Resposta UTE: {resp[:200]}{'…' if len(resp) > 200 else ''}")
        if r["ficheiro"]:
            linhas.append(f"   Ficheiro: {r['ficheiro']}")
        for a in r["achados"]:
            if a["trecho"]:
                trecho = " ".join(a["trecho"].split())
                linhas.append(f"   ✓ apartado {a['ref']}: {trecho[:220]}{'…' if len(trecho) > 220 else ''}")
            else:
                linhas.append(f"   ✗ apartado {a['ref']}: NÃO encontrado no ficheiro")
        if r["mudancas"]:
            linhas.append(f"   Δ mudou entre versões ({len(r['mudancas'])} linhas):")
            for m in r["mudancas"][:max_diff]:
                linhas.append(f"      {m[:150]}")
            if len(r["mudancas"]) > max_diff:
                linhas.append(f"      … (+{len(r['mudancas']) - max_diff} linhas)")
        for nota in r["notas"]:
            linhas.append(f"   ! {nota}")
        linhas.append("")
    return "\n".join(linhas)
