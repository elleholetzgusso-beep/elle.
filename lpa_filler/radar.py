"""Radar dirigido: instrui o avaliador sobre ONDE procurar erros num documento.

A ponte que faltava entre as duas metades da ferramenta:

  * a base do ``harvest`` sabe *onde costuma ter erro* (por tipo de documento e
    por tema RAMS) — mas o ``suggest`` nunca abre os documentos da obra nova;
  * o ``leer`` abre e lê o conteúdo real — mas com um checklist genérico, igual
    para toda obra, sem usar a base.

O ``radar`` liga as duas: para cada documento recebido, lê o texto real, deteta
o tipo, e cruza-o com o que a *sua* base histórica diz que costuma falhar nesse
tipo de documento — emitindo pistas ancoradas no texto (com localização) e no
histórico (com procedência).

FILOSOFIA — igual ao ``leer``: isto é um **radar, não um veredito**. Cada pista
diz "olhe aqui, porque…"; nunca "isto é uma não conformidade" e nunca redige o
hallazgo. A leitura e a decisão são do avaliador (ISO 17020). Tudo é
determinístico e rastreável: cada pista carrega o *porquê* (contagens reais da
base + um exemplo com fonte) e o *onde* (o sinal encontrado no texto).

Nada é inventado: uma sonda só dispara quando (a) o texto real tem o sinal e
(b) a sua base histórica apoia aquele tipo de achado para aquele tipo de
documento. Sem apoio histórico, a sonda cala-se.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import guide, leer, lector, tema

VALORACIONES = ["Crítico", "Importante", "Informativo", "Formal"]
_VAL_ORDER = {v: i for i, v in enumerate(VALORACIONES)}


def _norm(s) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


def load_base(csv_path: str | Path) -> list[dict]:
    """Carrega a base de hallazgos (saída do ``harvest``)."""
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _pior_valoracion(rows: list[dict]) -> str:
    """A valoración mais grave presente num conjunto de hallazgos (para o nível da pista)."""
    presentes = [(_VAL_ORDER.get((r.get("valoracion") or "").strip(), 9), (r.get("valoracion") or "").strip())
                 for r in rows]
    presentes = [p for p in presentes if p[1]]
    return min(presentes)[1] if presentes else "Importante"


def _n_cerrado(rows: list[dict]) -> int:
    return sum(1 for r in rows if _norm(r.get("estado")) == "cerrado")


def _exemplo(rows: list[dict]) -> tuple[str, str]:
    """Um hallazgo ilustrativo (prefere Cerrado) + a sua fonte, para citar o porquê."""
    cerrados = [r for r in rows if _norm(r.get("estado")) == "cerrado"]
    r = (cerrados or rows)[0]
    return (r.get("hallazgo") or "").strip(), (r.get("fuente") or "").strip()


# ---------------------------------------------------------------------------
# Frentes de atenção: o que a base diz que costuma falhar NESTE tipo de documento
# ---------------------------------------------------------------------------

def base_do_tipo(base: list[dict], tipo: str, excluir_obra: str | None = None) -> list[dict]:
    """Subconjunto da base cujo documento é do ``tipo`` dado (via ``guide``).

    ``excluir_obra``: código de obra a remover da base (ex. "EXC2026-16883"),
    para que, ao correr o radar numa obra JÁ presente na base, ele não "cole da
    resposta" — instrui a partir das *outras* obras, não da própria.
    """
    alvo = _norm(excluir_obra) if excluir_obra else None
    out = []
    for r in base:
        if guide.tipo_documento(r.get("documento", "")) != tipo:
            continue
        if alvo and alvo in _norm(r.get("obra")):
            continue
        out.append(r)
    return out


def frentes_por_tema(rows_tipo: list[dict]) -> list[dict]:
    """Agrupa os hallazgos de um tipo por tema RAMS, ordenados por gravidade.

    Cada frente: tema, contagem por valoración, nº de obras, nº Cerrados e um
    exemplo real (com fonte). É o "onde costuma ter erros graves" deste tipo de
    documento, direto da base — sem abrir o documento novo ainda.
    """
    acc: dict[str, list[dict]] = {}
    for r in rows_tipo:
        temas = [t.strip() for t in (r.get("tema") or "").split(",") if t.strip()]
        for t in (temas or ["(sem tema)"]):
            acc.setdefault(t, []).append(r)
    frentes = []
    for t, rows in acc.items():
        criticos = sum(1 for r in rows if (r.get("valoracion") or "").strip() == "Crítico")
        obras = len({(r.get("obra") or "").strip() for r in rows if (r.get("obra") or "").strip()})
        ex_txt, ex_fonte = _exemplo(rows)
        frentes.append({
            "tema": t, "total": len(rows), "criticos": criticos, "obras": obras,
            "cerrados": _n_cerrado(rows), "exemplo": ex_txt, "fonte": ex_fonte,
        })
    frentes.sort(key=lambda x: (-x["criticos"], -x["total"]))
    return frentes


# ---------------------------------------------------------------------------
# Sondas: sinais concretos no texto real, apoiados pela base
# ---------------------------------------------------------------------------

@dataclass
class Contexto:
    """Tudo o que uma sonda precisa: o texto real (bruto+normalizado) e a fatia
    da base correspondente ao tipo deste documento (para declarar o seu apoio)."""
    raw: str
    norm: str
    tipo: str
    base_tipo: list[dict]


@dataclass
class Pista:
    nivel: str          # valoración sugerida pela base (Crítico/Importante/...)
    titulo: str         # o que olhar
    porque: str         # apoio histórico (contagens reais + exemplo com fonte)
    no_texto: str       # o sinal determinístico encontrado no texto real
    onde: str           # onde no documento ir ver


# Registo: (id, regex sobre o rótulo do tipo, função). Uma sonda com tipo=".*"
# aplica-se a todos os documentos.
_SONDAS: list[tuple[str, str, Callable[[Contexto], Pista | None]]] = []


def sonda(id: str, tipos: str = r".*"):
    def deco(fn):
        _SONDAS.append((id, tipos, fn))
        return fn
    return deco


def _apoio(ctx: Contexto, termos: list[str]) -> list[dict]:
    """Hallazgos da base (deste tipo) cujo texto menciona algum dos ``termos``.

    É o apoio histórico da sonda: prova de que aquele tipo de achado já foi
    levantado para este tipo de documento. Sem apoio, a sonda não dispara."""
    out = []
    for r in ctx.base_tipo:
        txt = _norm(" ".join(str(r.get(k) or "") for k in ("hallazgo", "discusion", "punto")))
        if any(t in txt for t in termos):
            out.append(r)
    return out


def _frase_porque(apoio: list[dict], tipo: str) -> str:
    obras = len({(r.get("obra") or "").strip() for r in apoio if (r.get("obra") or "").strip()})
    ex_txt, ex_fonte = _exemplo(apoio)
    ex = (ex_txt[:130] + "…") if len(ex_txt) > 130 else ex_txt
    return (f"{len(apoio)} achado(s) em {tipo} na sua base ({_n_cerrado(apoio)} Cerrado, "
            f"{obras} obra(s)). Ex.: \"{ex}\" (fonte: {ex_fonte or '?'})")


@sonda("anexos_cruzados", r".*")
def _anexos_cruzados(ctx: Contexto) -> Pista | None:
    """Mesmo nº de anexo citado com nomes diferentes = referência cruzada trocada.

    Reproduz um erro Crítico real e recorrente da base ("como evidencia aparece
    Anejo 5. Estructuras, sin embargo el Anejo 5 es de Climatología"). Totalmente
    determinístico e verificável — não depende da base para disparar, mas cita-a
    como apoio quando existe."""
    # "Anejo/Anexo N. Nome" (o nome vai até vírgula/ponto-e-vírgula/fim de linha).
    pares = re.findall(r"\bane[jx]o\s+(\d{1,3})[.\-:\s]+([A-Za-zÁÉÍÓÚÑáéíóúñ][^,.;\n]{2,45})",
                       ctx.raw, re.IGNORECASE)
    porn: dict[str, set[str]] = {}
    for num, nome in pares:
        porn.setdefault(num, set()).add(_norm(nome))
    conflitos = {n: nomes for n, nomes in porn.items() if len(nomes) > 1}
    if not conflitos:
        return None
    n = sorted(conflitos)[0]
    nomes = " | ".join(sorted(conflitos[n]))
    apoio = _apoio(ctx, ["anejo", "anexo"])
    porque = ("inconsistência lógica no próprio texto (o mesmo anexo com dois nomes) — "
              "confirmar contra a lista de anexos do envío.")
    if apoio:
        obras = len({(r.get("obra") or "").strip() for r in apoio if (r.get("obra") or "").strip()})
        porque += (f" Referências a anexos são zona de erro recorrente: {len(apoio)} achado(s) "
                   f"em {ctx.tipo} na sua base ({_n_cerrado(apoio)} Cerrado, {obras} obra(s)).")
    return Pista(
        nivel=_pior_valoracion(apoio) if apoio else "Importante",
        titulo=f"Referência ao Anexo {n} inconsistente (nomes diferentes para o mesmo anexo)",
        porque=porque,
        no_texto=f"o «Anejo {n}» aparece no texto com nomes distintos: {nomes}",
        onde=f"cada citação de «Anejo {n}» (coluna de evidências) e a lista de anexos",
    )


@sonda("evidencias", r"REP|F3|Hazard")
def _evidencias(ctx: Contexto) -> Pista | None:
    """REP sem menção a 'evidencia' — padrão Crítico recorrente na base."""
    if "evidencia" in ctx.norm:
        return None
    apoio = _apoio(ctx, ["evidencia"])
    if not apoio:
        return None
    return Pista(
        nivel=_pior_valoracion(apoio),
        titulo="Coluna/apartado de «Evidencias» pode estar ausente",
        porque=_frase_porque(apoio, ctx.tipo),
        no_texto="o termo «evidencia» não aparece no texto extraído",
        onde="colunas da tabela de perigos (Evidencia por perigo/medida)",
    )


@sonda("estado_riesgo", r"REP|F3|Hazard")
def _estado_riesgo(ctx: Contexto) -> Pista | None:
    """REP que lista perigos mas não mostra o estado do risco de cada um."""
    if "peligro" not in ctx.norm and "hazard" not in ctx.norm:
        return None
    if any(e in ctx.norm for e in ("abierto", "cerrado", "controlado", "estado del riesgo", "estado del peligro")):
        return None
    apoio = _apoio(ctx, ["estado del riesgo", "estado del peligro", "sin estado", "estado del hazard"])
    if not apoio:
        return None
    return Pista(
        nivel=_pior_valoracion(apoio),
        titulo="Perigos sem estado do risco visível",
        porque=_frase_porque(apoio, ctx.tipo),
        no_texto="o texto menciona «peligro» mas não os estados (abierto/cerrado/controlado)",
        onde="coluna de estado/situación de cada perigo",
    )


@sonda("id_requisitos", r"REP|F3|Hazard")
def _id_requisitos(ctx: Contexto) -> Pista | None:
    """REP sem identificador por perigo/requisito de segurança."""
    if "peligro" not in ctx.norm and "requisito" not in ctx.norm:
        return None
    # Sinais de que há IDs: "ID 3", "ID-333", "id:" próximo do texto.
    if re.search(r"\bid[\s:\-]?\d", ctx.norm):
        return None
    apoio = _apoio(ctx, ["un id", "identificador", "codigo unico", "sin id", "id para cada", "id unico"])
    if not apoio:
        return None
    return Pista(
        nivel=_pior_valoracion(apoio),
        titulo="Perigos/requisitos sem ID único",
        porque=_frase_porque(apoio, ctx.tipo),
        no_texto="não se detetou um padrão de identificador (ID) por perigo/requisito",
        onde="coluna de ID/código do perigo ou do requisito de seguridad",
    )


def rodar_sondas(ctx: Contexto) -> list[Pista]:
    pistas = []
    for _id, tipos, fn in _SONDAS:
        if re.search(tipos, ctx.tipo, re.IGNORECASE):
            p = fn(ctx)
            if p is not None:
                pistas.append(p)
    pistas.sort(key=lambda p: _VAL_ORDER.get(p.nivel, 9))
    return pistas


# ---------------------------------------------------------------------------
# Análise de um documento / de uma pasta
# ---------------------------------------------------------------------------

def analisar_documento(path: str | Path, base: list[dict], excluir_obra: str | None = None) -> dict:
    p = Path(path)
    raw = lector.extract_text(p)
    tipo = guide.tipo_documento(p.stem)
    reg: dict = {
        "ficheiro": p.name, "tipo": tipo, "caracteres": len(raw),
        "frentes": [], "pistas": [], "estrutura": [], "normas": [], "notas": [],
    }
    if not raw:
        reg["notas"].append(f"sem texto — {lector.motivo_vazio(p)}")
        return reg

    norm = _norm(raw)
    rows_tipo = base_do_tipo(base, tipo, excluir_obra=excluir_obra)
    reg["frentes"] = frentes_por_tema(rows_tipo)[:5]

    ctx = Contexto(raw=raw, norm=norm, tipo=tipo, base_tipo=rows_tipo)
    reg["pistas"] = rodar_sondas(ctx)

    # Estrutura esperada (reusa o checklist do leer) + normas CENELEC citadas.
    partes = leer._checklist_para(p.stem)
    if partes:
        for rotulo, chaves in partes:
            reg["estrutura"].append((rotulo, any(_norm(c) in norm for c in chaves)))
    reg["normas"] = [nome for nome, rx in leer._NORMAS.items() if re.search(rx, norm)]
    reg["temas_no_texto"] = tema.classify(raw)
    return reg


def analisar_pasta(recibida_dir: str | Path, base: list[dict],
                   excluir_obra: str | None = None, on_file=None) -> list[dict]:
    from . import verify  # reutiliza a busca de ficheiros legíveis

    ficheiros = verify.ficheiros_legiveis(recibida_dir)
    registos = []
    for i, p in enumerate(ficheiros, 1):
        if on_file:
            on_file(i, len(ficheiros), p)
        registos.append(analisar_documento(p, base, excluir_obra=excluir_obra))
    return registos


# ---------------------------------------------------------------------------
# Relatório (o que o avaliador lê)
# ---------------------------------------------------------------------------

_SIMBOLO = {"Crítico": "‼", "Importante": "►", "Informativo": "·", "Formal": "·"}


def relatorio(registos: list[dict]) -> str:
    L: list[str] = [
        f"# RADAR DIRIGIDO — {len(registos)} documento(s)",
        "# Cada pista diz ONDE olhar e POR QUÊ. Não é veredito: a decisão é do avaliador.",
        "",
    ]
    for r in registos:
        L.append("═" * 70)
        L.append(f" {r['ficheiro']}   [tipo: {r['tipo']}]  ·  {r['caracteres']} caracteres")
        L.append("═" * 70)
        for nota in r["notas"]:
            L.append(f"  ! {nota}")
        if r["notas"] and not r.get("frentes"):
            L.append("")
            continue

        if r["frentes"]:
            L.append("")
            L.append(" ONDE ESTE TIPO DE DOCUMENTO COSTUMA FALHAR (da sua base)")
            for f in r["frentes"]:
                L.append(f"   • {f['tema']}: {f['criticos']} Críticos / {f['total']} achados, "
                         f"{f['obras']} obra(s), {f['cerrados']} Cerrados")

        if r["pistas"]:
            L.append("")
            L.append(" PISTAS NO TEXTO REAL DESTE DOCUMENTO")
            for p in r["pistas"]:
                L.append(f"   {_SIMBOLO.get(p.nivel, '►')} OLHAR [{p.nivel}] — {p.titulo}")
                L.append(f"       porquê: {p.porque}")
                L.append(f"       no texto: {p.no_texto}")
                L.append(f"       onde: {p.onde}")
        elif r["frentes"]:
            L.append("")
            L.append("   (nenhuma sonda determinística disparou no texto — rever à mão"
                     " as frentes acima)")

        if r["estrutura"]:
            L.append("")
            L.append(" ESTRUTURA ESPERADA (✓ presente / ✗ olhar)")
            for rotulo, ok in r["estrutura"]:
                L.append(f"   {'✓' if ok else '✗'} {rotulo}")
        if r["normas"]:
            L.append(f"   normas CENELEC citadas: {', '.join(r['normas'])}")
        L.append("")
    return "\n".join(L)
