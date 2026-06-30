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
    print("Nota: abrir no Excel e atualizar a PivotTable de 'Resumen Resultados' (Datos > Actualizar todo).")
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
    s.add_argument("--autor", default="UTE", help="Autor por omissão (default: UTE).")
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

    m = sub.add_parser("merge", help="Junta scan+from-docx num projeto.yaml pronto a editar.")
    m.add_argument("-m", "--meta", help="meta.yaml (saída do from-docx).")
    m.add_argument("-d", "--docs", help="documentos.yaml (saída do scan).")
    m.add_argument("-o", "--out", help="projeto.yaml de saída (por omissão: stdout).")
    m.set_defaults(func=_cmd_merge)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
