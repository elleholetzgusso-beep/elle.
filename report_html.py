"""
report_html.py - Relatorio visual (HTML) do tracker, sem internet.
Gera uma pagina com graficos de barras e abre no navegador.
"""
import argparse
import html
import os
import sqlite3
import sys
import webbrowser
from collections import defaultdict
from datetime import datetime, timedelta

# Formatação, categorias, projetos, cores e lista de ruído vêm do módulo comum
from comum import (fmt, categoria_de, rotulo_categoria, projeto_de,
                   CORES, IGNORAR)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(os.environ.get("LOCALAPPDATA", BASE_DIR), "produtividade")
DB_PATH = os.path.join(RAIZ, "dados", "atividade.db")
SAIDA = os.path.join(RAIZ, "relatorio.html")


def barra(label, seg, total, cor="#4f8cff"):
    pct = (seg / total * 100) if total else 0
    return (f'<div class="row"><div class="lbl" title="{html.escape(label)}">{html.escape(label)}</div>'
            f'<div class="bar"><div class="fill" style="width:{pct:.1f}%;background:{cor}"></div></div>'
            f'<div class="val">{fmt(seg)}</div></div>')


CSS = """
body{font-family:Segoe UI,Arial,sans-serif;background:#f4f6fb;color:#1f2430;margin:0;padding:24px;}
h1{font-size:22px;margin:0 0 4px;} .sub{color:#6b7280;margin-bottom:20px;}
.cards{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px;}
.card{background:#fff;border-radius:12px;padding:16px 20px;box-shadow:0 1px 4px rgba(0,0,0,.08);flex:1;min-width:150px;}
.card .big{font-size:26px;font-weight:700;} .card .cap{color:#6b7280;font-size:13px;}
.sec{background:#fff;border-radius:12px;padding:18px 20px;margin-bottom:18px;box-shadow:0 1px 4px rgba(0,0,0,.08);}
.sec h2{font-size:15px;margin:0 0 14px;text-transform:uppercase;letter-spacing:.5px;color:#374151;}
.row{display:flex;align-items:center;gap:10px;margin:5px 0;}
.lbl{width:230px;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.bar{flex:1;background:#eef1f6;border-radius:6px;height:16px;overflow:hidden;}
.fill{height:100%;border-radius:6px;}
.val{width:70px;text-align:right;font-size:13px;font-variant-numeric:tabular-nums;color:#374151;}
"""


def carregar(ini, fim):
    if not os.path.exists(DB_PATH):
        return []
    c = sqlite3.connect(DB_PATH)
    rows = c.execute("SELECT app,titulo,ocioso,duracao,ts FROM atividade WHERE ts>=? AND ts<?",
                     (ini, fim)).fetchall()
    c.close()
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dias", type=int, default=1)
    p.add_argument("--data", type=str)
    a = p.parse_args()
    if a.data:
        ini = datetime.fromisoformat(a.data); fim = ini + timedelta(days=1); rot = a.data
    else:
        fim = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        ini = fim - timedelta(days=a.dias)
        rot = "hoje" if a.dias == 1 else f"ultimos {a.dias} dias"

    rows = carregar(ini.isoformat(), fim.isoformat())
    total = sum(r[3] for r in rows)
    ativo = sum(r[3] for r in rows if r[2] == 0)
    ocioso = total - ativo

    cat = defaultdict(int); app = defaultdict(int); hora = defaultdict(int)
    titulo = defaultdict(int); proj = defaultdict(int)
    for ap, ti, oc, du, ts in rows:
        if oc:
            continue
        a2 = ap or "(desconhecido)"
        if a2.lower() in IGNORAR:
            continue
        cat[categoria_de(ap)] += du
        app[a2] += du
        hora[datetime.fromisoformat(ts).hour] += du
        if ti:
            titulo[ti] += du
        proj[projeto_de(ti)] += du

    def secao(tit, itens, total_ref, colorf=None, labelf=None, n=12):
        h = f'<div class="sec"><h2>{tit}</h2>'
        for k, v in sorted(itens.items(), key=lambda x: -x[1])[:n]:
            cor = colorf(k) if colorf else "#4f8cff"
            rotulo = labelf(k) if labelf else k
            h += barra(rotulo, v, total_ref or 1, cor)
        return h + "</div>"

    horas_html = '<div class="sec"><h2>Por hora do dia</h2>'
    maxh = max(hora.values()) if hora else 1
    for hh in range(24):
        if hora.get(hh):
            horas_html += barra(f"{hh:02d}h", hora[hh], maxh, "#4f8cff")
    horas_html += "</div>"

    pct_at = ativo * 100 // max(total, 1)
    doc = ("<!doctype html><html><head><meta charset='utf-8'>"
           f"<title>Relatorio {rot}</title><style>{CSS}</style></head><body>"
           f"<h1>Relatorio de Produtividade</h1><div class='sub'>{rot} &middot; "
           f"gerado em {datetime.now():%d/%m/%Y %H:%M}</div>"
           "<div class='cards'>"
           f"<div class='card'><div class='big'>{fmt(total)}</div><div class='cap'>Tempo monitorado</div></div>"
           f"<div class='card'><div class='big'>{fmt(ativo)}</div><div class='cap'>Ativo ({pct_at}%)</div></div>"
           f"<div class='card'><div class='big'>{fmt(ocioso)}</div><div class='cap'>Ocioso ({100-pct_at}%)</div></div>"
           "</div>")
    if not rows:
        doc += "<div class='sec'>Sem dados nesse periodo.</div>"
    else:
        doc += secao("Por projeto", proj, ativo, n=15)
        doc += secao("Por categoria", cat, ativo,
                     lambda k: CORES.get(k, "#9ca3af"), rotulo_categoria)
        doc += secao("Aplicativos", app, ativo, n=12)
        doc += horas_html
        doc += secao("Janelas / tarefas", titulo, ativo, n=15)
    doc += "</body></html>"

    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"Relatorio salvo em: {SAIDA}")
    webbrowser.open(SAIDA)


if __name__ == "__main__":
    main()
