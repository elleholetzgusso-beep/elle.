"""Atualiza um projeto existente (de uma revisão anterior) com documentos novos.

Cenário de REVISÃO: já existe um LPA anterior. O fluxo é
``extract`` (recupera puntos + versiones + documentos do LPA anterior) e depois
``update`` para acrescentar os documentos do novo envío — **sem tocar nos
puntos**. É a alternativa ao ``merge``, que serve só para projetos novos (zera
os puntos).

Mescla por nome de documento: se o documento já existe no projeto, acrescenta
apenas os envíos novos (dedup por referência); se é novo, adiciona-o ao fim.
Preserva ``puntos``, ``versiones`` e ``portada`` intactos.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def _norm(s: Any) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


def merge_documentos(projeto: dict[str, Any], novos: list[dict[str, Any]]) -> dict[str, int]:
    """Mescla ``novos`` (documentos do scan) no ``projeto``, in-place.

    Devolve contagens: documentos novos acrescentados e envíos novos anexados a
    documentos já existentes. Não mexe em puntos/versiones/portada.
    """
    docs = projeto.setdefault("documentos", [])
    idx = {_norm(d.get("nombre")): d for d in docs}
    n_docs = n_envios = 0

    for nd in novos:
        key = _norm(nd.get("nombre"))
        existente = idx.get(key)
        if existente is None:
            docs.append(nd)
            idx[key] = nd
            n_docs += 1
            continue
        refs = {_norm(e.get("referencia")) for e in existente.get("envios", [])}
        for e in nd.get("envios", []):
            if _norm(e.get("referencia")) not in refs:
                existente.setdefault("envios", []).append(e)
                refs.add(_norm(e.get("referencia")))
                n_envios += 1

    return {"novos_documentos": n_docs, "novos_envios": n_envios}
