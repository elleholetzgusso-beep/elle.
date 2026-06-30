"""
report_consolidado.py - Relatório único juntando todos os PCs
=============================================================

Lê todos os bancos 'atividade-*.db' da pasta de sync (publicados pelo
sincronizar.py em cada computador) MAIS o banco local ao vivo, junta tudo e
gera um relatório combinado + uma quebra por máquina.

Como usar:
    python report_consolidado.py              # hoje, todos os PCs
    python report_consolidado.py --dias 7     # última semana
    python report_consolidado.py --pasta E:\\backup
"""

import argparse
import glob
import os
import socket
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta

# Formatação/classificação vêm do módulo comum; 'barra' (terminal) vem do report
from comum import fmt, categoria_de, rotulo_categoria
from report import barra

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DADOS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", BASE_DIR), "produtividade", "dados")
DB_LOCAL = os.path.join(DADOS_DIR, "atividade.db")
SYNC_PADRAO = os.path.join(BASE_DIR, "sync")


def ler_banco(caminho, ini, fim):
    """Lê linhas de um banco, retornando (ts, app, titulo, ocioso, dur, maquina)."""
    if not os.path.exists(caminho):
        return []
    try:
        conn = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
        cols = [c[1] for c in conn.execute("PRAGMA table_info(atividade)").fetchall()]
        tem_maquina = "maquina" in cols
        campo = "maquina" if tem_maquina else "NULL as maquina"
        rows = conn.execute(
            f"SELECT ts, app, titulo, ocioso, duracao, {campo} FROM atividade "
            "WHERE ts >= ? AND ts < ?",
            (ini, fim),
        ).fetchall()
        conn.close()
        return rows
    except sqlite3.Error as e:
        print(f"  (aviso: não consegui ler {os.path.basename(caminho)}: {e})")
        return []


def coletar(pasta, ini, fim):
    """Junta o banco local + todos os atividade-*.db da pasta de sync, sem duplicar."""
    por_maquina = {}  # nome -> lista de rows
    local_host = socket.gethostname()

    # 1) Arquivos sincronizados (de todos os PCs)
    for arq in glob.glob(os.path.join(pasta, "atividade-*.db")):
        rows = ler_banco(arq, ini, fim)
        if not rows:
            continue
        # nome da máquina: da coluna 'maquina' se houver, senão do nome do arquivo
        nome = rows[0][5] or os.path.basename(arq)[len("atividade-"):-len(".db")]
        por_maquina[nome] = rows

    # 2) Banco local AO VIVO sobrescreve o arquivo sync deste PC (dados mais recentes)
    rows_local = ler_banco(DB_LOCAL, ini, fim)
    if rows_local:
        nome_local = rows_local[0][5] or local_host
        por_maquina[nome_local] = rows_local

    return por_maquina


def resumir(rows):
    total = sum(r[4] for r in rows)
    ativo = sum(r[4] for r in rows if r[3] == 0)
    return total, ativo


def relatorio(por_maquina, rotulo):
    print("\n" + "=" * 64)
    print(f"  RELATÓRIO CONSOLIDADO (todos os PCs) — {rotulo}")
    print("=" * 64)

    todas = [r for rows in por_maquina.values() for r in rows]
    if not todas:
        print("  Sem dados nesse período em nenhum PC.")
        print(f"  (Procurei em: {DB_LOCAL} e na pasta de sync)")
        return

    total, ativo = resumir(todas)
    ocioso = total - ativo

    print(f"\n  PCs com dados          : {', '.join(por_maquina.keys())}")
    print(f"  Tempo total monitorado : {fmt(total)}")
    print(f"  Tempo ativo            : {fmt(ativo)}  ({ativo*100//max(total,1)}%)")
    print(f"  Tempo ocioso           : {fmt(ocioso)}  ({ocioso*100//max(total,1)}%)")

    # Tempo ativo por máquina
    print("\n  ── Tempo ativo por PC ──")
    for nome, rows in sorted(por_maquina.items(), key=lambda x: -resumir(x[1])[1]):
        _, at = resumir(rows)
        print(f"    {nome:<22} {barra(at, ativo)} {fmt(at)}")

    # Categorias somando todos os PCs
    por_cat = defaultdict(int)
    por_app = defaultdict(int)
    for ts, app, titulo, isocioso, dur, _maq in todas:
        if isocioso:
            continue
        por_cat[categoria_de(app)] += dur
        por_app[app or "(desconhecido)"] += dur

    print("\n  ── Por categoria (todos os PCs) ──")
    for cat, seg in sorted(por_cat.items(), key=lambda x: -x[1]):
        print(f"    {rotulo_categoria(cat):<16} {barra(seg, ativo)} {fmt(seg)}")

    print("\n  ── Top 10 aplicativos (todos os PCs) ──")
    for app, seg in sorted(por_app.items(), key=lambda x: -x[1])[:10]:
        print(f"    {app:<24} {barra(seg, ativo, 20)} {fmt(seg)}")

    print()


def main():
    p = argparse.ArgumentParser(description="Relatório consolidado de todos os PCs")
    p.add_argument("--dias", type=int, default=1, help="Quantos dias para trás (padrão: 1 = hoje)")
    p.add_argument("--data", type=str, help="Data específica YYYY-MM-DD")
    p.add_argument("--pasta", help="Pasta de sync (padrão: subpasta sync/ no OneDrive)")
    args = p.parse_args()

    if args.data:
        ini = datetime.fromisoformat(args.data)
        fim = ini + timedelta(days=1)
        rotulo = args.data
    else:
        fim = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        ini = fim - timedelta(days=args.dias)
        rotulo = "hoje" if args.dias == 1 else f"últimos {args.dias} dias"

    pasta = args.pasta or os.environ.get("PRODUTIVIDADE_SYNC") or SYNC_PADRAO
    por_maquina = coletar(pasta, ini.isoformat(), fim.isoformat())
    relatorio(por_maquina, rotulo)


if __name__ == "__main__":
    main()
