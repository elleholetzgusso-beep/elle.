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
import re
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


# ---------------------------------------------------------------------------
# ID estável do hallazgo (rastreabilidade entre revisões — PE/03, ISO 17020)
# ---------------------------------------------------------------------------
#
# O 'n' é o número de APRESENTAÇÃO: renumera-se 1..N sempre que se insere ou
# descarta um punto, por isso não identifica nada ao longo do tempo. O 'id' é
# atribuído uma vez e nunca muda: é ele que liga o mesmo hallazgo entre a
# revisão 01 e a 05 do LPA, e o que se cita numa auditoria.
#
# Prefixo textual de propósito: em YAML, um "001" sem aspas seria lido como o
# inteiro 1 e perdia-se o zero à esquerda.
ID_PREFIXO = "H-"
_ID_RE = re.compile(rf"^{re.escape(ID_PREFIXO)}(\d+)$")


def _id_num(pt: dict[str, Any]) -> int | None:
    m = _ID_RE.match(str(pt.get("id") or "").strip())
    return int(m.group(1)) if m else None


def assign_ids(data: dict[str, Any]) -> list[str]:
    """Atribui um ``id`` estável a cada punto que ainda não tenha um.

    Nunca reatribui nem reutiliza: o próximo ID é sempre ``max(existentes) + 1``,
    mesmo que puntos anteriores tenham sido descartados. Apagar o punto H-007 não
    faz o seguinte passar a H-007 — o número fica queimado, como num registo de
    não conformidades auditável.

    Devolve a lista de IDs novos (para o comando os poder reportar).
    """
    puntos = data.get("puntos") or []
    proximo = max((_id_num(pt) or 0 for pt in puntos), default=0) + 1
    novos: list[str] = []
    for pt in puntos:
        if _id_num(pt) is not None:
            continue
        novo = f"{ID_PREFIXO}{proximo:03d}"
        # À cabeça do punto no YAML: é a chave de identidade, lê-se primeiro.
        resto = dict(pt)
        pt.clear()
        pt["id"] = novo
        pt.update(resto)
        novos.append(novo)
        proximo += 1
    return novos


def normalize_id(valor: Any) -> str | None:
    """Aceita ``H-001``, ``h-1``, ``001`` ou ``1`` e devolve a forma canónica.

    Serve as linhas de comando, onde escrever o prefixo e os zeros à mão é ruído.
    Devolve ``None`` se não for reconhecível como ID — quem chama decide se isso
    é erro (num registo de compliance, é).
    """
    txt = str(valor).strip()
    m = _ID_RE.match(txt) or re.match(r"^(\d+)$", txt)
    if not m:
        m = re.match(rf"^{re.escape(ID_PREFIXO)}(\d+)$", txt, re.IGNORECASE)
    return f"{ID_PREFIXO}{int(m.group(1)):03d}" if m else None


def _etiqueta(pt: dict[str, Any]) -> str:
    """Como referir um punto numa mensagem: pelo ID estável, com o nº visível."""
    pid = str(pt.get("id") or "").strip()
    n = pt.get("n", "?")
    return f"{pid} (Nº {n})" if pid else f"Punto {n}"


PLACEHOLDERS = ("DESCREVER O HALLAZGO", "PREENCHER")


def drop_placeholders(data: dict[str, Any]) -> list[str]:
    """Remove puntos-placeholder (texto de exemplo por preencher) antes do fill.

    Devolve avisos sobre o que foi removido e sobre campos da portada ainda
    com 'PREENCHER' (esses não são removidos — têm de ser preenchidos).
    """
    avisos: list[str] = []
    mantidos = []
    for pt in data.get("puntos", []):
        texto = ((pt.get("dialogo") or [{}])[0].get("texto") or "").upper()
        if any(ph in texto for ph in PLACEHOLDERS):
            avisos.append(
                f"{_etiqueta(pt)} descartado: texto-modelo por preencher "
                f"(placeholder) — não entra no Excel."
            )
            continue
        mantidos.append(pt)
    data["puntos"] = mantidos
    for campo in ("titulo", "referencia"):
        valor = str(data.get("portada", {}).get(campo) or "")
        if "PREENCHER" in valor.upper():
            avisos.append(f"Portada.{campo} ainda com 'PREENCHER' — corrige antes de emitir.")
    return avisos


