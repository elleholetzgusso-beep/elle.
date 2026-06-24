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
# Pasta do PROJETO (a que contem 3_Doc Generada, etc.).
# Podes mudar aqui OU passar como argumento:
#   py gerar_fsp.py "2025-04019-1 ESTEYCO AsBo PC Cruce Estacion Alegia"
PASTA_PROJETO = r"2025-4263-1-PC POSADAS"

# Template FSP (o teu FSP de referencia)
FSP_TEMPLATE = r"FSP_template.xlsx"

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
    Exemplos:
      EXC2025-16126-1-002-LPA-05  -> expediente=EXC2025-16126-1, cod_doc=002, tipo=LPA, versao=05
      EXC2025-04019-002-LPA-03    -> expediente=EXC2025-04019,   cod_doc=002, tipo=LPA, versao=03
    Ancorado pelo fim: os 3 ultimos campos sao sempre COD_DOC-TIPO-VERSAO.
    Devolve None se nao corresponde ao padrao.
    """
    m = re.match(
        r"(EXC\d{4}-.+)-(\d{3})-([A-Z]+)-(\d+)$",
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
    # avaliadores: linhas com nomes (col 1) e papeis (col 2)
    avaliadores = []
    for r in rows:
        nome = r[1] if len(r) > 1 else None
        papel = r[2] if len(r) > 2 else None
        if nome and papel and "(" in str(papel):
            avaliadores.append({"nome": str(nome), "papel": str(papel)})
    dados["avaliadores"] = avaliadores

    # extrai expediente do ref do LPA  EXC2025-16126-1/002/LPA/05
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
    # cabecalho na linha 2: Nombre, Referencia, Version, Fecha, Autor, Envio, FechaEnvio, Firmado, Estado, Comentarios
    docs = []
    doc_atual = None
    for r in rows_de[1:]:  # pula cabecalho
        nome, ref_doc, ver, fecha, autor, envio, fecha_envio, firmado, estado, comentario = (r + (None,) * 10)[:10]
        if nome:
            doc_atual = {
                "nome": str(nome).strip(),
                "versoes": [],
            }
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

    # --- Remitente: primeiro autor nao vazio dos docs aportados ---
    remitente = ""
    for d in docs:
        for v in d["versoes"]:
            if v.get("autor"):
                remitente = str(v["autor"]).strip()
                break
        if remitente:
            break
    dados["remitente"] = remitente

    # --- Datas do projeto ---
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

    # deduplica: para o mesmo tipo+versao, prefere .xlsm/.docx sobre .pdf
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
        "Fecha de Apertura": dados.get("fecha_apertura"),
        "Fecha de Cierre": dados.get("fecha_cierre"),
        "Normativa": "UE/402/2013, UE/2015/1136",
    }

    # Substitui nome do projeto (primeira linha nao vazia com texto longo)
    for row in ws.iter_rows():
        for cell in row:
            if cell.value and len(str(cell.value)) > 30:
                cell.value = dados.get("projeto", cell.value)
                break

    # Substitui valores pelos labels
    for label, valor in updates.items():
        c = encontrar_celula(ws, label)
        if c:
            ws.cell(row=c.row, column=c.column + 1).value = valor

    # Escreve evaluadores: procura celula "Evaluador" e preenche linhas abaixo
    c_eval = encontrar_celula(ws, "Evaluador", col_max=10)
    if c_eval:
        for i, av in enumerate(dados.get("avaliadores", [])):
            ws.cell(row=c_eval.row + 1 + i, column=c_eval.column).value = av["nome"]

    print("  Portada: OK")


def limpar_sheet(ws, min_row=2):
    """Limpa valores a partir de min_row, ignorando MergedCells."""
    from openpyxl.cell.cell import MergedCell
    for row in ws.iter_rows(min_row=min_row):
        for cell in row:
            if not isinstance(cell, MergedCell):
                cell.value = None


def unmerge_sheet(ws, min_row=2):
    """Remove merges que toquem nas linhas de dados para poder escrever livremente."""
    to_remove = [str(r) for r in list(ws.merged_cells.ranges) if r.max_row >= min_row]
    for r in to_remove:
        ws.unmerge_cells(r)


def popular_envios(ws, dados):
    unmerge_sheet(ws)
    limpar_sheet(ws)

    # Agrupa versoes por envio
    envios = {}
    for doc in dados["docs_avaliados"]:
        for v in doc["versoes"]:
            n = v.get("envio")
            if not n:
                continue
            if n not in envios:
                envios[n] = {
                    "fecha": v.get("fecha_envio"),
                    "docs": [],
                }
            envios[n]["docs"].append(v.get("ref", ""))

    row_num = 2
    for n in sorted(envios.keys(), key=ordenar_num):
        e = envios[n]
        docs_str = "\n".join(d for d in e["docs"] if d)
        ws.cell(row_num, 1).value = n
        ws.cell(row_num, 2).value = e["fecha"]
        ws.cell(row_num, 3).value = dados.get("remitente") or REMITENTE_PADRAO
        ws.cell(row_num, 4).value = docs_str
        ws.cell(row_num, 5).value = COMENTARIO_ENVIO
        row_num += 1

    print(f"  Envios de Cliente: {row_num - 2} envios")


def popular_doc_aportados(ws, dados):
    unmerge_sheet(ws)
    limpar_sheet(ws)

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
    unmerge_sheet(ws)
    limpar_sheet(ws)

    # Indice de versoes LPA por numero
    lpa_cv = {v["num"]: v for v in versoes_lpa}

    row_num = 2
    for arq in arquivos:
        tipo = arq["tipo"]
        ver_num = int(arq["versao"])
        ver_str = str(ver_num).zfill(2)

        # Descricao da versao
        if tipo == "LPA" and ver_num in lpa_cv:
            ctrl_ver = lpa_cv[ver_num].get("desc", "")
        else:
            ctrl_ver = ""

        ws.cell(row_num, 1).value = ETAPAS.get(tipo, "")
        ws.cell(row_num, 2).value = arq["ref"]
        ws.cell(row_num, 3).value = NOMES_DOCS.get(tipo, tipo)
        ws.cell(row_num, 4).value = ver_str
        ws.cell(row_num, 5).value = ""   # Redactor — preencher manualmente
        ws.cell(row_num, 6).value = ""   # Revisor — preencher manualmente
        ws.cell(row_num, 7).value = arq.get("mtime")
        ws.cell(row_num, 8).value = arq.get("mtime")
        ws.cell(row_num, 9).value = ctrl_ver
        row_num += 1

    print(f"  Control doc. Generados: {row_num - 2} entradas")
    if row_num > 2:
        print("  NOTA: preenche Redactor/Revisor manualmente na aba Control doc. Generados")


# ---- localizar pasta de docs gerados -----------------------

def encontrar_pasta_docs(pasta_projeto):
    """
    Dentro da pasta do projeto, procura a subpasta '3_Doc Generada'
    (tolera variacoes de espaco/acento) e dentro dela a pasta 'Doc'.
    Devolve o Path da pasta com os ficheiros gerados.
    """
    raiz = Path(pasta_projeto)
    if not raiz.exists():
        raise SystemExit(f"ERRO: Pasta do projeto nao encontrada: {raiz}")

    # procura subpasta que contenha "doc generada" no nome
    gerada = None
    for sub in raiz.iterdir():
        if sub.is_dir() and "doc generada" in sub.name.lower().replace("_", " "):
            gerada = sub
            break
    if gerada is None:
        raise SystemExit(f"ERRO: Nao encontrei '3_Doc Generada' dentro de '{raiz}'")

    # dentro dela, procura subpasta 'Doc'
    doc = gerada / "Doc"
    if doc.is_dir():
        return doc
    # se nao houver subpasta Doc, usa a propria pasta Generada
    return gerada


# ---- main --------------------------------------------------

def main():
    import sys
    pasta_projeto = sys.argv[1] if len(sys.argv) > 1 else PASTA_PROJETO

    pasta = encontrar_pasta_docs(pasta_projeto)
    template = Path(FSP_TEMPLATE)
    output = Path(pasta_projeto) / "FSP_GERADO.xlsx"

    if not template.exists():
        raise SystemExit(f"ERRO: Template FSP nao encontrado: {template}")

    print("=" * 55)
    print("GERADOR DE FSP")
    print("=" * 55)
    print(f"Projeto: {pasta_projeto}")
    print(f"Pasta docs: {pasta}")

    # 1. Ler LPA
    lpa_path = encontrar_ultimo_lpa(pasta)
    dados = ler_lpa(lpa_path)
    print(f"Projeto: {str(dados.get('projeto', ''))[:70]}")
    print(f"Expediente: {dados.get('expediente', '')}")
    print(f"Docs avaliados: {len(dados['docs_avaliados'])}")

    # 2. Escanear pasta
    arquivos = escanear_pasta(pasta)
    print(f"Ficheiros gerados encontrados: {len(arquivos)}")

    # 3. Carregar template
    wb = openpyxl.load_workbook(template)
    print("\nPopulando sheets:")

    # 4. Portada
    if "Portada" in wb.sheetnames:
        popular_portada(wb["Portada"], dados, dados.get("lpa_ref", ""))

    # 5. Envios de Cliente
    aba_envios = next((s for s in wb.sheetnames if "envio" in s.lower()), None)
    if aba_envios:
        popular_envios(wb[aba_envios], dados)

    # 6. Control doc. Aportados
    aba_aportados = next((s for s in wb.sheetnames if "aportado" in s.lower()), None)
    if aba_aportados:
        popular_doc_aportados(wb[aba_aportados], dados)

    # 7. Control doc. Generados
    aba_generados = next((s for s in wb.sheetnames if "generado" in s.lower()), None)
    if aba_generados:
        popular_doc_generados(wb[aba_generados], arquivos, dados.get("versoes_lpa", []))

    # 8. M.C.S. — mantida do template, nao alterada
    print("  M.C.S.: mantida do template (preencher manualmente no final)")

    # 9. Guardar
    wb.save(output)
    print(f"\nGuardado em: {output.resolve()}")
    print("=" * 55)
    print("Proximos passos:")
    print("  1. Abre FSP_GERADO.xlsx e revisa cada aba")
    print("  2. Preenche Redactor/Revisor em Control doc. Generados")
    print("  3. Preenche M.C.S. no final do projeto")
    print("=" * 55)


if __name__ == "__main__":
    main()
