"""Interface de linha de comandos do lpa_filler.

Comandos:
  fill       Preenche o template .xlsm a partir de um YAML de dados.
  scan       Percorre as pastas de "Doc Recibida" e gera a secção `documentos`.
  from-docx  Extrai portada/evaluadores/documentos do relatório PES (.docx).
  extract    Lê um .xlsm já preenchido e reconstrói o YAML (bootstrap).

Exemplos:
  python -m lpa_filler fill -t template.xlsm -d projeto.yaml -o LPA.xlsm
  python -m lpa_filler scan -r "1_Doc Recibida" -o documentos.yaml
  python -m lpa_filler from-docx -i origem_PES.docx -o meta.yaml
  python -m lpa_filler extract -i LPA_existente.xlsm -o projeto.yaml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):  # evita &anchor/*alias em datas repetidas
        return True


def _dump_yaml(data: Any, out: str | None) -> None:
    text = yaml.dump(
        data, Dumper=_NoAliasDumper, allow_unicode=True, sort_keys=False, default_flow_style=False
    )
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"Escrito: {out}")
    else:
        sys.stdout.write(text)


def _cmd_fill(args) -> int:
    from . import filler, model

    data = model.load(args.data)
    out = filler.fill(args.template, data, args.out)
    counts = model.resumen_counts(data)
    total = sum(c["total"] for c in counts.values())
    print(f"Gerado: {out}")
    print(f"  documentos: {len(data['documentos'])} | puntos: {len(data['puntos'])} (total hallazgos: {total})")
    for val, c in counts.items():
        if c["total"]:
            print(f"  {val}: {c['total']}")
    avisos = model.lint(data)
    if avisos:
        print(f"\nAvisos ({len(avisos)}) — boas práticas do guia LPA:")
        for a in avisos:
            print(f"  ! {a}")
    return 0


def _cmd_scan(args) -> int:
    from . import scan

    documentos = scan.scan(args.recibida, autor=args.autor, group_by=args.group_by, estado=args.estado)
    _dump_yaml({"documentos": documentos}, args.out)
    print(f"# {len(documentos)} documentos encontrados", file=sys.stderr)
    return 0


def _cmd_from_docx(args) -> int:
    from . import docx_source

    meta = docx_source.extract(args.input)
    _dump_yaml(meta, args.out)
    return 0


def _cmd_extract(args) -> int:
    from . import extract

    data = extract.extract(args.input)
    _dump_yaml(data, args.out)
    return 0


def _load_yaml(path: str):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def _cmd_merge(args) -> int:
    """Junta a saída do scan (documentos) com a do from-docx (portada) e cria um
    projeto.yaml pronto a editar — basta acrescentar os 'puntos' (hallazgos)."""
    import datetime as _dt

    meta = _load_yaml(args.meta) if args.meta else {}
    docs = _load_yaml(args.docs) if args.docs else {}

    documentos = docs.get("documentos") or meta.get("documentos") or []
    mp = meta.get("portada", {})
    NORMATIVA = "Anexo I del Reglamento de Ejecución UE/402/2013 (modificado por UE/2015/1136)"
    # Portada sempre com os campos preenchíveis (senão o template mantém o texto antigo).
    portada = {
        "titulo": mp.get("titulo") or "PREENCHER: título do projeto",
        "referencia": mp.get("referencia") or mp.get("codigo") or "PREENCHER: ex. EXC.../002/LPA/01",
        "normativa": mp.get("normativa") or NORMATIVA,
        "evaluadores": mp.get("evaluadores", []),
    }
    versiones = meta.get("versiones") or [
        {"rev": 1, "fecha": _dt.date.today(), "descripcion": "PREENCHER: descrição desta versão"}
    ]
    projeto = {
        "portada": portada,
        "versiones": versiones,
        "documentos": documentos,
        # Esqueleto de um punto para o utilizador completar (hallazgos = critério do avaliador).
        "puntos": [
            {
                "n": 1,
                "eval": "SM",
                "documento": documentos[0]["nombre"] if documentos else "",
                "ref_documento": "auto",
                "punto": "",
                "valoracion": "Importante",
                "version": None,
                "estado": "Abierto",
                "dialogo": [{"tipo": "Hallazgo", "texto": "DESCREVER O HALLAZGO AQUI"}],
            }
        ],
    }
    _dump_yaml(projeto, args.out)
    print(
        f"# projeto criado: {len(documentos)} documentos. "
        f"Edita a secção 'puntos' (hallazgos) e depois corre o comando 'fill'.",
        file=sys.stderr,
    )
    return 0


def _cmd_harvest(args) -> int:
    from . import harvest

    if args.recibida:
        paths = harvest.find_lpa_files(args.recibida)
        if not paths:
            print("Nenhum ficheiro de LPA (.xlsm com 'LPA' no nome) encontrado.", file=sys.stderr)
            return 1
    else:
        paths = args.input
    novos, total, saltados = harvest.harvest(paths, args.out, append=not args.overwrite)
    print(f"Base de hallazgos: {args.out} (+{novos} novos, {total} no total, de {len(paths)} ficheiros)")
    if saltados:
        print(f"Saltados {len(saltados)} (não são LPA no formato esperado):", file=sys.stderr)
        for s in saltados:
            print(f"  - {s}", file=sys.stderr)
    return 0


def _cmd_suggest(args) -> int:
    from . import suggest

    base = suggest.load_base(args.base)
    if args.projeto:
        projeto = _load_yaml(args.projeto)
        puntos = suggest.suggest_for_projeto(base, projeto, n_per_doc=args.n)
        projeto["puntos"] = puntos
        _dump_yaml(projeto, args.out)
        print(f"# {len(puntos)} puntos sugeridos (rever!) a partir de {len(base)} hallazgos.", file=sys.stderr)
    elif args.query:
        res = suggest.search(base, args.query, n=args.n)
        if not res:
            print("Sem correspondências.")
        for sc, r in res:
            print(f"[{sc:.0f}] {r.get('valoracion','')}/{r.get('estado','')} | {r.get('documento','')[:35]} | {r.get('punto','')[:25]}")
            print(f"     {(r.get('hallazgo') or '')[:100]}  (de {r.get('fuente','')})")
    else:
        print("Indica -q \"texto\" ou -p projeto.yaml.", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lpa_filler", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fill", help="Preenche o template .xlsm a partir do YAML.")
    f.add_argument("-t", "--template", required=True, help="Template .xlsm padrão.")
    f.add_argument("-d", "--data", required=True, help="Ficheiro de dados (.yaml/.json).")
    f.add_argument("-o", "--out", required=True, help="Caminho do .xlsm a gerar.")
    f.set_defaults(func=_cmd_fill)

    s = sub.add_parser("scan", help="Gera `documentos` a partir das pastas de envíos.")
    s.add_argument("-r", "--recibida", required=True, help="Pasta '1_Doc Recibida'.")
    s.add_argument("-o", "--out", help="YAML de saída (por omissão: stdout).")
    s.add_argument("--autor", default="", help='Autor por omissão (vazio). Ex.: --autor "UTE".')
    s.add_argument(
        "--group-by",
        choices=["file", "folder"],
        default="file",
        help="file: nombre=ficheiro (default). folder: nombre=pasta, referencia=ficheiro.",
    )
    s.add_argument(
        "--estado",
        default="auto",
        help='Estado dos documentos: "auto" (fórmula, default) ou literal "Abierto"/"Resuelto"/"Cerrado".',
    )
    s.set_defaults(func=_cmd_scan)

    d = sub.add_parser("from-docx", help="Extrai portada/documentos do relatório PES (.docx).")
    d.add_argument("-i", "--input", required=True, help="Relatório de origem (.docx).")
    d.add_argument("-o", "--out", help="YAML de saída (por omissão: stdout).")
    d.set_defaults(func=_cmd_from_docx)

    e = sub.add_parser("extract", help="Reconstrói o YAML a partir de um .xlsm preenchido.")
    e.add_argument("-i", "--input", required=True, help=".xlsm já preenchido.")
    e.add_argument("-o", "--out", help="YAML de saída (por omissão: stdout).")
    e.set_defaults(func=_cmd_extract)

    h = sub.add_parser("harvest", help="Extrai hallazgos de LPAs para uma base de dados (CSV).")
    h.add_argument("-i", "--input", nargs="+", help="Um ou mais ficheiros .xlsm de LPA.")
    h.add_argument("-r", "--recibida", help="Pasta a percorrer à procura de LPAs (.xlsm com 'LPA').")
    h.add_argument("-o", "--out", default="base_hallazgos.csv", help="CSV de saída (default: base_hallazgos.csv).")
    h.add_argument("--overwrite", action="store_true", help="Reescrever em vez de acrescentar.")
    h.set_defaults(func=_cmd_harvest)

    m = sub.add_parser("merge", help="Junta scan+from-docx num projeto.yaml pronto a editar.")
    m.add_argument("-m", "--meta", help="meta.yaml (saída do from-docx).")
    m.add_argument("-d", "--docs", help="documentos.yaml (saída do scan).")
    m.add_argument("-o", "--out", help="projeto.yaml de saída (por omissão: stdout).")
    m.set_defaults(func=_cmd_merge)

    g = sub.add_parser("suggest", help="Sugere hallazgos da base de dados para um novo LPA.")
    g.add_argument("-b", "--base", required=True, help="CSV da base (saída do harvest).")
    g.add_argument("-q", "--query", help="Texto/documento a consultar (modo impressão).")
    g.add_argument("-p", "--projeto", help="projeto.yaml a pré-preencher com puntos sugeridos.")
    g.add_argument("-o", "--out", help="YAML de saída (modo -p; por omissão stdout).")
    g.add_argument("-n", type=int, default=8, help="Nº de sugestões (por documento no modo -p).")
    g.set_defaults(func=_cmd_suggest)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
