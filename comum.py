"""
comum.py - Funções e tabelas compartilhadas por todos os scripts do projeto
===========================================================================

FONTE ÚNICA de:
  - fmt                -> formata segundos como "1h05m"
  - CATEGORIAS / CAT_DISPLAY / categoria_de / rotulo_categoria
  - PROJ_RE / PROJ_NOMES / projeto_de
  - CORES
  - IGNORAR
  - normalizar_titulo  -> usada pelo tracker p/ agrupar sessões

Antes este código estava DUPLICADO (e já tinha divergido) entre report.py e
report_html.py. Agora todos importam daqui.

Mantido SEM dependências externas (só biblioteca padrão), igual ao resto do
projeto.
"""

import re


# ---------------------------------------------------------------------------
# Formatação de tempo
# ---------------------------------------------------------------------------
def fmt(segundos) -> str:
    """Formata uma quantidade de segundos como '1h05m', '5m30s' ou '42s'."""
    h, resto = divmod(int(segundos), 3600)
    m, s = divmod(resto, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


# ---------------------------------------------------------------------------
# Categorias de aplicativos
# ---------------------------------------------------------------------------
# As CHAVES são "internas" (sem acento) para casar com CORES e evitar
# divergências de digitação. O texto bonito para exibir vem de CAT_DISPLAY.
CATEGORIAS = {
    "trabalho/estudo": ["code.exe", "winword.exe", "excel.exe", "powerpnt.exe",
                        "acrobat.exe", "acrord32.exe", "matlab.exe", "rstudio.exe",
                        "python.exe", "pycharm", "notepad++.exe", "notepad.exe",
                        "windowsterminal.exe", "claude.exe", "explorer.exe"],
    "reuniao": ["teams.exe", "ms-teams.exe", "granola.exe", "zoom.exe"],
    "comunicacao": ["outlook.exe", "slack.exe", "discord.exe", "whatsapp.exe",
                    "telegram.exe"],
    "navegador": ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"],
    "distracao": ["spotify.exe", "steam.exe", "vlc.exe"],
}

# Rótulos "bonitos" (com acento) para exibir no terminal e no HTML.
# Chave interna -> texto exibido. Categorias sem entrada aqui usam a própria chave.
CAT_DISPLAY = {
    "trabalho/estudo": "Trabalho/Estudo",
    "reuniao": "Reunião",
    "comunicacao": "Comunicação",
    "navegador": "Navegador",
    "distracao": "Distração",
    "outros": "Outros",
}


def categoria_de(app: str) -> str:
    """Chave interna da categoria de um executável (ex.: 'comunicacao')."""
    a = (app or "").lower()
    for cat, apps in CATEGORIAS.items():
        if any(p in a for p in apps):
            return cat
    return "outros"


def rotulo_categoria(cat: str) -> str:
    """Texto bonito (com acento) para exibir uma categoria."""
    return CAT_DISPLAY.get(cat, cat)


# ---------------------------------------------------------------------------
# Projetos (código de obra ou nome de empresa no título da janela)
# ---------------------------------------------------------------------------
PROJ_RE = re.compile(r"20\d{2}[-_]\d{3,5}")
PROJ_NOMES = ["DRAGADOS", "SYNEOX", "SICE", "AECOM", "ESTEYCO", "ALEGIA", "AMEYUGO"]


def projeto_de(titulo: str) -> str:
    """Tenta inferir o projeto a partir do título da janela."""
    t = titulo or ""
    m = PROJ_RE.search(t)
    if m:
        return m.group(0).replace("_", "-")
    up = t.upper()
    for nome in PROJ_NOMES:
        if nome in up:
            return nome.capitalize()
    return "(sem projeto)"


# ---------------------------------------------------------------------------
# Cores por categoria (usadas no relatório HTML) — chaveadas pela chave interna
# ---------------------------------------------------------------------------
CORES = {"trabalho/estudo": "#22a06b", "reuniao": "#f59e0b", "comunicacao": "#8b5cf6",
         "navegador": "#4f8cff", "distracao": "#ef4444", "outros": "#9ca3af"}


# ---------------------------------------------------------------------------
# Apps de "ruído" do Windows que não interessam nos relatórios
# ---------------------------------------------------------------------------
IGNORAR = {"lockapp.exe", "shellexperiencehost.exe", "openwith.exe",
           "pickerhost.exe", "shellhost.exe", "searchhost.exe",
           "startmenuexperiencehost.exe", "(desconhecido)"}


# ---------------------------------------------------------------------------
# Normalização de título (para agrupar sessões no tracker)
# ---------------------------------------------------------------------------
# Contadores de não-lidos como "(3) WhatsApp" ou "(12) Caixa de Entrada".
_CONTADOR_RE = re.compile(r"\(\d+\)\s*")


def normalizar_titulo(titulo: str) -> str:
    """
    Normaliza o título para COMPARAR sessões: remove contadores '(N)' (ex.:
    notificações de não-lidos, que mudam o tempo todo e fragmentariam as
    sessões) e colapsa espaços. Mantém o resto intacto — códigos de obra como
    '2026-1234' não estão entre parênteses, então não são afetados.

    Conservadora de propósito: não tenta adivinhar título de players de vídeo
    (isso pode ser refinado depois, por app). O valor retornado também serve
    como título "representativo" para exibição.
    """
    t = _CONTADOR_RE.sub("", titulo or "")
    return " ".join(t.split())
