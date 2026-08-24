#!/usr/bin/env python3
"""Monta uma planilha Excel com a lista de documentos, titulos, versoes e conteudo.

Complementa o extrair_arquivos.py: depois de juntar tudo em uma pasta so,
este script le cada documento e gera um .xlsx com uma linha por arquivo.

Nao mexe em nada: so le a pasta (com todas as subpastas) e escreve o .xlsx.

Dois modos:
    lista completa  - le titulo, versao, paginas e conteudo de cada documento
    --so-nomes      - so nomes, caminhos e dados dos arquivos, bem mais rapido

Formatos com leitura de texto: .pdf, .docx, .txt, .md, .csv, .xlsx
Os demais entram na lista apenas com os dados do arquivo.

Instalacao das bibliotecas:
    pip install openpyxl pypdf python-docx

Exemplos:
    python listar_documentos.py "Tarragona A"
    python listar_documentos.py pasta/ lista.xlsx --limite-conteudo 5000
    python listar_documentos.py pasta/ lista.xlsx --so-nomes
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import re
import sys
from pathlib import Path

# O pypdf reclama alto de PDFs meio quebrados; os erros ja sao tratados aqui.
logging.getLogger("pypdf").setLevel(logging.ERROR)

AVISO_INSTALACAO = ("falta a biblioteca openpyxl. Instale com:\n"
                    "    pip install openpyxl pypdf python-docx")
try:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
except ImportError:  # o app avisa na tela em vez de quebrar na abertura
    openpyxl = None

# Excel nao aceita celulas maiores que isso nem caracteres de controle.
LIMITE_CELULA = 32_767
CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

TEXTO_SIMPLES = {".txt", ".md", ".csv", ".log", ".json", ".xml", ".html", ".htm"}

# Titulos de metadados que nao dizem nada e viram fallback para a primeira linha.
TITULOS_INUTEIS = {"untitled", "sem titulo", "document", "documento", "doc1",
                   "document1", "planilha1", "pasta1", "apresentacao1", "titulo"}

# Padroes de versao/revisao no nome do arquivo, em ordem de prioridade.
# INICIO/FIM no lugar de \b porque o "_" conta como letra para o \b e
# nomes como "Memoria_Rev02" nao seriam reconhecidos.
INICIO = r"(?<![A-Za-z0-9])"
FIM = r"(?![A-Za-z0-9])"
PADROES_VERSAO = [
    re.compile(INICIO + r"(?:rev(?:is[aã]o)?|rv)[\s._-]*([0-9]{1,3}(?:\.[0-9]{1,2})?)" + FIM, re.I),
    re.compile(INICIO + r"(?:rev(?:is[aã]o)?)[\s._-]*([A-Z])" + FIM, re.I),
    re.compile(INICIO + r"(?:vers[aã]o|version|ver|v)[\s._-]*([0-9]{1,3}(?:\.[0-9]{1,2})?)" + FIM, re.I),
    re.compile(INICIO + r"(?:ed(?:i[cç][aã]o)?)[\s._-]*([0-9]{1,3})" + FIM, re.I),
    re.compile(r"\((\d{1,3})\)\s*$"),  # copias do Windows: documento (2).pdf
]

COLUNAS = [
    # (cabecalho, largura, chave do registro)
    ("#", 5, "indice"),
    ("Arquivo", 38, "arquivo"),
    ("Titulo", 38, "titulo"),
    ("Versao", 9, "versao"),
    ("Versoes", 9, "versoes"),
    ("Mais recente", 13, "recente"),
    ("Documento base", 32, "base_exibida"),
    ("Tipo", 8, "tipo"),
    ("Tamanho (KB)", 13, "tamanho"),
    ("Paginas", 9, "paginas"),
    ("Palavras", 10, "palavras"),
    ("Modificado em", 18, "modificado"),
    ("Pasta", 22, "pasta"),
    ("Caminho completo", 52, "caminho_completo"),
    ("Conteudo", 90, "conteudo"),
]

# Colunas que so fazem sentido quando o conteudo dos arquivos e lido.
COLUNAS_DE_CONTEUDO = {"titulo", "paginas", "palavras", "conteudo"}


def limpar(texto: str) -> str:
    """Tira caracteres que o Excel recusa e espacos sobrando."""
    return CONTROLE.sub(" ", texto).strip()


def primeira_linha(texto: str, maximo: int = 150) -> str:
    """Usa a primeira linha com conteudo como titulo aproximado."""
    for linha in texto.splitlines():
        limpa = limpar(linha).lstrip("#").strip()
        if len(limpa) > 2:
            return limpa[:maximo]
    return ""


def titulo_util(titulo: str, caminho: Path) -> str:
    """Descarta titulos de metadados vazios ou genericos."""
    limpo = limpar(titulo)
    # "Microsoft Word - CONTRATO.doc" -> "CONTRATO"
    limpo = re.sub(r"^Microsoft\s+\w+\s*-\s*", "", limpo, flags=re.I)
    limpo = re.sub(r"\.(docx?|pdf|xlsx?|pptx?)$", "", limpo, flags=re.I).strip()
    if not limpo or limpo.lower() in TITULOS_INUTEIS:
        return ""
    if limpo.lower() == caminho.stem.lower():
        return ""
    return limpo


def detectar_versao(nome: str, conteudo: str = "") -> str:
    """Procura a versao/revisao no nome do arquivo e, se faltar, no inicio do texto."""
    for padrao in PADROES_VERSAO:
        achado = padrao.search(nome)
        if achado:
            return achado.group(1).upper()
    for padrao in PADROES_VERSAO[:2]:
        achado = padrao.search(conteudo[:800])
        if achado:
            return achado.group(1).upper()
    return ""


def documento_base(nome: str) -> str:
    """Nome sem a versao, usado para agrupar as varias versoes do mesmo documento."""
    base = nome
    for padrao in PADROES_VERSAO:
        base = padrao.sub(" ", base)
    base = re.sub(r"[\s._-]+", " ", base).strip(" .-_")
    return base or nome


def ordem_versao(versao: str) -> tuple[int, float]:
    """Chave de ordenacao: numeros antes de letras, vazio por ultimo."""
    if not versao:
        return (-1, 0.0)
    try:
        return (1, float(versao))
    except ValueError:
        return (0, float(sum(ord(c) for c in versao)))


def ler_pdf(caminho: Path) -> tuple[str, str, int | None]:
    from pypdf import PdfReader

    leitor = PdfReader(str(caminho))
    if leitor.is_encrypted:
        try:
            leitor.decrypt("")
        except Exception:
            return "", "(PDF protegido por senha)", None

    partes = []
    for pagina in leitor.pages:
        try:
            partes.append(pagina.extract_text() or "")
        except Exception:
            continue
    conteudo = "\n".join(partes)

    titulo = ""
    try:
        if leitor.metadata and leitor.metadata.title:
            titulo = titulo_util(str(leitor.metadata.title), caminho)
    except Exception:
        pass
    return titulo or primeira_linha(conteudo), conteudo, len(leitor.pages)


def ler_docx(caminho: Path) -> tuple[str, str, int | None]:
    import docx

    documento = docx.Document(str(caminho))
    partes = [p.text for p in documento.paragraphs if p.text.strip()]
    for tabela in documento.tables:
        for linha in tabela.rows:
            celulas = [c.text.strip() for c in linha.cells if c.text.strip()]
            if celulas:
                partes.append(" | ".join(celulas))
    conteudo = "\n".join(partes)

    titulo = ""
    try:
        titulo = titulo_util(documento.core_properties.title or "", caminho)
    except Exception:
        pass
    if not titulo:
        for paragrafo in documento.paragraphs:
            if paragrafo.style.name.startswith("Heading") and paragrafo.text.strip():
                titulo = limpar(paragrafo.text)
                break
    return titulo or primeira_linha(conteudo), conteudo, None


def ler_xlsx(caminho: Path) -> tuple[str, str, int | None]:
    livro = openpyxl.load_workbook(str(caminho), read_only=True, data_only=True)
    partes = []
    for aba in livro.worksheets:
        partes.append(f"[{aba.title}]")
        for linha in aba.iter_rows(max_row=200, values_only=True):
            valores = [str(v) for v in linha if v is not None]
            if valores:
                partes.append(" | ".join(valores))
    titulo = titulo_util(livro.properties.title or "", caminho) if livro.properties else ""
    paginas = len(livro.worksheets)
    livro.close()
    return titulo, "\n".join(partes), paginas


def ler_texto(caminho: Path) -> tuple[str, str, int | None]:
    for codificacao in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            conteudo = caminho.read_text(encoding=codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        return "", "(nao foi possivel ler o texto)", None
    return primeira_linha(conteudo), conteudo, None


def extrair_documento(caminho: Path) -> tuple[str, str, int | None, str]:
    """Devolve (titulo, conteudo, paginas, aviso) de acordo com a extensao."""
    extensao = caminho.suffix.lower()
    try:
        if extensao == ".pdf":
            titulo, conteudo, paginas = ler_pdf(caminho)
        elif extensao == ".docx":
            titulo, conteudo, paginas = ler_docx(caminho)
        elif extensao in {".xlsx", ".xlsm"}:
            titulo, conteudo, paginas = ler_xlsx(caminho)
        elif extensao in TEXTO_SIMPLES:
            titulo, conteudo, paginas = ler_texto(caminho)
        elif extensao in {".doc", ".rtf", ".odt", ".ppt", ".pptx"}:
            return "", "", None, "formato sem leitura de texto (converta para PDF ou DOCX)"
        else:
            return "", "", None, ""
    except ImportError as erro:
        falta = "pypdf" if extensao == ".pdf" else "python-docx"
        return "", "", None, f"instale {falta} para ler este arquivo ({erro})"
    except Exception as erro:  # arquivo corrompido, protegido, etc.
        return "", "", None, f"erro ao ler: {type(erro).__name__}"

    return titulo, conteudo, paginas, ""


def listar_arquivos(pasta: Path, saida: Path, extensoes: set[str] | None,
                    incluir_ocultos: bool) -> list[Path]:
    arquivos = []
    for caminho in sorted(pasta.rglob("*")):
        if not caminho.is_file() or caminho.resolve() == saida.resolve():
            continue
        partes = caminho.relative_to(pasta).parts
        if not incluir_ocultos and any(p.startswith(".") for p in partes):
            continue
        if extensoes and caminho.suffix.lower() not in extensoes:
            continue
        arquivos.append(caminho)
    return arquivos


def montar_planilha(pasta: Path, saida: Path, extensoes: set[str] | None,
                    limite_conteudo: int, sem_conteudo: bool,
                    incluir_ocultos: bool, log=print, progresso=None) -> int:
    """Gera a planilha. `log` recebe as mensagens e `progresso` recebe (feitos, total)."""
    if openpyxl is None:
        log(f"erro: {AVISO_INSTALACAO}")
        return 1
    if not pasta.is_dir():
        log(f"erro: pasta nao encontrada: {pasta}")
        return 1

    arquivos = listar_arquivos(pasta, saida, extensoes, incluir_ocultos)
    if not arquivos:
        log("Nenhum arquivo encontrado com esses filtros.")
        return 0

    log("Modo: so nomes e caminhos (sem ler o conteudo)." if sem_conteudo
        else "Modo: lista completa (lendo o conteudo dos documentos).")

    registros = []
    for indice, caminho in enumerate(arquivos, start=1):
        log(f"  [{indice}/{len(arquivos)}] {caminho.name}")
        if progresso:
            progresso(indice, len(arquivos))

        if sem_conteudo:
            titulo, conteudo, paginas, aviso = "", "", None, ""
        else:
            titulo, conteudo, paginas, aviso = extrair_documento(caminho)

        conteudo = limpar(conteudo)
        estatistica = caminho.stat()
        relativa = caminho.relative_to(pasta).parent
        versao = detectar_versao(caminho.stem, conteudo)

        registros.append({
            "caminho": caminho,
            "indice": indice,
            "arquivo": caminho.name,
            "caminho_completo": str(caminho),
            "titulo": limpar(titulo) or caminho.stem,
            "versao": versao,
            "base": documento_base(caminho.stem).lower(),
            "base_exibida": documento_base(caminho.stem),
            "tipo": (caminho.suffix.lower().lstrip(".") or "(sem)"),
            "tamanho": round(estatistica.st_size / 1024, 1),
            "paginas": paginas,
            "palavras": len(conteudo.split()) if conteudo else None,
            "modificado": dt.datetime.fromtimestamp(estatistica.st_mtime),
            "pasta": str(relativa) if str(relativa) != "." else "",
            "conteudo": conteudo,
            "aviso": aviso,
        })

    # Agrupa por documento base para contar versoes e marcar a mais recente.
    grupos: dict[str, list[dict]] = {}
    for registro in registros:
        grupos.setdefault(registro["base"], []).append(registro)
    for itens in grupos.values():
        for registro in itens:
            registro["versoes"] = len(itens)
        mais_recente = max(itens, key=lambda r: (ordem_versao(r["versao"]), r["modificado"]))
        for registro in itens:
            registro["recente"] = "Sim" if registro is mais_recente else "Nao"

    livro = openpyxl.Workbook()
    aba = livro.active
    aba.title = "Documentos"

    # No modo "so nomes e caminhos" as colunas de conteudo nem aparecem.
    colunas = [c for c in COLUNAS if not (sem_conteudo and c[2] in COLUNAS_DE_CONTEUDO)]

    cabecalho_fonte = Font(bold=True, color="FFFFFF")
    cabecalho_fundo = PatternFill("solid", fgColor="305496")
    destaque = PatternFill("solid", fgColor="FFF2CC")
    for coluna, (nome, largura, _chave) in enumerate(colunas, start=1):
        celula = aba.cell(row=1, column=coluna, value=nome)
        celula.font = cabecalho_fonte
        celula.fill = cabecalho_fundo
        celula.alignment = Alignment(horizontal="center", vertical="center")
        aba.column_dimensions[get_column_letter(coluna)].width = largura

    limite = min(limite_conteudo, LIMITE_CELULA - 20)
    avisos = 0
    contagem_tipos: dict[str, int] = {}
    colunas_versao = {"versao", "versoes", "recente", "base_exibida"}

    for indice, registro in enumerate(registros, start=1):
        if registro["aviso"]:
            avisos += 1
        contagem_tipos[registro["tipo"]] = contagem_tipos.get(registro["tipo"], 0) + 1

        linha = indice + 1
        for coluna, (_nome, _largura, chave) in enumerate(colunas, start=1):
            valor = registro.get(chave)
            if chave == "tipo":
                valor = str(valor).upper()
            elif chave == "conteudo":
                valor = valor or registro["aviso"]
                if len(valor) > limite:
                    valor = valor[:limite] + "... (truncado)"
            celula = aba.cell(row=linha, column=coluna, value=valor)

            if chave == "arquivo":
                celula.hyperlink = registro["caminho"].resolve().as_uri()
                celula.font = Font(color="0563C1", underline="single")
            elif chave == "modificado":
                celula.number_format = "dd/mm/yyyy hh:mm"
            elif chave == "versoes":
                celula.alignment = Alignment(horizontal="center")
            elif chave == "conteudo":
                celula.alignment = Alignment(wrap_text=True, vertical="top")
            # Amarelo nas linhas que tem mais de uma versao do mesmo documento.
            if chave in colunas_versao and registro["versoes"] > 1:
                celula.fill = destaque

    aba.freeze_panes = "C2"
    aba.auto_filter.ref = f"A1:{get_column_letter(len(colunas))}{len(registros) + 1}"

    escrever_resumo(livro, contagem_tipos, registros, grupos,
                    cabecalho_fonte, cabecalho_fundo)

    saida.parent.mkdir(parents=True, exist_ok=True)
    try:
        livro.save(saida)
    except PermissionError:
        log(f"erro: nao foi possivel salvar {saida.name}. "
            "Feche o arquivo no Excel e rode de novo.")
        return 1

    com_varias = sum(1 for itens in grupos.values() if len(itens) > 1)
    log("")
    log(f"Planilha criada: {saida}")
    log(f"Documentos listados: {len(registros)}")
    log(f"Documentos distintos: {len(grupos)}")
    if com_varias:
        log(f"Documentos com mais de uma versao: {com_varias}")
    if avisos:
        log(f"Arquivos sem leitura de conteudo: {avisos}")
    return 0


def escrever_resumo(livro, contagem_tipos: dict[str, int], registros: list[dict],
                    grupos: dict[str, list[dict]], fonte, fundo) -> None:
    resumo = livro.create_sheet("Resumo")
    resumo["A1"], resumo["B1"] = "Tipo", "Quantidade"
    for celula in ("A1", "B1"):
        resumo[celula].font = fonte
        resumo[celula].fill = fundo

    linha = 2
    for tipo, quantidade in sorted(contagem_tipos.items(), key=lambda x: -x[1]):
        resumo.cell(row=linha, column=1, value=tipo.upper())
        resumo.cell(row=linha, column=2, value=quantidade)
        linha += 1
    resumo.cell(row=linha, column=1, value="TOTAL").font = Font(bold=True)
    resumo.cell(row=linha, column=2, value=len(registros)).font = Font(bold=True)

    linha += 2
    resumo.cell(row=linha, column=1, value="Documentos distintos")
    resumo.cell(row=linha, column=2, value=len(grupos))
    linha += 1
    resumo.cell(row=linha, column=1, value="Com mais de uma versao")
    resumo.cell(row=linha, column=2,
                value=sum(1 for itens in grupos.values() if len(itens) > 1))
    linha += 1
    resumo.cell(row=linha, column=1, value="Sem versao identificada")
    resumo.cell(row=linha, column=2,
                value=sum(1 for r in registros if not r["versao"]))

    linha += 2
    resumo.cell(row=linha, column=1, value="Documento base").font = fonte
    resumo.cell(row=linha, column=1).fill = fundo
    resumo.cell(row=linha, column=2, value="Versoes").font = fonte
    resumo.cell(row=linha, column=2).fill = fundo
    resumo.cell(row=linha, column=3, value="Versoes encontradas").font = fonte
    resumo.cell(row=linha, column=3).fill = fundo
    linha += 1
    for itens in sorted(grupos.values(), key=lambda x: (-len(x), x[0]["base"])):
        if len(itens) < 2:
            continue
        versoes = sorted({r["versao"] or "?" for r in itens}, key=ordem_versao)
        resumo.cell(row=linha, column=1, value=itens[0]["base_exibida"])
        resumo.cell(row=linha, column=2, value=len(itens))
        resumo.cell(row=linha, column=3, value=", ".join(versoes))
        linha += 1

    resumo.column_dimensions["A"].width = 38
    resumo.column_dimensions["B"].width = 14
    resumo.column_dimensions["C"].width = 30


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Monta um Excel com a lista de documentos, titulos, versoes e conteudo.")
    parser.add_argument("pasta", type=Path, help="pasta com os documentos")
    parser.add_argument("saida", type=Path, nargs="?", default=Path("lista_documentos.xlsx"),
                        help="arquivo .xlsx de saida (padrao: lista_documentos.xlsx)")
    parser.add_argument("--ext", nargs="+", metavar="EXT",
                        help="extensoes a incluir, ex: --ext .pdf .docx")
    parser.add_argument("--limite-conteudo", type=int, default=2000,
                        help="maximo de caracteres do conteudo por linha (padrao: 2000)")
    parser.add_argument("--so-nomes", "--sem-conteudo", dest="sem_conteudo",
                        action="store_true",
                        help="lista so nomes, caminhos e dados dos arquivos, "
                             "sem abrir o conteudo (bem mais rapido)")
    parser.add_argument("--incluir-ocultos", action="store_true",
                        help="tambem lista arquivos e pastas que comecam com ponto")
    args = parser.parse_args(argv)

    if openpyxl is None:
        print(f"erro: {AVISO_INSTALACAO}", file=sys.stderr)
        return 1

    extensoes = None
    if args.ext:
        extensoes = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in args.ext}

    saida = args.saida.expanduser()
    if saida.suffix.lower() not in {".xlsx", ".xlsm"}:
        saida = saida.with_suffix(".xlsx")

    return montar_planilha(
        pasta=args.pasta.expanduser().resolve(),
        saida=saida.resolve(),
        extensoes=extensoes,
        limite_conteudo=max(0, args.limite_conteudo),
        sem_conteudo=args.sem_conteudo,
        incluir_ocultos=args.incluir_ocultos,
    )


if __name__ == "__main__":
    raise SystemExit(main())
