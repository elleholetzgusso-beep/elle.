#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GERADOR DE FSP  —  Exceltic
------------------------------------------------------------
Uso:
  1. Coloca este script na pasta automacao\
  2. Ajusta o bloco CONFIG abaixo
  3. py gerar_fsp.py

Gera FSP_GERADO.xlsx a partir de:
  - O LPA mais recente (.xlsm) da pasta 3_Doc_Generada
  - Os ficheiros PES / LPA / IES presentes nessa pasta

Dependencias:  pip install openpyxl
"""

import re
import os
from pathlib import Path
from copy import copy
import datetime
import openpyxl
from openpyxl.utils import get_column_letter

# ========================== CONFIG ==========================
# Pasta onde estao os ficheiros gerados (PES, LPA, IES)
PASTA_DOCS_GERADOS = r"3_Doc_Generada"

# Template FSP (o teu FSP de referencia)
FSP_TEMPLATE = r"FSP_template.xlsx"

# Nome do ficheiro de saida
OUTPUT = r"FSP_GERADO.xlsx"

# Remitente padrao (quem envia os documentos ao cliente)
REMITENTE_PADRAO = "UTE PASOS ANDENES LOTE 3"

# Comentario padrao na aba Envios de Cliente
COMENTARIO_ENVIO = "Documentos recibidos para evaluacion, apoyo o justificacion"

# Etapas por tipo de documento
ETAPAS = {
    "PES": "Planificacion / Act. 2. Redaccion del Plan de la Evaluacion.",
    "LPA": "Planificacion / Act. 3. Revision de los Planes del Solicitante.",
    "IES": "Ejecucion / Act. 8. Redaccion del Informe de Evaluacion.",
}

NOMES_DOCS = {
    "PES": "Plan de Evaluacion de Seguridad",
    "LPA": "Listado de Puntos Abiertos",
    "IES": "Informe de Evaluacion Independiente de Seguridad",
}
# ============================================================


# ---- helpers -----------------------------------------------

def fmt_date(d):
    if isinstance(d, datetime.datetime):
        return d.strftime("%d/%m/%Y")
    return str(d) if d else ""


def ordenar_num(v):
    try:
        return int(v)
    except Exception:
        return 0


def parse_nome_ficheiro(nome):
    """
    Padrao: EXC{ANO}-{CODIGO_OFERTA}-{COD_DOC}-{NOME_DOC}-{VERSAO}
    Exemplo: EXC2025-16126-1-002-LPA-05
      -> expediente = EXC2025-16126-1
      -> cod_doc    = 002
      -> tipo       = LPA
      -> versao     = 05
    Devolve None se nao corresponde ao padrao.
    """
    m = re.match(
        r"(EXC\d{4}-[\d]+-\d+)-(\d{3})-([A-Z]+)-(\d+)",
        nome.upper()
    )
    if not m:
        return None
    return {
        "expediente": m.group(1),
        "cod_doc": m.group(2),
        "tipo": m.group(3),
        "versao": m.group(4),
        "ref": nome,
    }


# ---- leitura do LPA ----------------------------------------

def encontrar_ultimo_lpa(pasta):
    """Devolve o Path do LPA .xlsm com maior numero de versao."""
    lpas = []
    for f in Path(pasta).iterdir():
        if not f.is_file():
            continue
        parsed = parse_nome_ficheiro(f.stem)
        if parsed and parsed["tipo"] == "LPA" and f.suffix.lower() in (".xlsm", ".xlsx"):
            lpas.append((int(parsed["versao"]), f))
    if not lpas:
        raise SystemExit(f"ERRO: Nenhum LPA .xlsm encontrado em '{pasta}'")
    lpas.sort(key=lambda x: x[0])
    _, path = lpas[-1]
    print(f"LPA encontrado: {path.name}")
    return path


def ler_lpa(path):
    wb = openpyxl.load_workbook(path, keep_vba=True, data_only=True)
    dados = {}

    # --- Portada ---
    ws = wb["Portada"]
    rows = [r for r in ws.iter_rows(values_only=True) if any(v for v in r)]
    dados["projeto"] = rows[0][1] if rows else ""
    dados["lpa_ref"] = rows[2][1] if len(rows) > 2 else ""
    avaliadores = []
    for r in rows:
        nome = r[1] if len(r) > 1 else None
        papel = r[2] if len(r) > 2 else None
        if nome and papel and "(" in str(papel):
            avaliadores.append({"nome": str(nome), "papel": str(papel)})
    dados["avaliadores"] = avaliadores

    ref = str(dados["lpa_ref"])
    m = re.match(r"(EXC\d{4}-[\d-]+\d)", ref)
    dados["expediente"] = m.group(1) if m else ""

    # --- Control de versiones ---
    ws_cv = wb["Control de versiones"]
    versoes_lpa = []
    for r in ws_cv.iter_rows(min_row=3, values_only=True):
        if r[0] and str(r[0]).strip().isdigit():
            versoes_lpa.append({
                "num": int(r[0]),
                "fecha": r[1],
                "desc": r[2],
            })
    dados["versoes_lpa"] = versoes_lpa

    # --- Doc Evaluados ---
    ws_de = wb["Doc Evaluados"]
    rows_de = list(ws_de.iter_rows(min_row=2, values_only=True))
    docs = []
    doc_atual = None
    for r in rows_de[1:]:
        nome, ref_doc, ver, fecha, autor, envio, fecha_envio, firmado, estado, comentario = (r + (None,) * 10)[:10]
        if nome:
            doc_atual = {"nome": str(nome).strip(), "versoes": []}
            docs.append(doc_atual)
        if doc_atual is not None and ref_doc:
            doc_atual["versoes"].append({
                "ref": str(ref_doc).strip() if ref_doc else "",
                "ver": ver,
                "fecha": fecha,
                "autor": autor,
                "envio": envio,
                "fecha_envio": fecha_envio,
                "firmado": firmado,
                "estado": estado,
                "comentario": comentario,
            })
    dados["docs_avaliados"] = docs

    todas_datas = [
        v["fecha_envio"]
        for d in docs
        for v in d["versoes"]
        if v.get("fecha_envio")
    ]
    todas_datas = [d for d in todas_datas if isinstance(d, datetime.datetime)]
    dados["fecha_apertura"] = min(todas_datas) if todas_datas else None
    dados["fecha_cierre"] = max(todas_datas) if todas_datas else None

    wb.close()
    return dados


# ---- escanear pasta de docs gerados ------------------------

def escanear_pasta(pasta):
    """Devolve lista de dicts para cada ficheiro gerado (PES/LPA/IES)."""
    resultado = []
    for f in sorted(Path(pasta).iterdir()):
        if not f.is_file() or f.suffix.lower() not in (".xlsm", ".xlsx", ".docx", ".pdf"):
            continue
        parsed = parse_nome_ficheiro(f.stem)
        if not parsed or parsed["tipo"] not in ("PES", "LPA", "IES"):
            continue
        mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
        parsed["mtime"] = mtime
        parsed["extensao"] = f.suffix.lower()
        resultado.append(parsed)

    visto = {}
    for p in resultado:
        chave = (p["tipo"], p["versao"])
        if chave not in visto or p["extensao"] in (".xlsm", ".docx"):
            visto[chave] = p
    return sorted(visto.values(), key=lambda x: (x["tipo"], ordenar_num(x["versao"])))


# ---- encontrar celula por texto ----------------------------

def encontrar_celula(ws, texto, col_max=5):
    for row in ws.iter_rows(max_col=col_max):
        for cell in row:
            if cell.value and texto.lower() in str(cell.value).lower():
                return cell
    return None


# ---- popular sheets ----------------------------------------

def popular_portada(ws, dados, ref_fsp):
    updates = {
        "Codigo de Proyecto": ref_fsp,
        "Referencia": ref_fsp.replace("/001/PES/02", "").replace("/", "-") + "-000-FSP-01",
        "Fecha de Apertura": dados.get("fecha_apertura"),
        "Fecha de Cierre": dados.get("fecha_cierre"),
        "Normativa": "UE/402/2013, UE/2015/1136",
    }

    for row in ws.iter_rows():
        for cell in row:
            if cell.value and len(str(cell.value)) > 30 and "cruce" in str(cell.value).lower():
                cell.value = dados.get("projeto", cell.value)
                break

    for label, valor in updates.items():
        c = encontrar_celula(ws, label)
        if c:
            ws.cell(row=c.row, column=c.column + 1).value = valor

    print("  Portada: OK")


def popular_envios(ws, dados):
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.value = None

    envios = {}
    for doc in dados["docs_avaliados"]:
        for v in doc["versoes"]:
            n = v.get("envio")
            if not n:
                continue
            if n not in envios:
                envios[n] = {"fecha": v.get("fecha_envio"), "docs": []}
            envios[n]["docs"].append(v.get("ref", ""))

    row_num = 2
    for n in sorted(envios.keys(), key=ordenar_num):
        e = envios[n]
        docs_str = "\n".join(d for d in e["docs"] if d)
        ws.cell(row_num, 1).value = n
        ws.cell(row_num, 2).value = e["fecha"]
        ws.cell(row_num, 3).value = REMITENTE_PADRAO
        ws.cell(row_num, 4).value = docs_str
        ws.cell(row_num, 5).value = COMENTARIO_ENVIO
        row_num += 1

    print(f"  Envios de Cliente: {row_num - 2} envios")


def popular_doc_aportados(ws, dados):
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.value = None

    row_num = 2
    de_num = 1
    for doc in dados["docs_avaliados"]:
        id_str = f"[DE-{de_num}]"
        primeira = True
        for v in doc["versoes"]:
            ws.cell(row_num, 1).value = id_str if primeira else None
            ws.cell(row_num, 2).value = v.get("ref", "")
            ws.cell(row_num, 3).value = doc["nome"] if primeira else None
            ws.cell(row_num, 4).value = v.get("envio")
            ws.cell(row_num, 5).value = v.get("fecha_envio")
            ws.cell(row_num, 6).value = v.get("ver")
            ws.cell(row_num, 7).value = v.get("fecha")
            ws.cell(row_num, 8).value = v.get("autor", "")
            ws.cell(row_num, 9).value = v.get("estado", "")
            ws.cell(row_num, 10).value = v.get("comentario", "")
            row_num += 1
            primeira = False
        de_num += 1

    print(f"  Control doc. Aportados: {de_num - 1} documentos")


def popular_doc_generados(ws, arquivos, versoes_lpa):
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.value = None

    lpa_cv = {v["num"]: v for v in versoes_lpa}

    row_num = 2
    for arq in arquivos:
        tipo = arq["tipo"]
        ver_num = int(arq["versao"])
        ver_str = str(ver_num).zfill(2)

        if tipo == "LPA" and ver_num in lpa_cv:
            ctrl_ver = lpa_cv[ver_num].get("desc", "")
        else:
            ctrl_ver = ""

        ws.cell(row_num, 1).value = ETAPAS.get(tipo, "")
        ws.cell(row_num, 2).value = arq["ref"]
        ws.cell(row_num, 3).value = NOMES_DOCS.get(tipo, tipo)
        ws.cell(row_num, 4).value = ver_str
        ws.cell(row_num, 5).value = ""  # Redactor
        ws.cell(row_num, 6).value = ""  # Revisor
        ws.cell(row_num, 7).value = arq.get("mtime")
        ws.cell(row_num, 8).value = arq.get("mtime")
        ws.cell(row_num, 9).value = ctrl_ver
        row_num += 1

    print(f"  Control doc. Generados: {row_num - 2} entradas")
    if row_num > 2:
        print("  NOTA: preenche Redactor/Revisor manualmente na aba Control doc. Generados")


# ---- main --------------------------------------------------

def main():
    pasta = Path(PASTA_DOCS_GERADOS)
    template = Path(FSP_TEMPLATE)

    if not pasta.exists():
        raise SystemExit(f"ERRO: Pasta nao encontrada: {pasta}")
    if not template.exists():
        raise SystemExit(f"ERRO: Template FSP nao encontrado: {template}")

    print("=" * 55)
    print("GERADOR DE FSP")
    print("=" * 55)

    lpa_path = encontrar_ultimo_lpa(pasta)
    dados = ler_lpa(lpa_path)
    print(f"Projeto: {str(dados.get('projeto', ''))[:70]}")
    print(f"Expediente: {dados.get('expediente', '')}")
    print(f"Docs avaliados: {len(dados['docs_avaliados'])}")

    arquivos = escanear_pasta(pasta)
    print(f"Ficheiros gerados encontrados: {len(arquivos)}")

    wb = openpyxl.load_workbook(template)
    print("\nPopulando sheets:")

    if "Portada" in wb.sheetnames:
        popular_portada(wb["Portada"], dados, dados.get("lpa_ref", ""))

    aba_envios = next((s for s in wb.sheetnames if "envio" in s.lower()), None)
    if aba_envios:
        popular_envios(wb[aba_envios], dados)

    aba_aportados = next((s for s in wb.sheetnames if "aportado" in s.lower()), None)
    if aba_aportados:
        popular_doc_aportados(wb[aba_aportados], dados)

    aba_generados = next((s for s in wb.sheetnames if "generado" in s.lower()), None)
    if aba_generados:
        popular_doc_generados(wb[aba_generados], arquivos, dados.get("versoes_lpa", []))

    print("  M.C.S.: mantida do template (preencher manualmente no final)")

    saida = Path(OUTPUT)
    wb.save(saida)
    print(f"\nGuardado em: {saida.resolve()}")
    print("=" * 55)
    print("Proximos passos:")
    print("  1. Abre FSP_GERADO.xlsx e revisa cada aba")
    print("  2. Preenche Redactor/Revisor em Control doc. Generados")
    print("  3. Preenche M.C.S. no final do projeto")
    print("=" * 55)


if __name__ == "__main__":
    main()
