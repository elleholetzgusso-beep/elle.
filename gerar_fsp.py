#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GERADOR DE FSP  —  Exceltic
------------------------------------------------------------
Uso:
  1. Coloca este script na pasta automacao\
  2. Ajusta PASTA_PROJETO abaixo (ou passa como argumento)
  3. py gerar_fsp.py
     py gerar_fsp.py "2025-04019-1 ESTEYCO AsBo PC Cruce Estacion Alegia"

Dependencias:  pip install openpyxl
"""

import re
import sys
import shutil
import zipfile
import unicodedata
from pathlib import Path
import datetime
import openpyxl
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

# ========================== CONFIG ==========================
PASTA_PROJETO   = r"2025-4263-1-PC POSADAS"
FSP_TEMPLATE    = r"FSP_template.xlsx"
COMENTARIO_ENVIO = "Documentos recibidos para evaluacion, apoyo o justificacion"

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

def norm(txt):
    """Minusculas sem acentos para comparacao."""
    if txt is None:
        return ""
    txt = str(txt)
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return txt.lower()


def ordenar_num(v):
    try:
        return int(v)
    except Exception:
        return 0


def parse_nome_ficheiro(nome):
    m = re.match(r"(EXC\d{4}-.+)-(\d{3})-([A-Z]+)-(\d+)$", nome.upper())
    if not m:
        return None
    return {
        "expediente": m.group(1),
        "cod_doc":    m.group(2),
        "tipo":       m.group(3),
        "versao":     m.group(4),
        "ref":        nome,
    }


def extrair_iniciais(papel):
    """'Roberto Abad (RAM)' -> 'RAM'. Sem parenteses: 'Roberto Abad' -> 'RA'."""
    m = re.search(r"\(([A-Z]+)\)", str(papel))
    if m:
        return m.group(1)
    return ""


def iniciais_do_nome(nome):
    """'Soukaina Meliani' -> 'SM'"""
    partes = str(nome).strip().split()
    return "".join(p[0].upper() for p in partes if p)


def iniciais_avaliadores(avaliadores):
    """Devolve string 'SM/RAM' com todas as iniciais (de papel ou de nome)."""
    result = []
    for av in avaliadores:
        ini = extrair_iniciais(av["papel"]) or iniciais_do_nome(av["nome"])
        if ini:
            result.append(ini)
    return "/".join(result)


def iniciais_por_papel(avaliadores, palavra):
    """Devolve iniciais do primeiro avaliador cujo papel contenha 'palavra'."""
    for av in avaliadores:
        if palavra.lower() in norm(av["papel"]):
            return extrair_iniciais(av["papel"])
    return ""


# ---- leitura do LPA ----------------------------------------

def encontrar_ultimo_lpa(pasta):
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

    # nome do projeto: primeira celula com texto longo (> 30 chars)
    dados["projeto"] = ""
    for r in ws.iter_rows(values_only=True):
        for v in r:
            if v and len(str(v)) > 30:
                dados["projeto"] = str(v).strip()
                break
        if dados["projeto"]:
            break

    # ref do LPA: celula com padrao EXC.../NNN/TIPO/NN
    dados["lpa_ref"] = ""
    for r in ws.iter_rows(max_col=8, values_only=True):
        for v in r:
            if v and re.search(r"EXC\d{4}-.+/\d+/[A-Z]+/\d+", str(v)):
                dados["lpa_ref"] = str(v).strip()
                break
        if dados["lpa_ref"]:
            break

    # avaliadores: linhas com nome (col B) e papel entre parenteses (col C)
    avaliadores = []
    for r in ws.iter_rows(values_only=True):
        nome  = r[1] if len(r) > 1 else None
        papel = r[2] if len(r) > 2 else None
        if nome and papel and "(" in str(papel):
            avaliadores.append({"nome": str(nome).strip(), "papel": str(papel).strip()})
    dados["avaliadores"] = avaliadores

    # expediente
    m = re.match(r"(EXC\d{4}-[\d-]+\d)", str(dados["lpa_ref"]))
    dados["expediente"] = m.group(1) if m else ""

    # --- Control de versiones ---
    ws_cv = wb["Control de versiones"]
    versoes_lpa = []
    for r in ws_cv.iter_rows(min_row=3, values_only=True):
        if r[0] and str(r[0]).strip().isdigit():
            versoes_lpa.append({"num": int(r[0]), "fecha": r[1], "desc": r[2]})
    dados["versoes_lpa"] = versoes_lpa

    # --- Doc Evaluados ---
    ws_de   = wb["Doc Evaluados"]
    rows_de = list(ws_de.iter_rows(min_row=2, values_only=True))

    # Le cabecalho (linha 1 do iter, ou seja rows_de[0]) para mapear colunas por nome
    cabecalho = rows_de[0] if rows_de else ()
    def idx(nomes):
        """Devolve o indice da primeira coluna cujo cabecalho contem algum dos nomes (sem acentos)."""
        for i, h in enumerate(cabecalho):
            hn = norm(str(h)) if h else ""
            for n in nomes:
                if n in hn:
                    return i
        return None

    i_nome     = idx(["nombre", "nome"])
    i_ref      = idx(["referencia", "ref"])
    i_ver      = idx(["version", "versao", "vers"])
    i_fecha    = idx(["fecha", "data"]) if idx(["fecha envio", "data envio"]) is None else None
    i_autor    = idx(["autor", "remitente"])
    i_envio    = idx(["envio", "n envio", "num"])
    i_fenvio   = idx(["fecha envio", "data envio", "recibido", "recebido"])
    i_firmado  = idx(["firmado", "assinado"])
    i_estado   = idx(["estado", "evaluado", "resultado"])
    i_coment   = idx(["comentario", "observa"])
    # fecha (data do documento) e diferente de fecha_envio
    if i_fecha is None:
        used = {i_ref, i_ver, i_autor, i_envio, i_fenvio, i_firmado, i_estado, i_coment, i_nome}
        for i, h in enumerate(cabecalho):
            hn = norm(str(h)) if h else ""
            if i not in used and ("fecha" in hn or "data" in hn):
                i_fecha = i
                break

    def get(r, i):
        return r[i] if i is not None and i < len(r) else None

    docs, doc_atual = [], None
    for r in rows_de[1:]:  # pula cabecalho
        nome    = get(r, i_nome)
        ref_doc = get(r, i_ref)
        if nome:
            doc_atual = {"nome": str(nome).strip(), "versoes": []}
            docs.append(doc_atual)
        if doc_atual is not None and ref_doc:
            doc_atual["versoes"].append({
                "ref":        str(ref_doc).strip(),
                "ver":        get(r, i_ver),
                "fecha":      get(r, i_fecha),
                "autor":      get(r, i_autor),
                "envio":      get(r, i_envio),
                "fecha_envio": get(r, i_fenvio),
                "firmado":    get(r, i_firmado),
                "estado":     get(r, i_estado),
                "comentario": get(r, i_coment),
            })
    dados["docs_avaliados"] = docs

    # remitente: primeiro autor nao vazio
    dados["remitente"] = ""
    for d in docs:
        for v in d["versoes"]:
            if v.get("autor"):
                dados["remitente"] = str(v["autor"]).strip()
                break
        if dados["remitente"]:
            break

    # datas abertura/fecho
    todas = [v["fecha_envio"] for d in docs for v in d["versoes"] if v.get("fecha_envio")]
    todas = [x for x in todas if isinstance(x, datetime.datetime)]
    dados["fecha_apertura"] = min(todas) if todas else None
    dados["fecha_cierre"]   = max(todas) if todas else None

    wb.close()
    return dados


# ---- escanear pasta de docs gerados ------------------------

def escanear_pasta(pasta):
    resultado = []
    for f in sorted(Path(pasta).iterdir()):
        if not f.is_file() or f.suffix.lower() not in (".xlsm", ".xlsx", ".docx", ".pdf"):
            continue
        parsed = parse_nome_ficheiro(f.stem)
        if not parsed or parsed["tipo"] not in ("PES", "LPA", "IES"):
            continue
        mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
        parsed["mtime"]    = mtime
        parsed["extensao"] = f.suffix.lower()
        resultado.append(parsed)
    visto = {}
    for p in resultado:
        chave = (p["tipo"], p["versao"])
        if chave not in visto or p["extensao"] in (".xlsm", ".docx"):
            visto[chave] = p
    return sorted(visto.values(), key=lambda x: (x["tipo"], ordenar_num(x["versao"])))


# ---- encontrar celula por texto (normalizado) ---------------

def encontrar_celula(ws, texto, col_max=5):
    alvo = norm(texto)
    for row in ws.iter_rows(max_col=col_max):
        for cell in row:
            if cell.value and alvo in norm(cell.value):
                return cell
    return None


# ---- popular sheets ----------------------------------------

def _celula_valor_label(ws, label):
    """
    Encontra a primeira celula nao-MergedCell que contem `label` (normalizado).
    Devolve a celula ADJACENTE (mesma linha, coluna+1) onde o valor deve ir,
    saltando MergedCells ate encontrar uma celula editavel.
    """
    from openpyxl.cell.cell import MergedCell
    c = encontrar_celula(ws, label)
    if not c:
        return None
    # percorre para a direita ate encontrar celula editavel
    col = c.column + 1
    while col <= ws.max_column + 5:
        candidate = ws.cell(row=c.row, column=col)
        if not isinstance(candidate, MergedCell):
            return candidate
        col += 1
    return None


def popular_portada(ws, dados):
    from openpyxl.cell.cell import MergedCell

    lpa_ref = str(dados.get("lpa_ref", ""))
    # Referencia FSP: EXC2025-04019/002/LPA/03 -> EXC2025-04019-000-FSP-01
    ref_fsp = re.sub(r"/\d+/[A-Z]+/\d+$", "-000-FSP-01", lpa_ref)

    # --- Nome do projeto: so celulas cujo texto começa com "PROYECTO DE" ---
    projeto = dados.get("projeto", "")
    if projeto:
        for row in ws.iter_rows():
            for cell in row:
                if (cell.value and not isinstance(cell, MergedCell)
                        and norm(str(cell.value)).startswith("proyecto de")):
                    cell.value = projeto

    # --- Campos label → valor ---
    updates = {
        "Codigo de Proyecto": lpa_ref,
        "Referencia":         ref_fsp,
        "Fecha de Apertura":  dados.get("fecha_apertura"),
        "Fecha de Cierre":    dados.get("fecha_cierre"),
        "Normativa":          "UE/402/2013, UE/2015/1136",
    }
    for label, valor in updates.items():
        dest = _celula_valor_label(ws, label)
        if dest:
            dest.value = valor
            if isinstance(valor, datetime.datetime):
                dest.number_format = "DD/MM/YYYY"

    # --- Avaliadores: a partir da linha do label "Equipo Evaluador" ---
    c_eval = encontrar_celula(ws, "Equipo Evaluador", col_max=3) \
             or encontrar_celula(ws, "Evaluador", col_max=3)
    if c_eval:
        avaliadores = dados.get("avaliadores", [])
        for i, av in enumerate(avaliadores):
            row_av = c_eval.row + i  # primeiro avaliador na mesma linha do label
            # Nome: coluna C (col_label + 1), pulando MergedCells
            col_nome = c_eval.column + 1
            while isinstance(ws.cell(row_av, col_nome), MergedCell):
                col_nome += 1
            ws.cell(row=row_av, column=col_nome).value = av["nome"]
            # Papel/Role: coluna F (col_nome + 3)
            col_papel = col_nome + 3
            ws.cell(row=row_av, column=col_papel).value = av["papel"]

    print("  Portada: OK")


def limpar_sheet(ws, min_row=2):
    from openpyxl.cell.cell import MergedCell
    for row in ws.iter_rows(min_row=min_row):
        for cell in row:
            if not isinstance(cell, MergedCell):
                cell.value = None
                # nao toca no numero_format para preservar formatacao do template


def escrever_data(cell, valor):
    """Escreve um valor de data preservando o formato DD/MM/YYYY."""
    cell.value = valor
    if isinstance(valor, datetime.datetime):
        cell.number_format = "DD/MM/YYYY"


def unmerge_sheet(ws, min_row=2):
    """Remove apenas merges que comecem nas linhas de dados (nao toca no cabecalho)."""
    to_remove = [str(r) for r in list(ws.merged_cells.ranges) if r.min_row >= min_row]
    for r in to_remove:
        ws.unmerge_cells(r)


def popular_envios(ws, dados):
    unmerge_sheet(ws)
    limpar_sheet(ws)

    # Agrupa por numero de envio; guarda ref + nome do doc
    envios = {}
    for doc in dados["docs_avaliados"]:
        for v in doc["versoes"]:
            n = v.get("envio")
            if not n:
                continue
            if n not in envios:
                envios[n] = {"fecha": v.get("fecha_envio"), "docs": []}
            ref  = v.get("ref", "")
            nome = doc["nome"]
            envios[n]["docs"].append(f"{ref} {nome}" if ref else nome)

    row_num = 2
    for n in sorted(envios.keys(), key=ordenar_num):
        e = envios[n]
        docs_str = "\n".join(d for d in e["docs"] if d)
        ws.cell(row_num, 1).value = n
        escrever_data(ws.cell(row_num, 2), e["fecha"])
        ws.cell(row_num, 3).value = dados.get("remitente") or ""
        ws.cell(row_num, 4).value = docs_str
        ws.cell(row_num, 5).value = COMENTARIO_ENVIO
        row_num += 1

    print(f"  Envios de Cliente: {row_num - 2} envios")


def popular_doc_aportados(ws, dados):
    unmerge_sheet(ws)
    limpar_sheet(ws)

    avs      = dados.get("avaliadores", [])
    eval_str = iniciais_avaliadores(avs)  # ex: "SM/RAM"

    row_num = 2
    de_num  = 1
    for doc in dados["docs_avaliados"]:
        id_str   = f"[DE-{de_num}]"
        primeira = True
        for v in doc["versoes"]:
            ws.cell(row_num, 1).value  = id_str if primeira else None
            ws.cell(row_num, 2).value  = v.get("ref", "")
            ws.cell(row_num, 3).value  = doc["nome"] if primeira else None
            ws.cell(row_num, 4).value  = v.get("envio")
            escrever_data(ws.cell(row_num, 5), v.get("fecha_envio"))
            ws.cell(row_num, 6).value  = v.get("ver")
            escrever_data(ws.cell(row_num, 7), v.get("fecha"))
            ws.cell(row_num, 8).value  = eval_str          # Evaluador (SM/RAM)
            ws.cell(row_num, 9).value  = v.get("estado", "")
            ws.cell(row_num, 10).value = v.get("comentario", "")
            row_num  += 1
            primeira  = False
        de_num += 1

    # Formatacao condicional col I (Evaluado)
    last_row = max(row_num - 1, 2)
    cf_range = f"I2:I{last_row}"
    fill_grey   = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
    fill_red    = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    fill_yellow = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    fill_green  = PatternFill(start_color="92D050", end_color="92D050", fill_type="solid")
    ws.conditional_formatting.add(cf_range, CellIsRule(operator="equal", formula=['"Informativo"'], fill=fill_grey))
    ws.conditional_formatting.add(cf_range, CellIsRule(operator="equal", formula=['"Abierto"'],    fill=fill_red))
    ws.conditional_formatting.add(cf_range, CellIsRule(operator="equal", formula=['"Resuelto"'],   fill=fill_yellow))
    ws.conditional_formatting.add(cf_range, CellIsRule(operator="equal", formula=['"Conforme"'],   fill=fill_green))

    # Dropdown de validacao de dados col I
    dv = DataValidation(
        type="list",
        formula1='"Informativo,Abierto,Resuelto,Conforme"',
        allow_blank=True,
        showDropDown=False,
    )
    dv.sqref = cf_range
    ws.add_data_validation(dv)

    print(f"  Control doc. Aportados: {de_num - 1} documentos")


def popular_doc_generados(ws, arquivos, versoes_lpa, avaliadores):
    unmerge_sheet(ws)
    limpar_sheet(ws)

    lpa_cv = {v["num"]: v for v in versoes_lpa}

    # Redactor = Evaluador Tecnico; Revisor = Responsable de Evaluacion
    redactor = iniciais_por_papel(avaliadores, "tecnico")
    revisor  = iniciais_por_papel(avaliadores, "responsable")

    row_num = 2
    for arq in arquivos:
        tipo    = arq["tipo"]
        ver_num = int(arq["versao"])
        ver_str = str(ver_num).zfill(2)
        ctrl_ver = lpa_cv[ver_num].get("desc", "") if tipo == "LPA" and ver_num in lpa_cv else ""

        ws.cell(row_num, 1).value = ETAPAS.get(tipo, "")
        ws.cell(row_num, 2).value = arq["ref"]
        ws.cell(row_num, 3).value = NOMES_DOCS.get(tipo, tipo)
        ws.cell(row_num, 4).value = ver_str
        ws.cell(row_num, 5).value = redactor
        ws.cell(row_num, 6).value = revisor
        ws.cell(row_num, 7).value = arq.get("mtime")
        ws.cell(row_num, 8).value = arq.get("mtime")
        ws.cell(row_num, 9).value = ctrl_ver
        row_num += 1

    print(f"  Control doc. Generados: {row_num - 2} entradas")


# ---- localizar pasta de docs gerados -----------------------

def encontrar_pasta_docs(pasta_projeto):
    raiz = Path(pasta_projeto)
    if not raiz.exists():
        raise SystemExit(f"ERRO: Pasta do projeto nao encontrada: {raiz}")
    gerada = None
    for sub in raiz.iterdir():
        if sub.is_dir() and "doc generada" in sub.name.lower().replace("_", " "):
            gerada = sub
            break
    if gerada is None:
        raise SystemExit(f"ERRO: Nao encontrei '3_Doc Generada' dentro de '{raiz}'")
    doc = gerada / "Doc"
    return doc if doc.is_dir() else gerada


# ---- preservar logo do template ----------------------------

def copiar_imagem_template(template_path, output_path):
    """
    openpyxl nao preserva imagens/drawings. Apos salvar, esta funcao copia
    os ficheiros de logo do template para o output via zipfile.
    """
    files_to_copy = [
        "xl/drawings/drawing1.xml",
        "xl/drawings/_rels/drawing1.xml.rels",
        "xl/media/image1.png",
    ]

    with zipfile.ZipFile(str(template_path), "r") as tmpl:
        namelist = tmpl.namelist()
        drawing_data = {f: tmpl.read(f) for f in files_to_copy if f in namelist}
        # le o _rels do sheet1 do template para reutilizar o rId correto
        tmpl_sheet1_rels = tmpl.read("xl/worksheets/_rels/sheet1.xml.rels").decode("utf-8") \
            if "xl/worksheets/_rels/sheet1.xml.rels" in namelist else ""

    if not drawing_data:
        print("  Aviso: logo nao encontrado no template")
        return

    # extrai a linha de Relationship do drawing do template
    drawing_rel_line = ""
    for line in tmpl_sheet1_rels.splitlines():
        if "drawing" in line.lower() and "Relationship" in line:
            drawing_rel_line = line.strip()
            break
    if not drawing_rel_line:
        drawing_rel_line = (
            '<Relationship Id="rId2"'
            ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"'
            ' Target="../drawings/drawing1.xml"/>'
        )

    sheet1_rels_template = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + drawing_rel_line +
        '</Relationships>'
    )

    tmp = str(output_path) + ".tmp"
    with zipfile.ZipFile(str(output_path), "r") as src, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        existing = src.namelist()
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "xl/worksheets/_rels/sheet1.xml.rels":
                # substitui completamente pelo do template (tem rId correto)
                data = sheet1_rels_template.encode("utf-8")
            dst.writestr(item, data)
        # se o _rels nao existia no output, cria-o
        if "xl/worksheets/_rels/sheet1.xml.rels" not in existing:
            dst.writestr("xl/worksheets/_rels/sheet1.xml.rels",
                         sheet1_rels_template.encode("utf-8"))
        # adiciona ficheiros de drawing/media do template
        for fname, fdata in drawing_data.items():
            dst.writestr(fname, fdata)

    shutil.move(tmp, str(output_path))
    print("  Logo: copiado do template")


# ---- main --------------------------------------------------

def main():
    pasta_projeto = sys.argv[1] if len(sys.argv) > 1 else PASTA_PROJETO

    pasta    = encontrar_pasta_docs(pasta_projeto)
    template = Path(FSP_TEMPLATE)
    output   = Path(pasta_projeto) / "FSP_GERADO.xlsx"

    if not template.exists():
        raise SystemExit(f"ERRO: Template FSP nao encontrado: {template}")

    print("=" * 55)
    print("GERADOR DE FSP")
    print("=" * 55)
    print(f"Projeto: {pasta_projeto}")
    print(f"Pasta docs: {pasta}")

    lpa_path = encontrar_ultimo_lpa(pasta)
    dados    = ler_lpa(lpa_path)
    print(f"Projeto: {str(dados.get('projeto', ''))[:70]}")
    print(f"Expediente: {dados.get('expediente', '')}")
    print(f"Avaliadores: {iniciais_avaliadores(dados.get('avaliadores', []))}")
    print(f"Remitente: {dados.get('remitente', '')}")
    print(f"Docs avaliados: {len(dados['docs_avaliados'])}")

    arquivos = escanear_pasta(pasta)
    print(f"Ficheiros gerados: {len(arquivos)}")

    wb = openpyxl.load_workbook(template)
    print("\nPopulando sheets:")

    if "Portada" in wb.sheetnames:
        popular_portada(wb["Portada"], dados)

    aba_envios = next((s for s in wb.sheetnames if "envio" in s.lower()), None)
    if aba_envios:
        popular_envios(wb[aba_envios], dados)

    aba_aportados = next((s for s in wb.sheetnames if "aportado" in s.lower()), None)
    if aba_aportados:
        popular_doc_aportados(wb[aba_aportados], dados)

    aba_generados = next((s for s in wb.sheetnames if "generado" in s.lower()), None)
    if aba_generados:
        popular_doc_generados(wb[aba_generados], arquivos,
                              dados.get("versoes_lpa", []),
                              dados.get("avaliadores", []))

    print("  M.C.S.: mantida do template (preencher manualmente no final)")

    wb.save(output)
    copiar_imagem_template(template, output)

    print(f"\nGuardado em: {output.resolve()}")
    print("=" * 55)
    print("Proximos passos:")
    print("  1. Abre FSP_GERADO.xlsx e revisa cada aba")
    print("  2. Preenche M.C.S. no final do projeto")
    print("=" * 55)


if __name__ == "__main__":
    main()
