"""
migrar.py - Compacta o histórico antigo (1 linha/tick) em SESSÕES
=================================================================

OPCIONAL e NÃO-DESTRUTIVO. Lê o banco atual (atividade.db, no formato antigo
de uma linha a cada tick) e gera um banco NOVO já no formato de sessões, com
as colunas 'ts_fim', 'projeto' e 'categoria' preenchidas. O banco original
NÃO é tocado.

Como funciona: percorre as linhas em ordem de tempo e funde linhas
CONSECUTIVAS que tenham o mesmo app + título normalizado + estado
(ativo/ocioso). Uma folga de tempo grande entre duas linhas (padrão: 5 min,
ex.: tracker desligado durante a noite) quebra a sessão, para não fundir
períodos distantes só porque o contexto era o mesmo.

Como usar:
    python migrar.py                         # atividade.db -> atividade-compacto.db
    python migrar.py --origem X --destino Y
    python migrar.py --gap 600               # folga máxima (s) p/ continuar a sessão
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timedelta

from comum import normalizar_titulo, projeto_de, categoria_de, fmt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DADOS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", BASE_DIR), "produtividade", "dados")
DB_PADRAO = os.path.join(DADOS_DIR, "atividade.db")
DESTINO_PADRAO = os.path.join(DADOS_DIR, "atividade-compacto.db")

GAP_PADRAO = 300  # segundos


def criar_schema(conn):
    """Cria a tabela 'atividade' no formato novo (idêntico ao do tracker)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS atividade (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        TEXT NOT NULL,
            app       TEXT,
            titulo    TEXT,
            ocioso    INTEGER NOT NULL,
            duracao   INTEGER NOT NULL,
            maquina   TEXT,
            ts_fim    TEXT,
            projeto   TEXT,
            categoria TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON atividade(ts)")


def ler_linhas(origem):
    """Lê as linhas do banco de origem em ordem de tempo (read-only)."""
    conn = sqlite3.connect(f"file:{origem}?mode=ro", uri=True)
    cols = [c[1] for c in conn.execute("PRAGMA table_info(atividade)").fetchall()]
    campo_maq = "maquina" if "maquina" in cols else "NULL"
    rows = conn.execute(
        f"SELECT ts, app, titulo, ocioso, duracao, {campo_maq} FROM atividade ORDER BY ts"
    ).fetchall()
    conn.close()
    return rows


def compactar(rows, gap_max):
    """Funde linhas consecutivas de mesmo contexto em sessões."""
    sessoes = []
    atual = None
    for ts, app, titulo, ocioso, dur, maq in rows:
        titn = normalizar_titulo(titulo)
        oc = int(ocioso or 0)
        dur = int(dur or 0)
        chave = (app, titn, oc, maq)
        ini = datetime.fromisoformat(ts)
        fim = ini + timedelta(seconds=dur)

        mesmo = (atual is not None and atual["chave"] == chave
                 and (ini - atual["fim"]).total_seconds() <= gap_max)
        if mesmo:
            atual["dur"] += dur
            atual["fim"] = fim
        else:
            if atual is not None:
                sessoes.append(atual)
            atual = {"chave": chave, "ts": ini, "fim": fim, "dur": dur,
                     "app": app, "titulo": titn, "ocioso": oc, "maq": maq}
    if atual is not None:
        sessoes.append(atual)
    return sessoes


def gravar(destino, sessoes):
    if os.path.exists(destino):
        os.remove(destino)  # recria o COMPACTO do zero; nunca toca no original
    conn = sqlite3.connect(destino)
    criar_schema(conn)
    for s in sessoes:
        conn.execute(
            "INSERT INTO atividade "
            "(ts, app, titulo, ocioso, duracao, maquina, ts_fim, projeto, categoria) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (s["ts"].isoformat(timespec="seconds"), s["app"], s["titulo"],
             s["ocioso"], s["dur"], s["maq"],
             s["fim"].isoformat(timespec="seconds"),
             projeto_de(s["titulo"]), categoria_de(s["app"])),
        )
    conn.commit()
    conn.close()


def main():
    p = argparse.ArgumentParser(description="Compacta o histórico antigo em sessões (não-destrutivo)")
    p.add_argument("--origem", default=DB_PADRAO, help="Banco de origem (padrão: atividade.db)")
    p.add_argument("--destino", default=DESTINO_PADRAO, help="Banco de saída (padrão: atividade-compacto.db)")
    p.add_argument("--gap", type=int, default=GAP_PADRAO,
                   help=f"Folga máx. (s) entre ticks p/ continuar a sessão (padrão: {GAP_PADRAO})")
    args = p.parse_args()

    if not os.path.exists(args.origem):
        print(f"Banco de origem não encontrado: {args.origem}")
        sys.exit(1)
    if os.path.abspath(args.origem) == os.path.abspath(args.destino):
        print("Origem e destino não podem ser o mesmo arquivo (isto é não-destrutivo).")
        sys.exit(1)

    rows = ler_linhas(args.origem)
    sessoes = compactar(rows, args.gap)
    gravar(args.destino, sessoes)

    total_orig = sum(int(r[4] or 0) for r in rows)
    total_novo = sum(s["dur"] for s in sessoes)
    print(f"Origem : {args.origem}")
    print(f"         {len(rows)} linhas, tempo total {fmt(total_orig)}")
    print(f"Destino: {args.destino}")
    print(f"         {len(sessoes)} sessões, tempo total {fmt(total_novo)}")
    if total_orig == total_novo:
        print("OK! Tempo total preservado. O banco original NÃO foi alterado.")
    else:
        print("ATENÇÃO: tempo total divergiu — confira antes de usar o compacto.")


if __name__ == "__main__":
    main()
