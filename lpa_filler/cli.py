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
    from . import filler, model, nomenclatura

    data = model.load(args.data)
    nomen = [
        m
        for m in (
            nomenclatura.check_referencia((data.get("portada") or {}).get("referencia") or ""),
            nomenclatura.check_filename(Path(args.out).stem),
        )
        if m
    ] + nomenclatura.avisos_documentos(data.get("documentos", []))
    for m in nomen:
        print(f"  ! nomenclatura: {m}")
    descartes = model.drop_placeholders(data) + model.drop_fora_de_escopo(data)
    for d in descartes:
        print(f"  ! {d}")
    v = model.veredicto(data)
    vtexto = model.veredicto_texto(v)
    out = filler.fill(args.template, data, args.out, veredicto_text=vtexto, veredicto_cell=args.veredicto_cell)
    print(f"\n== {vtexto} ==")
    if v["criticos_abiertos"]:
        print("   (um Crítico Abierto impede o informe favorável — PE/03; o ficheiro foi gerado na mesma)")
    print()
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

    documentos = scan.scan(
        args.recibida, autor=args.autor, group_by=args.group_by, estado=args.estado,
        triage=not args.no_triage,
    )
    _dump_yaml({"documentos": documentos}, args.out)
    print(f"# {len(documentos)} documentos encontrados", file=sys.stderr)
    desviados = [d for d in documentos if d.get("_triage") == "desviado"]
    incertos = [d for d in documentos if d.get("_triage") == "incerto"]
    if desviados:
        print(f"# {len(desviados)} desviados (não avaliativos, PE/01 — sem puntos de LPA):", file=sys.stderr)
        for d in desviados:
            print(f"#   - {d['nombre']}: {d['_triage_motivo']}", file=sys.stderr)
    if incertos:
        print(f"# {len(incertos)} incertos (rever manualmente; seguem no fluxo normal):", file=sys.stderr)
        for d in incertos:
            print(f"#   ? {d['nombre']}: {d['_triage_motivo']}", file=sys.stderr)
    from . import nomenclatura

    for a in nomenclatura.avisos_documentos(documentos):
        print(f"# ! nomenclatura: {a}", file=sys.stderr)
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
    versiones = meta.get("versiones") or []
    if not versiones:
        from . import versiones as _vers

        envios = _vers.envios_do_projeto(documentos)
        desc = (
            _vers.descripcion(1, envios, args.solicitante)
            if envios
            else "PREENCHER: descrição desta versão"
        )
        versiones = [{"rev": 1, "fecha": _dt.date.today(), "descripcion": desc}]
    projeto = {
        "portada": portada,
        "versiones": versiones,
        "documentos": documentos,
        # Sem esqueleto de punto: um placeholder por preencher acabava no Excel final.
        # Ver o formato em config/projeto_exemplo.yaml; o comando suggest acrescenta candidatos.
        "puntos": [],
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
    from . import scope as _scope
    from . import suggest

    base = suggest.load_base(args.base)
    if args.projeto:
        projeto = _load_yaml(args.projeto)
        existentes = [] if args.replace else (projeto.get("puntos") or [])
        skip = {
            " ".join(((pt.get("dialogo") or [{}])[0].get("texto") or "").split()).lower()
            for pt in existentes
        }
        skip.discard("")
        # Âncoras da obra: --scope na linha de comandos, senão a chave 'scope' do projeto.
        anchors = _scope.parse_anchors(args.scope or projeto.get("scope"))
        sugeridos = suggest.suggest_for_projeto(
            base, projeto, n_per_doc=args.n, min_score=args.min_score, skip_texts=skip,
            anchors=anchors,
        )
        if args.debug:
            print("\n# DEBUG: melhor score por documento (mesmo abaixo de --min-score):", file=sys.stderr)
            vistos = set()
            for doc in projeto.get("documentos", []):
                nombre = doc.get("nombre") or ""
                if not nombre or nombre in vistos:
                    continue
                vistos.add(nombre)
                res = suggest.search(base, nombre, doc_hint=nombre, n=1, min_score=0)
                sc = res[0][0] if res else 0.0
                marca = "OK" if sc >= args.min_score else "abaixo do limiar"
                print(f"#   {sc:6.1f}  {marca:18} {nombre[:55]}", file=sys.stderr)
        projeto["puntos"] = list(existentes) + sugeridos
        for i, pt in enumerate(projeto["puntos"], 1):
            pt["n"] = i
        _dump_yaml(projeto, args.out)
        fora = [pt for pt in sugeridos if pt.get("_fora_escopo")]
        print(
            f"# {len(existentes)} puntos existentes + {len(sugeridos)} sugeridos "
            f"(rever!) de {len(base)} hallazgos.",
            file=sys.stderr,
        )
        if anchors:
            print(
                f"# scope={anchors}: {len(fora)} sugestões marcadas _fora_escopo "
                f"(provável contaminação de outra obra — confirmar/remover).",
                file=sys.stderr,
            )
            for pt in fora:
                print(
                    f"#   Nº{pt['n']} [{pt.get('_marcadores','?')}] {pt['documento'][:45]}",
                    file=sys.stderr,
                )
        elif projeto.get("documentos"):
            print(
                "# (sem --scope: filtro de contaminação entre obras desligado; "
                'ex.: --scope "Torre Pacheco, L352, Balsicas")',
                file=sys.stderr,
            )
    elif args.query:
        res = suggest.search(base, args.query, n=args.n, valoracion=args.valoracion)
        if not res:
            print("Sem correspondências.")
        for sc, r in res:
            print(f"[{sc:.0f}] {r.get('valoracion','')}/{r.get('estado','')} | {r.get('documento','')[:35]} | {r.get('punto','')[:25]}")
            print(f"     {(r.get('hallazgo') or '')[:100]}  (de {r.get('fuente','')})")
    else:
        print("Indica -q \"texto\" ou -p projeto.yaml.", file=sys.stderr)
        return 1
    return 0


def _cmd_rev(args) -> int:
    from . import versiones as _vers

    projeto = _load_yaml(args.projeto)
    entrada = _vers.nueva_revision(projeto, solicitante=args.solicitante)
    if entrada is None:
        print("Nada a acrescentar: todos os envíos já estão mencionados no Control de Versiones.")
        return 0
    _dump_yaml(projeto, args.out or args.projeto)
    print(f"# Revisão {entrada['rev']} acrescentada:", file=sys.stderr)
    for linha in str(entrada["descripcion"]).splitlines():
        print(f"#   {linha}", file=sys.stderr)
    return 0


def _cmd_verify(args) -> int:
    from . import verify

    projeto = _load_yaml(args.projeto)

    def progresso(n, documento):
        print(f"  a verificar punto {n}: {documento[:60]}...", file=sys.stderr, flush=True)

    try:
        registos = verify.verificar(projeto, args.recibida, on_punto=progresso)
    except NotADirectoryError as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1
    texto = verify.relatorio(registos)
    if args.out:
        Path(args.out).write_text(texto, encoding="utf-8")
        print(f"Escrito: {args.out}")
    else:
        sys.stdout.write(texto)
    abertos = len(registos)
    localizados = sum(1 for r in registos if r["ficheiro"])
    sem_evidencia = sum(1 for r in registos if r["ficheiro"] and not any(a["trecho"] for a in r["achados"]))
    print(
        f"\n# {abertos} puntos abertos verificados: {localizados} com ficheiro localizado, "
        f"{sem_evidencia} sem trecho citado encontrado (rever à mão).",
        file=sys.stderr,
    )
    from . import lector

    if not lector.PDF_OK:
        print(
            "# nota: suporte a .pdf desligado (instala: pip install lpa-filler[pdf]) — "
            "os .pdf ficaram por ler.",
            file=sys.stderr,
        )
    return 0


def _cmd_leer(args) -> int:
    from . import leer, lector

    def progresso(i, total, path):
        print(f"  a ler ({i}/{total}): {path.name}", file=sys.stderr, flush=True)

    try:
        registos = leer.revisar_pasta(args.recibida, on_file=progresso)
    except NotADirectoryError as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1
    texto = leer.relatorio(registos)
    if args.out:
        Path(args.out).write_text(texto, encoding="utf-8")
        print(f"Escrito: {args.out}")
    else:
        sys.stdout.write(texto)
    ilegiveis = sum(1 for r in registos if r["caracteres"] == 0)
    print(
        f"\n# {len(registos)} documentos lidos ({ilegiveis} sem texto extraível).",
        file=sys.stderr,
    )
    if not lector.PDF_OK:
        print(
            "# nota: suporte a .pdf desligado (instala: pip install lpa-filler[pdf]).",
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
    f.add_argument(
        "--veredicto-cell",
        help='Célula onde escrever o veredicto esperado do IES, ex. "Portada!B30". '
        "Sem isto, o veredicto vai só para a consola e para as propriedades do ficheiro.",
    )
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
    s.add_argument(
        "--no-triage",
        action="store_true",
        help="Desliga a triagem de documentos não avaliativos (PE/01).",
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
    m.add_argument("--solicitante", default="", help='Quem realiza os envíos, ex. "UTE ESTEYCO-ARDANUY" (entra na descrição da versão).')
    m.add_argument("-m", "--meta", help="meta.yaml (saída do from-docx).")
    m.add_argument("-d", "--docs", help="documentos.yaml (saída do scan).")
    m.add_argument("-o", "--out", help="projeto.yaml de saída (por omissão: stdout).")
    m.set_defaults(func=_cmd_merge)

    v = sub.add_parser("rev", help="Acrescenta a próxima revisão ao Control de Versiones (envíos novos).")
    v.add_argument("-p", "--projeto", required=True, help="projeto.yaml a atualizar.")
    v.add_argument("-o", "--out", help="YAML de saída (por omissão: reescreve o próprio projeto).")
    v.add_argument("--solicitante", default="", help='Quem realiza os envíos, ex. "UTE ESTEYCO-ARDANUY".')
    v.set_defaults(func=_cmd_rev)

    g = sub.add_parser("suggest", help="Sugere hallazgos da base de dados para um novo LPA.")
    g.add_argument("-b", "--base", required=True, help="CSV da base (saída do harvest).")
    g.add_argument("-q", "--query", help="Texto/documento a consultar (modo impressão).")
    g.add_argument("-p", "--projeto", help="projeto.yaml a pré-preencher com puntos sugeridos.")
    g.add_argument("-o", "--out", help="YAML de saída (modo -p; por omissão stdout).")
    g.add_argument("-n", type=int, default=8, help="Nº de sugestões (por documento no modo -p).")
    g.add_argument("--min-score", type=float, default=1.0, help="Pontuação mínima para sugerir (modo -p). Aumenta para menos/melhores sugestões.")
    g.add_argument("--replace", action="store_true", help="Substituir os puntos existentes em vez de acrescentar (modo -p).")
    g.add_argument("--debug", action="store_true", help="Mostrar o melhor score por documento (modo -p), para calibrar --min-score.")
    g.add_argument(
        "--scope",
        help='Âncoras da obra atual p/ detetar contaminação de outras obras (modo -p). '
        'Ex.: --scope "Torre Pacheco, L352, Balsicas". Sugestões cujo texto nomeia '
        'outra obra ficam marcadas _fora_escopo. Sem isto, também se lê a chave '
        "'scope' do projeto.yaml.",
    )
    g.add_argument(
        "--valoracion",
        choices=["Crítico", "Importante", "Informativo", "Formal"],
        help="Filtra a base só a esta valoración antes de procurar (modo -q).",
    )
    g.set_defaults(func=_cmd_suggest)

    vf = sub.add_parser(
        "verify",
        help="Ciclo de resposta: abre os ficheiros novos e localiza o que a resposta cita.",
    )
    vf.add_argument("-p", "--projeto", required=True, help="projeto.yaml com os puntos e diálogos.")
    vf.add_argument("-r", "--recibida", required=True, help="Pasta com os ficheiros da resposta (novo envío).")
    vf.add_argument("-o", "--out", help="Relatório de saída (.txt/.md; por omissão: stdout).")
    vf.set_defaults(func=_cmd_verify)

    lr = sub.add_parser(
        "leer",
        help="Lê os documentos recebidos e corre um checklist estrutural por tipo.",
    )
    lr.add_argument("-r", "--recibida", required=True, help="Pasta com os documentos recebidos.")
    lr.add_argument("-o", "--out", help="Relatório de saída (.txt/.md; por omissão: stdout).")
    lr.set_defaults(func=_cmd_leer)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
