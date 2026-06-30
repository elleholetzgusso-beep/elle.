"""
tracker.py - Rastreador de atividade local para Windows
========================================================

Registra qual aplicativo e janela estão em foco e se você está ocioso (sem
mexer no mouse/teclado). Tudo fica em um banco SQLite LOCAL
(%LOCALAPPDATA%/produtividade/dados/atividade.db). Nada sai do seu computador.

NÃO captura conteúdo (o que você digita, textos, senhas). Só o NOME do app,
o TÍTULO da janela e o tempo.

AGREGAÇÃO POR SESSÃO
--------------------
Em vez de gravar uma linha a cada tick (~2000 linhas/dia, muitas idênticas em
sequência), o tracker trabalha por SESSÃO: enquanto você permanece no mesmo
app + título (normalizado) e no mesmo estado (ativo/ocioso), UMA única linha
cresce — somando 'duracao' e estendendo 'ts_fim' a cada tick. Ao trocar de
contexto, a linha é fechada e outra é aberta.

A linha é gravada já no INÍCIO da sessão e atualizada a cada tick, então se o
tracker fechar de repente você perde no máximo os últimos `intervalo` segundos.

Como usar:
    python tracker.py            # roda em primeiro plano (Ctrl+C para parar)
    python tracker.py --intervalo 10   # muda o intervalo de captura (segundos)

Sem dependências externas: usa só a biblioteca padrão + ctypes (Windows).
"""

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import socket
import sqlite3
import sys
import time
from datetime import datetime

# Classificação na ORIGEM e normalização de título vêm do módulo comum
from comum import categoria_de, projeto_de, normalizar_titulo, fmt

# Nome desta máquina (para consolidar dados de vários PCs depois)
MAQUINA = socket.gethostname()

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Dados ficam em %LOCALAPPDATA% (pasta LOCAL, fora do OneDrive — não sincroniza p/ nuvem)
DADOS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", BASE_DIR), "produtividade", "dados")
DB_PATH = os.path.join(DADOS_DIR, "atividade.db")

# Tempo (em segundos) sem input para considerar que você está OCIOSO
LIMITE_OCIOSO = 120

# ---------------------------------------------------------------------------
# Win32 via ctypes (sem instalar nada)
# ---------------------------------------------------------------------------
# O binding fica atrás deste guard para que o módulo possa ser IMPORTADO em
# outros sistemas (ex.: para testar a lógica de DB/sessão). A captura real só
# roda no Windows, onde estas funções são de fato chamadas.
if sys.platform == "win32":
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]


def segundos_ocioso() -> float:
    """Quantos segundos desde o último input (mouse/teclado)."""
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    user32.GetLastInputInfo(ctypes.byref(info))
    millis = kernel32.GetTickCount() - info.dwTime
    return millis / 1000.0


