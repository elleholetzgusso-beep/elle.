"""Leitura do texto de documentos recebidos (.docx / .pdf / .txt).

Base comum dos comandos ``leer`` (1º LPA) e ``verify`` (ciclo de resposta).

Filosofia — igual ao resto do lpa_filler: **determinístico e sem julgamento**.
O módulo traz o *conteúdo* dos ficheiros à superfície (texto, apartado citado,
diff entre versões) para o avaliador localizar e comparar a evidência. Nunca
interpreta se um requisito foi cumprido nem fecha um hallazgo — isso é
competência do avaliador (ISO 17020).

``.docx`` lê-se via XML em bruto (sem obrigar ``python-docx``); ``.pdf`` usa
``pypdf`` se estiver instalado (``pip install lpa-filler[pdf]``). Um ficheiro
ilegível devolve "" — o chamador decide o que fazer (nunca rebenta o fluxo).
"""
from __future__ import annotations

import difflib
import html
import re
import threading
import zipfile
from pathlib import Path

try:  # dependência opcional: só é precisa para .pdf
    import pypdf  # type: ignore

    PDF_OK = True
except Exception:  # noqa: BLE001
    PDF_OK = False

LEGIVEIS = (".docx", ".pdf", ".txt", ".md")

# Abaixo disto não há conteúdo que se possa analisar. Quase sempre é uma
# digitalização — imagem sem camada de texto — que o pypdf "leu" com êxito e
# devolveu com meia dúzia de caracteres. Sem este limiar passava como documento
# lido: o checklist do `leer` dava tudo por ausente e o `radar` não tinha nada
# para cruzar, ambos sem um único aviso.
MIN_TEXTO_UTIL = 200

# Tempo máximo (segundos) para extrair texto de UM .pdf. PDFs com estrutura
# interna corrompida (comuns em digitalizações) podem deixar o pypdf a tentar
# recuperar-se por muito tempo. Corre-se a extração numa thread `daemon`: se
# exceder o limite, desiste-se e segue-se para o próximo ficheiro — a thread
# fica a correr sozinha em segundo plano (não bloqueia o resto do programa
# nem a saída do processo, ao contrário de um ThreadPoolExecutor).
PDF_TIMEOUT_S = 25

# path (str) -> motivo do último erro/timeout, para o motivo_vazio() explicar
# sem ter de repetir a extração (que pode ser lenta).
_ULTIMO_ERRO: dict[str, str] = {}


def _docx_text(path: str | Path) -> str:
    """Texto de um .docx preservando quebras de parágrafo (via XML em bruto)."""
    try:
        xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return ""
    # Cada <w:p> é um parágrafo; dentro dele, os <w:t> são os fragmentos de texto.
    paras = re.split(r"</w:p>", xml)
    linhas = []
    for p in paras:
        frags = re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S)
        texto = "".join(html.unescape(re.sub(r"<[^>]+>", "", f)) for f in frags)
        if texto.strip():
            linhas.append(texto.strip())
    return "\n".join(linhas)


def _pdf_text_worker(path: str | Path, saida: list) -> None:
    try:
        reader = pypdf.PdfReader(str(path))
        saida.append(("ok", "\n".join((pg.extract_text() or "") for pg in reader.pages)))
    except Exception as e:  # noqa: BLE001
        saida.append(("erro", f"{type(e).__name__}: {e}"))


def _pdf_text(path: str | Path) -> str:
    """Texto de um .pdf via pypdf, com timeout de segurança (``PDF_TIMEOUT_S``).

    "" se pypdf não estiver instalado, o ficheiro for ilegível, ou a extração
    exceder o tempo limite (PDF corrompido) — o motivo fica em ``motivo_vazio``.
    """
    if not PDF_OK:
        return ""
    key = str(path)
    saida: list = []
    t = threading.Thread(target=_pdf_text_worker, args=(path, saida), daemon=True)
    t.start()
    t.join(PDF_TIMEOUT_S)
    if t.is_alive():
        _ULTIMO_ERRO[key] = (
            f"extração excedeu {PDF_TIMEOUT_S}s (ficheiro grande ou corrompido) — saltado"
        )
        return ""
    if saida and saida[0][0] == "ok":
        _ULTIMO_ERRO.pop(key, None)
        return saida[0][1]
    if saida:
        _ULTIMO_ERRO[key] = f"erro ao ler pdf: {saida[0][1]}"
    return ""


