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
import zipfile
from pathlib import Path

try:  # dependência opcional: só é precisa para .pdf
    import pypdf  # type: ignore

    PDF_OK = True
except Exception:  # noqa: BLE001
    PDF_OK = False

LEGIVEIS = (".docx", ".pdf", ".txt", ".md")


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


def _pdf_text(path: str | Path) -> str:
    """Texto de um .pdf via pypdf. "" se pypdf não estiver instalado/ilegível."""
    if not PDF_OK:
        return ""
    try:
        reader = pypdf.PdfReader(str(path))
        return "\n".join((pg.extract_text() or "") for pg in reader.pages)
    except Exception:  # noqa: BLE001
        return ""


def _txt_text(path: str | Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        return ""


def extract_text(path: str | Path) -> str:
    """Texto do ficheiro conforme a extensão. "" se ilegível ou tipo não suportado.

    Nota: um .pdf só é lido se ``pypdf`` estiver instalado (``PDF_OK``). Sem ele,
    devolve "" — o chamador deve avisar (ver ``motivo_vazio``).
    """
    suf = Path(path).suffix.lower()
    if suf == ".docx":
        return _docx_text(path)
    if suf == ".pdf":
        return _pdf_text(path)
    if suf in (".txt", ".md"):
        return _txt_text(path)
    return ""


def motivo_vazio(path: str | Path) -> str:
    """Explica por que ``extract_text`` devolveu "" (para mensagens ao utilizador)."""
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
