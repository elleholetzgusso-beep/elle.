"""
report.py - Relatório de produtividade a partir dos dados do tracker
====================================================================

Lê dados/atividade.db e gera um resumo: tempo por app, tempo ativo vs ocioso,
distribuição por hora do dia, e os títulos de janela mais frequentes.

Como usar:
    python report.py            # relatório do dia de hoje
    python report.py --dias 7   # últimos 7 dias
    python report.py --data 2026-06-25
"""

import argparse
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta

# Formatação e classificação vêm do módulo comum (fonte única)
from comum import fmt, categoria_de, rotulo_categoria

# Console do Windows usa cp1252 por padrão; força UTF-8 para os gráficos.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Mesmo caminho local usado pelo tracker (fora do OneDrive)
DADOS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", BASE_DIR), "produtividade", "dados")
DB_PATH = os.path.join(DADOS_DIR, "atividade.db")


def barra(valor, total, largura=30):
    if total == 0:
        return ""
    n = round(largura * valor / total)
    return "█" * n + "░" * (largura - n)


def carregar(data_ini: str, data_fim: str):
    if not os.path.exists(DB_PATH):
        print(f"Banco não encontrado em {DB_PATH}. Rode o tracker.py primeiro.")
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT ts, app, titulo, ocioso, duracao FROM atividade "
        "WHERE ts >= ? AND ts < ? ORDER BY ts",
        (data_ini, data_fim),
    ).fetchall()
    conn.close()
    return rows


def relatorio(rows, rotulo):
    print("\n" + "=" * 64)
    print(f"  RELATÓRIO DE PRODUTIVIDADE — {rotulo}")
    print("=" * 64)

    if not rows:
        print("  Sem dados nesse período. Deixe o tracker.py rodar um tempo.")
        return

    total = sum(r[4] for r in rows)
    ativo = sum(r[4] for r in rows if r[3] == 0)
    ocioso = total - ativo

    por_app = defaultdict(int)
    por_cat = defaultdict(int)
    por_hora = defaultdict(int)
    por_titulo = defaultdict(int)

    for ts, app, titulo, isocioso, dur in rows:
        if isocioso:
            continue  # só conta tempo ATIVO nas quebras abaixo
        por_app[app or "(desconhecido)"] += dur
        por_cat[categoria_de(app)] += dur
        hora = datetime.fromisoformat(ts).hour
        por_hora[hora] += dur
        if titulo:
            por_titulo[titulo] += dur

    print(f"\n  Tempo total monitorado : {fmt(total)}")
    print(f"  Tempo ativo            : {fmt(ativo)}  ({ativo*100//max(total,1)}%)")
    print(f"  Tempo ocioso           : {fmt(ocioso)}  ({ocioso*100//max(total,1)}%)")

    print("\n  ── Por categoria ──")
    for cat, seg in sorted(por_cat.items(), key=lambda x: -x[1]):
        print(f"    {rotulo_categoria(cat):<16} {barra(seg, ativo)} {fmt(seg)}")

    print("\n  ── Top 10 aplicativos (tempo ativo) ──")
    for app, seg in sorted(por_app.items(), key=lambda x: -x[1])[:10]:
        print(f"    {app:<24} {barra(seg, ativo, 20)} {fmt(seg)}")

    print("\n  ── Distribuição por hora ──")
    maxh = max(por_hora.values()) if por_hora else 1
    for h in range(24):
        if por_hora.get(h):
            print(f"    {h:02d}h  {barra(por_hora[h], maxh, 24)} {fmt(por_hora[h])}")

    print("\n  ── Top 8 janelas/tarefas ──")
    for titulo, seg in sorted(por_titulo.items(), key=lambda x: -x[1])[:8]:
        print(f"    {fmt(seg):>7}  {titulo[:54]}")

    print()


def main():
    p = argparse.ArgumentParser(description="Relatório de produtividade")
    p.add_argument("--dias", type=int, default=1, help="Quantos dias para trás (padrão: 1 = hoje)")
    p.add_argument("--data", type=str, help="Data específica YYYY-MM-DD")
    args = p.parse_args()

    if args.data:
        ini = datetime.fromisoformat(args.data)
        fim = ini + timedelta(days=1)
        rotulo = args.data
    else:
        fim = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        ini = fim - timedelta(days=args.dias)
        rotulo = "hoje" if args.dias == 1 else f"últimos {args.dias} dias"

    rows = carregar(ini.isoformat(), fim.isoformat())
    relatorio(rows, rotulo)


if __name__ == "__main__":
    main()