def _txt_text(path: str | Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return ""


# Texto já extraído nesta execução: path -> (mtime, tamanho, texto). O `leer` e o
# `radar` leem os mesmos ficheiros da mesma pasta recebida, um a seguir ao outro;
# sem isto, cada .pdf lento (até PDF_TIMEOUT_S) é pago duas vezes.
_CACHE: dict[str, tuple[float, int, str]] = {}


def _extract_text_sem_cache(path: str | Path) -> str:
    suf = Path(path).suffix.lower()
    if suf == ".docx":
        return _docx_text(path)
    if suf == ".pdf":
        return _pdf_text(path)
    if suf in (".txt", ".md"):
        return _txt_text(path)
    return ""


def extract_text(path: str | Path) -> str:
    """Texto do ficheiro conforme a extensão. "" se ilegível ou tipo não suportado.

    Nota: um .pdf só é lido se ``pypdf`` estiver instalado (``PDF_OK``). Sem ele,
    devolve "" — o chamador deve avisar (ver ``motivo_vazio``).

    Cacheado por (caminho, data de modificação, tamanho): chamar duas vezes sobre
    o mesmo ficheiro inalterado não volta a abri-lo nem a pagar o timeout do pdf.
    """
    chave = str(path)
    try:
        st = Path(path).stat()
        marca = (st.st_mtime, st.st_size)
    except OSError:
        marca = None

    if marca is not None:
        cache = _CACHE.get(chave)
        if cache is not None and cache[:2] == marca:
            return cache[2]

    texto = _extract_text_sem_cache(path)
    if marca is not None:
        _CACHE[chave] = (marca[0], marca[1], texto)
    return texto


def texto_utilizavel(texto: str) -> bool:
    """Se há texto que chegue para valer a pena analisar o documento.

    Não é um veredito sobre o documento — é sobre a *extração*. Um "não" quer
    dizer que nenhuma ferramenta o viu, e portanto que ninguém o analisou.
    """
    return len((texto or "").strip()) >= MIN_TEXTO_UTIL


def aviso_texto_curto(texto: str) -> str:
    """A nota a mostrar quando a extração deu quase nada. "" se deu que chegue."""
    n = len((texto or "").strip())
    if n == 0 or texto_utilizavel(texto):
        return ""
    return (
        f"solo {n} caracteres extraídos — probable digitalización sin capa de texto "
        f"(necesita OCR). Nada de este documento ha sido analizado: revisarlo a mano."
    )


def motivo_vazio(path: str | Path) -> str:
    """Explica por que ``extract_text`` devolveu "" (para mensagens ao utilizador)."""
    erro = _ULTIMO_ERRO.get(str(path))
    if erro:
        return erro
    suf = Path(path).suffix.lower()
    if suf not in LEGIVEIS:
        return f"tipo '{suf or '?'}' não legível (só {', '.join(LEGIVEIS)})"
    if suf == ".pdf" and not PDF_OK:
        return "pdf sem texto extraível — instala o suporte: pip install lpa-filler[pdf]"
    if not Path(path).exists():
        return "ficheiro não encontrado"
    return "sem texto extraível (pode ser digitalização/imagem — precisa de OCR)"


# ---------------------------------------------------------------------------
# Localização de apartados citados numa resposta ("corrigido no apartado 3.2")
# ---------------------------------------------------------------------------

# Números de secção: "3", "3.2", "3.2.1"; e páginas: "pág. 12".
_SECCION_RE = re.compile(r"\b(\d+(?:\.\d+){0,3})\b")
_PAGINA_RE = re.compile(r"\bp[áa]g(?:ina)?\.?\s*(\d+)", re.IGNORECASE)
# Palavras que, numa resposta, precedem uma referência a localização no documento.
_REF_HINT_RE = re.compile(
    r"\b(apartad|secci[oó]n|punt|clausul|cap[ií]tul|ep[íi]grafe|tabla|figura|anej|anex|p[áa]g)",
    re.IGNORECASE,
)


def referencias_citadas(texto: str) -> list[str]:
    """Extrai números de apartado/página que uma resposta menciona.

    Só considera números que venham logo a seguir a uma palavra-âncora
    (apartado/sección/punto/página/...), para não apanhar números soltos
    (datas, quantidades). Ex.: "corregido en el apartado 3.2 y la pág. 14"
    -> ["3.2", "14"]. Devolve a ordem de aparição, sem repetir.
    """
    out: list[str] = []
    for m in _REF_HINT_RE.finditer(texto or ""):
        cauda = texto[m.end(): m.end() + 25]
        sm = _SECCION_RE.search(cauda) or _PAGINA_RE.search(cauda)
        if sm and sm.group(1) not in out:
            out.append(sm.group(1))
    return out


def localizar_seccion(texto: str, numero: str, janela: int = 600) -> str | None:
    """Devolve o trecho do documento à volta do cabeçalho da secção ``numero``.

    Procura o número no início de uma linha (padrão de cabeçalho, ex. "3.2 Gestión
    de la seguridad"). Devolve essa linha + ``janela`` caracteres seguintes, ou
    ``None`` se não encontrar (a resposta cita algo que não existe no ficheiro —
    sinal a reportar). Determinístico: não adivinha, não reformata.
    """
    if not texto or not numero:
        return None
    num = re.escape(numero.strip())
    # Cabeçalho: início de linha, o número, e a seguir espaço/ponto/traço + letra.
    padrao = re.compile(rf"^\s*{num}[.\)\s\-–]+\S.*$", re.MULTILINE)
    m = padrao.search(texto)
    if not m:
        return None
    ini = m.start()
    return texto[ini: ini + janela].strip()


def diff_versoes(texto_antigo: str, texto_novo: str, contexto: int = 0) -> list[str]:
    """Linhas alteradas entre duas versões (formato +/-), ignorando o que ficou igual.

    Serve para ver o que MUDOU de facto entre a versão anterior e a nova de um
    documento — a evidência mais direta de que a UTE mexeu no ponto reclamado.
    Devolve as linhas com prefixo '+ ' (acrescentado) / '- ' (removido).
    """
    a = [l.strip() for l in (texto_antigo or "").splitlines() if l.strip()]
    b = [l.strip() for l in (texto_novo or "").splitlines() if l.strip()]
    out: list[str] = []
    for linha in difflib.unified_diff(a, b, n=contexto, lineterm=""):
        if linha.startswith("+++") or linha.startswith("---") or linha.startswith("@@"):
            continue
        if linha.startswith(("+", "-")):
            out.append(linha)
    return out