def drop_fora_de_escopo(data: dict[str, Any]) -> list[str]:
    """Remove puntos marcados ``_fora_escopo`` (provável contaminação de outra
    obra, detetada pelo ``suggest --scope``) antes do fill.

    Segurança por omissão: um punto marcado só entra no Excel se o utilizador
    o rever e apagar manualmente a chave ``_fora_escopo`` desse punto no YAML
    (confirmando que é um falso positivo). Renumera os puntos mantidos.
    """
    avisos: list[str] = []
    mantidos = []
    for pt in data.get("puntos", []):
        if pt.get("_fora_escopo"):
            marc = pt.get("_marcadores", "")
            avisos.append(
                f"{_etiqueta(pt)} descartado: marcado _fora_escopo ({marc}) — "
                f"provável hallazgo de outra obra. Para manter, apaga a chave "
                f"'_fora_escopo' deste punto no YAML e corre o fill de novo."
            )
            continue
        mantidos.append(pt)
    for i, pt in enumerate(mantidos, 1):
        pt["n"] = i
    data["puntos"] = mantidos
    return avisos


# ---------------------------------------------------------------------------
# Transições de estado (PE/Inspección/03 §8.4)
# ---------------------------------------------------------------------------
#
# O estado não é uma etiqueta livre: cada degrau exige que exista no diálogo a
# prova que o justifica.
#
#   Abierto   — comunicado ao cliente. Basta o Hallazgo.
#   Resuelto  — o cliente respondeu E o avaliador aceitou a ação proposta.
#   Cerrado   — além do acima, a execução está comprovada por evidência citada.
#
# A verificação é sobre a PRESENÇA da prova, não sobre o seu mérito: dizer se a
# evidência é suficiente continua a ser juízo do avaliador (ISO 17020). O que
# aqui se impede é o caso oposto — um punto marcado Cerrado sem que exista no
# registo nada que sustente o fecho.

# "Respuesta UTE (02/02/2025)", "Respuesta ENYSE (03/06/2026)" — a parte que
# responde é o cliente; a réplica da Exceltic é a aceitação do avaliador.
_RESPUESTA_RE = re.compile(r"^\s*respuesta\b", re.IGNORECASE)


def _linhas_com_texto(dialogo: list[dict], do_avaliador: bool) -> list[dict]:
    saida = []
    for d in dialogo[1:]:
        tipo = str(d.get("tipo") or "")
        texto = (d.get("texto") or "").strip()
        if not texto or "[RASCUNHO" in texto:
            continue
        if not _RESPUESTA_RE.match(tipo):
            continue
        if ("exceltic" in tipo.lower()) == do_avaliador:
            saida.append(d)
    return saida


# Sinais de que o fecho se apoia em algo concreto: uma versão, um apartado, um
# anexo, ou a menção explícita a evidência/documento aportado.
_EVIDENCIA_RE = re.compile(
    r"\bv\d|\brev\.?\s*\d|\bversi[oó]n\s*\d"
    r"|\bapartado\b|\bapdo\.|\bane[jx]o\b|\bcap[ií]tulo\b|\btabla\b|\bfigura\b|\bp[aá]g\w*\s*\d"
    r"|\bevidencia|\bse\s+adjunta|\bse\s+aporta|\badjunt|\baportad",
    re.IGNORECASE,
)


def check_transiciones(data: dict[str, Any]) -> list[str]:
    """Puntos cujo estado não é sustentado pelo diálogo (PE/03 §8.4).

    Devolve uma lista de motivos. Vazia = todos os estados têm suporte no
    registo. Estes avisos são candidatos a bloqueio (``fill --strict``), ao
    contrário dos do ``lint``, que são boas práticas.
    """
    problemas: list[str] = []
    for pt in data.get("puntos", []):
        estado = pt.get("estado")
        if estado not in ("Resuelto", "Cerrado"):
            continue
        et = _etiqueta(pt)
        dialogo = pt.get("dialogo") or []
        cliente = _linhas_com_texto(dialogo, do_avaliador=False)
        avaliador = _linhas_com_texto(dialogo, do_avaliador=True)

        if not cliente:
            problemas.append(
                f"{et}: '{estado}' sem resposta do cliente no diálogo — o PE/03 §8.4 "
                f"só permite sair de 'Abierto' depois de o cliente responder."
            )
        if not avaliador:
            problemas.append(
                f"{et}: '{estado}' sem aceitação da ação pelo avaliador (linha "
                f"'Respuesta Exceltic' preenchida) — sem ela o punto continua 'Abierto'."
            )
        if estado == "Cerrado" and not any(
            _EVIDENCIA_RE.search((d.get("texto") or "")) for d in cliente + avaliador
        ):
            problemas.append(
                f"{et}: 'Cerrado' sem evidência documental citada no diálogo "
                f"(versão, apartado, anexo ou documento aportado) — o fecho exige "
                f"prova de execução, não só a aceitação da ação."
            )
    return problemas


