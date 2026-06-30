"""
report_detalhado.py - O que voce fez em cada app (janelas/arquivos)
"""
import argparse
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta

# Formatação vem do módulo comum (fonte única)
from comum import fmt

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DADOS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", BASE_DIR), "produtividade", "dados")
DB_PATH = os.path.join(DADOS_DIR, "atividade.db")


def carregar(data_ini, data_fim):
    if not os.path.exists(DB_PATH):
        print(f"Banco nao encontrado em {DB_PATH}. Rode o tracker.py primeiro.")
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT app, titulo, ocioso, duracao FROM atividade "
        "WHERE ts >= ? AND ts < ? ORDER BY ts",
        (data_ini, data_fim),
    ).fetchall()
    conn.close()
    return rows


def main():
    p = argparse.ArgumentParser(description="Relatorio detalhado por app/janela")
    p.add_argument("--dias", type=int, default=1)
    p.add_argument("--data", type=str)
    p.add_argument("--min", type=int, default=30,
                   help="Tempo minimo (segundos) para listar uma janela (padrao: 30)")
    args = p.parse_args()

    if args.data:
        ini = datetime.fromisoformat(args.data)
        fim = ini + timedelta(days=1)
        rotulo = args.data
    else:
        fim = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        ini = fim - timedelta(days=args.dias)
        rotulo = "hoje" if args.dias == 1 else f"ultimos {args.dias} dias"

    rows = carregar(ini.isoformat(), fim.isoformat())

    print("\n" + "=" * 70)
    print(f"  RELATORIO DETALHADO (o que voce fez em cada app) - {rotulo}")
    print("=" * 70)

    if not rows:
        print("  Sem dados nesse periodo.")
        return

    por_app = defaultdict(int)
    por_app_titulo = defaultdict(lambda: defaultdict(int))
    for app, titulo, ocioso, dur in rows:
        if ocioso:
            continue
        a = app or "(desconhecido)"
        por_app[a] += dur
        por_app_titulo[a][titulo or "(sem titulo)"] += dur

    total_ativo = sum(por_app.values())
    print(f"\n  Tempo ativo total: {fmt(total_ativo)}\n")

    for app, seg_app in sorted(por_app.items(), key=lambda x: -x[1]):
        print(f"== {app}  ({fmt(seg_app)}) ==")
        titulos = sorted(por_app_titulo[app].items(), key=lambda x: -x[1])
        mostrados = 0
        for titulo, seg in titulos:
            if seg < args.min:
                continue
            print(f"     {fmt(seg):>7}  {titulo[:62]}")
            mostrados += 1
        if mostrados == 0:
            print(f"     (so janelas curtas, abaixo de {args.min}s)")
        print()


if __name__ == "__main__":
    main()