def janela_em_foco() -> tuple[str, str]:
    """Retorna (nome_do_processo, titulo_da_janela) da janela ativa."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ("", "")

    # Título da janela
    tamanho = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(tamanho + 1)
    user32.GetWindowTextW(hwnd, buffer, tamanho + 1)
    titulo = buffer.value

    # PID -> nome do executável
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    processo = nome_do_processo(pid.value)

    return (processo, titulo)


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def nome_do_processo(pid: int) -> str:
    """Resolve o nome do executável a partir do PID."""
    if not pid:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(512)
        tamanho = wt.DWORD(512)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(tamanho)):
            return os.path.basename(buffer.value)
        return ""
    finally:
        kernel32.CloseHandle(handle)


# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------
def init_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS atividade (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        TEXT NOT NULL,      -- início do bloco/sessão (ISO)
            app       TEXT,               -- nome do executável
            titulo    TEXT,               -- título (normalizado) da janela
            ocioso    INTEGER NOT NULL,   -- 1 = ocioso, 0 = ativo
            duracao   INTEGER NOT NULL,   -- soma de segundos do bloco
            maquina   TEXT,               -- nome do PC de origem
            ts_fim    TEXT,               -- fim do bloco (ISO) — atualizado a cada tick
            projeto   TEXT,               -- projeto inferido (comum.projeto_de)
            categoria TEXT                -- categoria inferida (comum.categoria_de)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON atividade(ts)")
    # Migração incremental: garante que bancos antigos ganhem as colunas novas,
    # checando PRAGMA table_info (mesmo padrão que já era usado para 'maquina').
    # Bancos antigos continuam legíveis: as colunas novas ficam NULL no histórico.
    cols = [c[1] for c in conn.execute("PRAGMA table_info(atividade)").fetchall()]
    for nome, tipo in (("maquina", "TEXT"), ("ts_fim", "TEXT"),
                       ("projeto", "TEXT"), ("categoria", "TEXT")):
        if nome not in cols:
            conn.execute(f"ALTER TABLE atividade ADD COLUMN {nome} {tipo}")
    conn.commit()
    return conn


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def abrir_sessao(conn, app, titulo, ocioso, duracao) -> dict:
    """
    Cria UMA linha nova para um bloco de atividade (já grava no início) e
    devolve o estado da sessão para os próximos ticks atualizarem.
    'projeto' e 'categoria' são calculados aqui, na ORIGEM.
    """
    projeto = projeto_de(titulo)
    categoria = categoria_de(app)
    agora = _agora()
    cur = conn.execute(
        "INSERT INTO atividade "
        "(ts, app, titulo, ocioso, duracao, maquina, ts_fim, projeto, categoria) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (agora, app, titulo, int(ocioso), duracao, MAQUINA, agora, projeto, categoria),
    )
    conn.commit()
    return {"id": cur.lastrowid, "app": app, "titulo": titulo,
            "ocioso": int(ocioso), "duracao": duracao,
            "projeto": projeto, "categoria": categoria}


def atualizar_sessao(conn, sessao, duracao) -> None:
    """Soma mais tempo ao bloco atual e estende seu ts_fim."""
    sessao["duracao"] += duracao
    conn.execute(
        "UPDATE atividade SET duracao = ?, ts_fim = ? WHERE id = ?",
        (sessao["duracao"], _agora(), sessao["id"]),
    )
    conn.commit()


def mesma_sessao(sessao, app, titulo, ocioso) -> bool:
    """True se o contexto atual pertence à mesma sessão já aberta."""
    return (sessao is not None
            and sessao["app"] == app
            and sessao["titulo"] == titulo
            and sessao["ocioso"] == int(ocioso))


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Rastreador de atividade local")
    parser.add_argument("--intervalo", type=int, default=15,
                        help="Segundos entre cada captura (padrão: 15)")
    args = parser.parse_args()

    conn = init_db()
    print(f"[tracker] Gravando em: {DB_PATH}")
    print(f"[tracker] Intervalo: {args.intervalo}s | Ocioso após: {LIMITE_OCIOSO}s sem input")
    print("[tracker] Rodando... (Ctrl+C para parar)\n")

    sessao = None
    try:
        while True:
            ocioso = segundos_ocioso() >= LIMITE_OCIOSO
            app, titulo_bruto = janela_em_foco()
            titulo = normalizar_titulo(titulo_bruto)

            # Mesmo contexto -> cresce a linha atual; senão -> abre nova sessão.
            if mesma_sessao(sessao, app, titulo, ocioso):
                atualizar_sessao(conn, sessao, args.intervalo)
            else:
                sessao = abrir_sessao(conn, app, titulo, ocioso, args.intervalo)

            estado = "OCIOSO" if ocioso else "ativo "
            print(f"  {datetime.now():%H:%M:%S} [{estado}] {app:<22} | "
                  f"{titulo[:46]}  ({fmt(sessao['duracao'])})")
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("\n[tracker] Parado. Dados salvos.")
    finally:
        conn.close()


if __name__ == "__main__":
    if sys.platform != "win32":
        print("Este tracker é específico para Windows.")
        sys.exit(1)
    main()