def lint(data: dict[str, Any]) -> list[str]:
    """Avisos de boas práticas do guia LPA (PE/Inspección/03). Não bloqueiam."""
    avisos: list[str] = []
    for pt in data.get("puntos", []):
        et = _etiqueta(pt)
        if not pt.get("id"):
            avisos.append(f"{et}: sem 'id' estável — corre o merge/suggest para o atribuir.")
        if not pt.get("valoracion"):
            avisos.append(f"{et}: sem 'valoracion' (Crítico/Importante/Informativo/Formal).")
        if not pt.get("punto"):
            avisos.append(f"{et}: 'punto' (requisito normativo) vazio — o guia exige referência à norma.")
        if not pt.get("estado"):
            avisos.append(f"{et}: sem 'estado' (Abierto/Resuelto/Cerrado).")
        dialogo = pt.get("dialogo") or []
        if not dialogo or not (dialogo[0].get("texto") or "").strip():
            avisos.append(f"{et}: sem texto de 'Hallazgo' na primeira linha do diálogo.")
        # Regra de ouro: nenhum Crítico pode ficar Abierto num informe positivo.
        if pt.get("valoracion") == "Crítico" and pt.get("estado") == "Abierto":
            avisos.append(f"{et}: CRÍTICO ainda 'Abierto' — bloqueia um informe positivo (regra de ouro).")
        # Rascunho do 'draft' por rever: a réplica do avaliador ainda é o scaffold
        # automático, não um parecer confirmado (ISO 17020) — não emitir assim.
        if pt.get("_rascunho") or any(
            "[RASCUNHO" in (d.get("texto") or "") for d in (pt.get("dialogo") or [])
        ):
            avisos.append(f"{et}: réplica ainda em RASCUNHO (do 'draft') — rever e confirmar antes de emitir.")
    avisos.extend(check_transiciones(data))
    return avisos


def veredicto(data: dict[str, Any]) -> dict[str, Any]:
    """Resultado esperado do IES segundo o PE/03: o informe "só será positivo
    no caso de que não permaneça aberto nenhum ponto bloqueante".

    - Crítico + Abierto  -> NO_FAVORABLE (bloqueante).
    - Importantes abertos são contados e reportados em bruto: o PE/03 fala em
      "número significativo" sem quantificar, por isso NÃO se aplica limiar —
      a contagem é informação, não bloqueio.
    - Conservador: um punto sem 'estado' conta como Abierto (dado em falta não
      pode tornar um informe favorável).

    Não bloqueia a geração do ficheiro — o RE pode precisar do documento para
    discussão mesmo com críticos abertos; apenas regista o resultado esperado.
    """
    criticos: list = []
    importantes: list = []
    for pt in data.get("puntos", []):
        aberto = (pt.get("estado") or "Abierto") == "Abierto"
        if not aberto:
            continue
        # Pelo ID estável: o veredito de uma revisão tem de ser comparável com o
        # da seguinte, e o 'n' renumera-se.
        ref = pt.get("id") or pt.get("n")
        if pt.get("valoracion") == "Crítico":
            criticos.append(ref)
        elif pt.get("valoracion") == "Importante":
            importantes.append(ref)
    return {
        "resultado": "NO_FAVORABLE" if criticos else "FAVORABLE",
        "criticos_abiertos": criticos,
        "importantes_abiertos": importantes,
    }


def veredicto_texto(v: dict[str, Any]) -> str:
    """Linha única e rastreável do veredito (consola, propriedade do ficheiro)."""
    partes = [f"Veredicto esperado del IES (PE/03): {v['resultado']}"]
    if v["criticos_abiertos"]:
        partes.append(f"críticos abiertos: {', '.join(str(n) for n in v['criticos_abiertos'])}")
    partes.append(f"importantes abiertos: {len(v['importantes_abiertos'])}")
    return " | ".join(partes)


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
