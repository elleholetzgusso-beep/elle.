"""Rascunho determinístico da réplica do avaliador (Respuesta Exceltic).

Para cada punto ainda aberto que já tenha uma resposta do contratista, o ``draft``
localiza nos documentos do novo envío o apartado que a resposta cita, extrai o
trecho real e o diff entre versões (reutiliza o ``verify``), e escreve um
RASCUNHO da Respuesta Exceltic com essa evidência.

Fronteira de segurança (ISO 17020) — é um SCAFFOLD, não um parecer:
  - o texto é factual ("localizei o apartado X, diz Y; mudaram N linhas"), nunca
    um juízo de conformidade ("cumpre / dá-se por fechado");
  - termina sempre em "pendiente de verificación y cierre por el evaluador";
  - **não altera o estado** do punto (não fecha nada);
  - marca o texto com um prefixo inconfundível e o punto com ``_rascunho: true``.
O avaliador revê, reescreve o parecer e decide o estado. O fill avisa se algum
rascunho ficou por rever.
"""
from __future__ import annotations

from typing import Any

from . import verify

# Entra no diálogo, e o diálogo entra no .xlsm entregue ao cliente: tem de ser
# legível por quem o recebe. O model reconhece também o "[RASCUNHO" antigo,
# para não invalidar projetos a meio.
MARCA = "[BORRADOR — revisar y confirmar]"


def _texto_scaffold(reg: dict[str, Any]) -> str:
    """Compõe a evidência localizada num rascunho factual (sem julgar)."""
    if not reg["ficheiro"]:
        return (
            f"{MARCA} No se localiza el documento «{reg['documento']}» en el envío. "
            f"Revisar manualmente."
        )
    partes: list[str] = []
    achados_ok = [a for a in reg["achados"] if a["trecho"]]
    achados_no = [a for a in reg["achados"] if not a["trecho"]]
    for a in achados_ok:
        trecho = " ".join(a["trecho"].split())
        if len(trecho) > 300:
            trecho = trecho[:300] + "…"
        partes.append(f"Se localiza el apartado {a['ref']} en «{reg['ficheiro']}»: «{trecho}».")
    for a in achados_no:
        partes.append(
            f"La respuesta cita el apartado {a['ref']} pero no se localiza en «{reg['ficheiro']}»."
        )
    if reg["mudancas"]:
        partes.append(f"Se detectan {len(reg['mudancas'])} líneas modificadas respecto a la versión anterior.")
    if not reg["refs"]:
        partes.append(f"La respuesta no cita apartado concreto; abrir «{reg['ficheiro']}» para verificar.")
    corpo = " ".join(partes) if partes else f"Documento «{reg['ficheiro']}» localizado; verificar contenido."
    return f"{MARCA} {corpo} Pendiente de verificación y cierre por el evaluador."


def _slot_exceltic(dialogo: list[dict]) -> dict:
    """Devolve a primeira 'Respuesta Exceltic' vazia do diálogo (a réplica do
    avaliador), ou cria e anexa uma se não existir."""
    for d in dialogo:
        if "exceltic" in (d.get("tipo") or "").lower() and not (d.get("texto") or "").strip():
            return d
    novo = {"tipo": "Respuesta Exceltic (dd/mm/aaaa)", "texto": ""}
    dialogo.append(novo)
    return novo


def elaborar(projeto: dict[str, Any], recibida_dir, on_punto=None) -> dict[str, Any]:
    """Preenche, in-place, um rascunho de Respuesta Exceltic para cada punto
    aberto que tenha resposta do contratista. Não altera estados.

    Devolve: rascunhos (nº preenchidos), sem_resposta (puntos abertos sem
    resposta do contratista), registos (os do verify, para o relatório).
    """
    registos = verify.verificar(projeto, recibida_dir, on_punto=on_punto)
    reg_por_n = {r["n"]: r for r in registos}
    n_rascunho = 0
    n_sem_resp = 0

    for pt in projeto.get("puntos", []):
        if (pt.get("estado") or "Abierto") == "Cerrado":
            continue
        reg = reg_por_n.get(pt.get("n"))
        if not reg or not reg["respuesta"]:
            n_sem_resp += 1
            continue
        slot = _slot_exceltic(pt.setdefault("dialogo", []))
        slot["texto"] = _texto_scaffold(reg)
        pt["_rascunho"] = True
        n_rascunho += 1

    return {"rascunhos": n_rascunho, "sem_resposta": n_sem_resp, "registos": registos}
