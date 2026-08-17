"""Interface de linha de comandos do lpa_filler.

Comandos:
  fill       Preenche o template .xlsm a partir de um YAML de dados.
  scan       Percorre as pastas de "Doc Recibida" e gera a secção `documentos`.
  from-docx  Extrai portada/evaluadores/documentos do relatório PES (.docx).
  extract    Lê um .xlsm já preenchido e reconstrói o YAML (bootstrap).
  anejo      Gera o Anejo A.2 — Base de No Conformidades (CSV), indexado por ID.

Exemplos:
  python -m lpa_filler fill -t template.xlsm -d projeto.yaml -o LPA.xlsm
  python -m lpa_filler scan -r "1_Doc Recibida" -o documentos.yaml
  python -m lpa_filler from-docx -i origem_PES.docx -o meta.yaml
  python -m lpa_filler extract -i LPA_existente.xlsm -o projeto.yaml
  python -m lpa_filler anejo -p projeto.yaml -o anejo_a2.csv
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
    # Ponto único de escrita de um projeto: garante que todo o punto sai daqui
    # com um 'id' estável, seja qual for o comando que o criou.
    if isinstance(data, dict) and "puntos" in data:
        from . import model

        novos = model.assign_ids(data)
        if novos:
            print(f"# {len(novos)} ID(s) estables asignados ({novos[0]}..{novos[-1]}).",
                  file=sys.stderr)
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
    descartes = model.preparar_emissao(data)
    for d in descartes:
        print(f"  ! {d}")
    # Estados sem suporte no diálogo (PE/03 §8.4). Com --strict, não se emite:
    # um 'Cerrado' sem prova de execução falseia o veredito do IES.
    transicoes = model.check_transiciones(data)
    if transicoes and args.strict:
        print(f"\n== ESTADOS SIN SOPORTE EN EL DIÁLOGO ({len(transicoes)}) — PE/03 §8.4 ==",
              file=sys.stderr)
        for t in transicoes:
            print(f"  ✗ {t}", file=sys.stderr)
        print("\nFichero NO generado (--strict). Corrige los estados de arriba, o ejecuta "
              "sem --strict para gerar mesmo assim.", file=sys.stderr)
        return 1
    v = model.veredicto(data)
    vtexto = model.veredicto_texto(v)
    try:
        out = filler.fill(args.template, data, args.out, veredicto_text=vtexto, veredicto_cell=args.veredicto_cell, skip_lpa=args.skip_lpa)
    except PermissionError:
        return _erro_bloqueado(args.out)
    print(f"\n== {vtexto} ==")
    if v["criticos_abiertos"]:
        print("   (un Crítico Abierto impide el informe favorable — PE/03; el fichero se generó igualmente)")
    print()
    counts = model.resumen_counts(data)
    total = sum(c["total"] for c in counts.values())
    print(f"Generado: {out}")
    print(f"  documentos: {len(data['documentos'])} | puntos: {len(data['puntos'])} (total hallazgos: {total})")
    for val, c in counts.items():
        if c["total"]:
            print(f"  {val}: {c['total']}")
    avisos = model.lint(data)
    if avisos:
        print(f"\nAvisos ({len(avisos)}) — buenas prácticas de la guía LPA:")
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
        print(f"# {len(desviados)} desviados (no evaluativos, PE/01 — sin puntos de LPA):", file=sys.stderr)
        for d in desviados:
            print(f"#   - {d['nombre']}: {d['_triage_motivo']}", file=sys.stderr)
    if incertos:
        print(f"# {len(incertos)} inciertos (revisar a mano; siguen en el flujo normal):", file=sys.stderr)
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


def _erro_bloqueado(path: str) -> int:
    """O caso do dia-a-dia: o ficheiro de saída está aberto no Excel.

    O Windows recusa a escrita e o openpyxl deixa passar um PermissionError em
    bruto — um traceback de 15 linhas para algo que se resolve fechando a janela.
    """
    print(
        f"\nNo puedo escribir '{path}': el fichero está abierto en otro programa "
        f"(normalmente Excel).\nCiérralo y ejecuta el comando otra vez.",
        file=sys.stderr,
    )
    return 1


def _cmd_anejo(args) -> int:
    from . import anejo, model

    projeto = _load_yaml(args.projeto)
    puntos = projeto.get("puntos") or []
    if not puntos:
        print(f"Sin puntos en {args.projeto} — nada que generar.", file=sys.stderr)
        return 1

    # O Anejo A.2 é indexado pelo ID estável (§4). Atribuir IDs só em memória
    # seria pior do que não os ter: saíam números que o projeto.yaml não conhece
    # e que mudavam ao correr de novo. Ou se persistem no projeto, ou não se gera.
    sem_id = [pt for pt in puntos if not model.normalize_id(pt.get("id") or "")]
    if sem_id and not args.asignar_ids:
        print(
            f"{len(sem_id)} punto(s) sin 'id' estable en {args.projeto}.\n"
            f"El Anejo A.2 se indexa por ID — ejecuta de nuevo con --asignar-ids "
            f"para asignarlos y guardarlos en el proyecto.",
            file=sys.stderr,
        )
        return 1
    if sem_id:
        novos = model.assign_ids(projeto)
        _dump_yaml(projeto, args.projeto)
        print(f"{len(novos)} ID(s) asignados y guardados en {args.projeto}.")

    # Mesmo funil do fill: o Anejo A.2 e o LPA são duas vistas do mesmo registo,
    # por isso têm de descrever o mesmo conjunto de hallazgos. Sem isto, o Anejo
    # levava os puntos que o fill descarta por serem de outra obra, e um 'n' que
    # não correspondia a nenhuma linha da folha emitida.
    antes = {model.normalize_id(pt.get("id") or "") for pt in puntos}
    for aviso in model.preparar_emissao(projeto):
        print(f"  ! {aviso}")
    descartados = antes - {model.normalize_id(pt.get("id") or "") for pt in projeto["puntos"]}

    if args.solo and (pedidos_fora := sorted(
        {model.normalize_id(v) for v in args.solo} & descartados
    )):
        print(
            f"IDs pedidos mas descartados nesta emissão: {', '.join(pedidos_fora)}. "
            f"Ver el motivo arriba — no entran en el LPA, luego no entran en el Anejo.",
            file=sys.stderr,
        )
        return 1

    try:
        linhas = anejo.build(projeto, solo=args.solo)
    except anejo.IdDesconhecido as e:
        print(str(e), file=sys.stderr)
        return 1

    try:
        out = anejo.to_csv(linhas, args.out)
    except PermissionError:
        return _erro_bloqueado(args.out)
    print(f"Generado: {out}")
    print(f"  líneas: {len(linhas)} (de {len(puntos)} puntos en el proyecto"
          + (f", {len(descartados)} descartados" if descartados else "") + ")")
    # Contar por campo, não por linha: a 'fecha_deteccion' não é derivável de
    # lado nenhum, por isso sai sempre por preencher e sozinha marcaria 100% das
    # linhas — um número que não distingue nada.
    for campo in anejo.CAMPOS:
        falta = sum(1 for ln in linhas if str(ln.get(campo)) == anejo.A_PREENCHER)
        if falta:
            print(f"  ! {campo}: {falta}/{len(linhas)} por completar")
    print("  (lo que no se deriva del diálogo no se fabrica — completar a mano.)")
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

    # Trava de segurança: o merge cria um projeto novo (puntos vazios). Se o
    # ficheiro de saída já existe e tem puntos (ex. saiu de um extract numa
    # revisão), recusa sobrescrever — senão apagava os hallazgos em silêncio.
    # Para acrescentar documentos a um projeto existente, usa-se o 'update'.
    if args.out and Path(args.out).exists() and not args.force:
        existente = _load_yaml(args.out)
        if existente.get("puntos"):
            print(
                f"Erro: '{args.out}' já tem {len(existente['puntos'])} puntos — o merge "
                f"los borraría (crea proyecto nuevo). Para una revisión, usa 'update' "
                f"(añade documentos sin tocar los puntos). Para forzar de todos modos "
                f"assim, --force.",
                file=sys.stderr,
            )
            return 1

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
        f"# proyecto creado: {len(documentos)} documentos. "
        f"Edita la sección 'puntos' (hallazgos) y después ejecuta el comando 'fill'.",
        file=sys.stderr,
    )
    return 0


def _cmd_update(args) -> int:
    """Revisão: acrescenta os documentos do novo envío a um projeto existente
    (vindo do extract), preservando puntos, versiones e portada."""
    from . import updater

    projeto = _load_yaml(args.projeto)
    if not projeto.get("puntos"):
        print(
            f"# aviso: '{args.projeto}' no tiene puntos. Para un proyecto nuevo, usa 'merge'. "
            f"El 'update' sirve para revisiones (proyecto ya con puntos, venido del extract).",
            file=sys.stderr,
        )
    docs = _load_yaml(args.docs)
    novos = docs.get("documentos") or []
    r = updater.merge_documentos(projeto, novos)
    _dump_yaml(projeto, args.out or args.projeto)
    print(
        f"# proyecto actualizado: +{r['novos_documentos']} documentos nuevos, "
        f"+{r['novos_envios']} envíos novos em documentos existentes. "
        f"{len(projeto.get('puntos', []))} puntos preservados.",
        file=sys.stderr,
    )
    print(
        "# a seguir: 'rev' (acrescenta a nova versão) e revê os estados/diálogos "
        "dos puntos à luz das respostas; 'verify' ajuda a localizar a evidência.",
        file=sys.stderr,
    )
    return 0


def _cmd_draft(args) -> int:
    from . import draft, lector

    projeto = _load_yaml(args.projeto)

    def progresso(n, documento):
        print(f"  redactando borrador del punto {n}: {documento[:55]}...", file=sys.stderr, flush=True)

    try:
        r = draft.elaborar(projeto, args.recibida, on_punto=progresso)
    except NotADirectoryError as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1
    _dump_yaml(projeto, args.out or args.projeto)
    print(
        f"\n# {r['rascunhos']} rascunhos de Respuesta Exceltic escritos "
        f"(marcados '[BORRADOR]'); {r['sem_resposta']} puntos abiertos sin respuesta del "
        f"contratista (nada a redigir).",
        file=sys.stderr,
    )
    print(
        "# REVER cada rascunho: reescreve o parecer e define o estado à mão. O programa "
        "NÃO fechou nenhum punto — o fill avisa enquanto houver rascunho por rever.",
        file=sys.stderr,
    )
    if not lector.PDF_OK:
        print("# nota: soporte a .pdf desactivado (pip install lpa-filler[pdf]).", file=sys.stderr)
    return 0


def _cmd_guide(args) -> int:
    from . import guide

    rows = guide.load_base(args.base)
    if not rows:
        print(f"Base vazia: {args.base}", file=sys.stderr)
        return 1
    r = guide.exportar(rows, args.out)
    print(f"Escrito: {args.out}")
    print(
        f"# {r['hallazgos']} hallazgos de {r['obras']} obras, em {r['tipos']} tipos de documento. "
        f"Abre a aba 'Por onde começar' para ver onde focar numa obra nova.",
        file=sys.stderr,
    )
    return 0


def _cmd_harvest(args) -> int:
    from . import harvest

    if args.recibida:
        paths = harvest.find_lpa_files(args.recibida)
        if not paths:
            print("Ningún fichero de LPA (.xlsm con 'LPA' en el nombre) encontrado.", file=sys.stderr)
            return 1
    else:
        paths = args.input
    novos, total, saltados = harvest.harvest(paths, args.out, append=not args.overwrite)
    print(f"Base de hallazgos: {args.out} (+{novos} nuevos, {total} en total, de {len(paths)} ficheros)")
    if saltados:
        print(f"Saltados {len(saltados)} (no son LPA en el formato esperado):", file=sys.stderr)
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
        referencia = (projeto.get("portada") or {}).get("referencia") or ""
        if anchors and not _scope.own_code_anchors(referencia):
            # Aqui é que os _fora_escopo são atribuídos; avisar depois (no fill)
            # já é tarde, porque a marcação ficou gravada no YAML.
            print(
                f"# ATENCIÓN: 'portada.referencia' ({referencia or 'vacía'}) no da el código "
                f"desta obra. Sem ele, um hallazgo que cite o relatório desta obra é marcado "
                f"_fora_escopo como se fosse de outra. Preenche a referência (ex. "
                f"EXC2026-16883/002/LPA/03) antes de confiar na marcação.",
                file=sys.stderr,
            )
        sugeridos = suggest.suggest_for_projeto(
            base, projeto, n_per_doc=args.n, min_score=args.min_score, skip_texts=skip,
            anchors=anchors,
        )
        if args.debug:
            print("\n# DEBUG: mejor puntuación por documento (incluso por debajo de --min-score):", file=sys.stderr)
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
            f"(¡revisar!) de {len(base)} hallazgos"
            + (f", {len(skip)} ya en el proyecto (no repetidos)." if skip else "."),
            file=sys.stderr,
        )
        if not sugeridos:
            # Zero sugestões tem duas causas muito diferentes, e a diferença
            # decide o que fazer a seguir. Sem isto, um limiar mal calibrado é
            # indistinguível de uma base já toda aproveitada.
            print(
                f"# Ninguna sugerencia nueva. O la base ya está toda en el proyecto, o nada "
                f"llega al umbral --min-score {args.min_score:g} — ejecuta con --debug "
                f"para ver o melhor score de cada documento.",
                file=sys.stderr,
            )
        # Distribuição dos scores: sem isto não há como calibrar --min-score, e um
        # LPA cheio de sugestões fracas gera um veredito que não significa nada.
        scores = sorted((pt.get("_score") or 0) for pt in sugeridos)
        if scores:
            fracos = [s for s in scores if s < args.min_score * 1.5]
            print(
                f"# puntuaciones de las sugerencias: mín {scores[0]:.1f} / mediana "
                f"{scores[len(scores) // 2]:.1f} / max {scores[-1]:.1f} "
                f"(umbral actual --min-score {args.min_score:g}).",
                file=sys.stderr,
            )
            if len(fracos) > len(scores) // 3:
                print(
                    f"# ATENCIÓN: {len(fracos)} de las {len(scores)} sugerencias están cerca del "
                    f"limiar — matches fracos (uma palavra em comum no nome do documento) "
                    f"entram como hallazgos. Sobe o limiar até só sobrar o que reconheces: "
                    f"--min-score {max(args.min_score * 2, 12):g}",
                    file=sys.stderr,
                )
        if anchors:
            print(
                f"# scope={anchors}: {len(fora)} sugerencias marcadas _fora_escopo "
                f"(probable contaminación de otra obra — confirmar/eliminar).",
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
            print("Sin coincidencias.")
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
        print("Nada que añadir: todos los envíos ya están mencionados en el Control de Versiones.")
        return 0
    _dump_yaml(projeto, args.out or args.projeto)
    print(f"# Revisión {entrada['rev']} añadida:", file=sys.stderr)
    for linha in str(entrada["descripcion"]).splitlines():
        print(f"#   {linha}", file=sys.stderr)
    return 0


def _cmd_verify(args) -> int:
    from . import verify

    projeto = _load_yaml(args.projeto)

    def progresso(n, documento):
        print(f"  verificando punto {n}: {documento[:60]}...", file=sys.stderr, flush=True)

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
        f"\n# {abertos} puntos abiertos verificados: {localizados} con fichero localizado, "
        f"{sem_evidencia} sin fragmento citado encontrado (revisar a mano).",
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
        print(f"  leyendo ({i}/{total}): {path.name}", file=sys.stderr, flush=True)

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
        f"\n# {len(registos)} documentos leídos ({ilegiveis} sin texto extraíble).",
        file=sys.stderr,
    )
    if not lector.PDF_OK:
        print(
            "# nota: soporte a .pdf desactivado (instala: pip install lpa-filler[pdf]).",
            file=sys.stderr,
        )
    return 0


def _cmd_radar(args) -> int:
    from . import lector, radar

    base = radar.load_base(args.base)

    def progresso(i, total, path):
        print(f"  analizando ({i}/{total}): {path.name}", file=sys.stderr, flush=True)

    try:
        registos = radar.analisar_pasta(
            args.recibida, base, excluir_obra=args.excluir_obra, on_file=progresso
        )
    except NotADirectoryError as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1
    texto = radar.relatorio(registos, so_pistas=args.so_pistas)
    if args.out:
        Path(args.out).write_text(texto, encoding="utf-8")
        print(f"Escrito: {args.out}")
    else:
        sys.stdout.write(texto)

    n_pistas = sum(len(r["pistas"]) for r in registos)
    criticas = sum(1 for r in registos for p in r["pistas"] if p.nivel == "Crítico")
    ilegiveis = sum(1 for r in registos if r["caracteres"] == 0)
    print(
        f"\n# {len(registos)} documentos analizados: {n_pistas} pistas "
        f"({criticas} de nivel Crítico), {ilegiveis} sin texto extraíble. "
        f"Base: {len(base)} hallazgos.",
        file=sys.stderr,
    )
    if args.excluir_obra:
        print(f"# obra '{args.excluir_obra}' excluida de la base (no copia de la propia respuesta).",
              file=sys.stderr)
    if not lector.PDF_OK:
        print("# nota: soporte a .pdf desactivado (instala: pip install lpa-filler[pdf]).",
              file=sys.stderr)
    return 0


def _cmd_gui(args) -> int:
    try:
        from . import gui
    except ImportError:
        print("La ventana gráfica necesita tkinter, que falta en esta instalación de Python.\n"
              "No Windows, reinstala o Python com a opção 'tcl/tk and IDLE' ligada.",
              file=sys.stderr)
        return 1
    return gui.main()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lpa_filler", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fill", help="Preenche o template .xlsm a partir do YAML.")
    f.add_argument("-t", "--template", required=True, help="Template .xlsm padrão.")
    f.add_argument("-d", "--data", required=True, help="Ficheiro de dados (.yaml/.json).")
    f.add_argument("-o", "--out", required=True, help="Caminho do .xlsm a gerar.")
    f.add_argument(
        "--strict",
        action="store_true",
        help="Não gerar o ficheiro se algum punto estiver 'Resuelto'/'Cerrado' sem o "
             "suporte que o PE/03 §8.4 exige no diálogo (resposta do cliente, aceitação "
             "do avaliador, evidência documental no fecho).",
    )
    f.add_argument(
        "--skip-lpa",
        action="store_true",
        help="Deixa a aba LPA vazia para editar manualmente; preenche só Portada, "
             "Control de versiones e Doc Evaluados.",
    )
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

    an = sub.add_parser(
        "anejo",
        help="Gera o Anejo A.2 — Base de Datos de No Conformidades (CSV), indexado por ID.",
    )
    an.add_argument("-p", "--projeto", required=True, help="projeto.yaml com os puntos.")
    an.add_argument("-o", "--out", default="anejo_a2.csv", help="CSV de saída (default: anejo_a2.csv).")
    an.add_argument(
        "--solo",
        nargs="+",
        metavar="ID",
        help="Restringe aos puntos com estes IDs estáveis (ex. as não conformidades novas "
             "desta revisão). Aceita 'H-007', 'h-7' ou '7'. Um ID inexistente é erro.",
    )
    an.add_argument(
        "--asignar-ids",
        action="store_true",
        dest="asignar_ids",
        help="Atribuir 'id' aos puntos que não o tenham e GRAVAR no projeto.yaml "
             "(o Anejo é indexado por ID, e um ID só é estável se ficar no projeto).",
    )
    an.set_defaults(func=_cmd_anejo)

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
    m.add_argument("--force", action="store_true", help="Sobrescrever mesmo que o -o já tenha puntos (apaga-os — cuidado).")
    m.set_defaults(func=_cmd_merge)

    u = sub.add_parser("update", help="Revisão: acrescenta documentos novos a um projeto existente (preserva puntos).")
    u.add_argument("-p", "--projeto", required=True, help="projeto.yaml existente (vindo do extract do LPA anterior).")
    u.add_argument("-d", "--docs", required=True, help="documentos.yaml do novo envío (saída do scan).")
    u.add_argument("-o", "--out", help="YAML de saída (por omissão: reescreve o próprio projeto).")
    u.set_defaults(func=_cmd_update)

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
    g.add_argument("--min-score", type=float, default=8.0,
                   help="Pontuação mínima para sugerir (modo -p; default 8). Abaixo de ~8 basta "
                        "uma palavra comum no nome do documento para casar, e a LPA enche-se de "
                        "hallazgos de outras obras. Sobe para 12+ se ainda vier ruído; "
                        "usa --debug para ver o melhor score de cada documento.")
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

    dr = sub.add_parser(
        "draft",
        help="Rascunha a réplica do avaliador (Respuesta Exceltic) com a evidência dos ficheiros.",
    )
    dr.add_argument("-p", "--projeto", required=True, help="projeto.yaml (puntos com respostas do contratista).")
    dr.add_argument("-r", "--recibida", required=True, help="Pasta com os ficheiros do novo envío.")
    dr.add_argument("-o", "--out", help="YAML de saída (por omissão: reescreve o próprio projeto).")
    dr.set_defaults(func=_cmd_draft)

    gd = sub.add_parser(
        "guide",
        help="Exporta a base num .xlsx organizado (guia de 'por onde começar' numa obra nova).",
    )
    gd.add_argument("-b", "--base", required=True, help="CSV da base (saída do harvest).")
    gd.add_argument("-o", "--out", default="base_organizada.xlsx", help="Excel de saída (default: base_organizada.xlsx).")
    gd.set_defaults(func=_cmd_guide)

    rd = sub.add_parser(
        "radar",
        help="Instrui onde procurar erros em cada documento recebido, cruzando o texto real com a base.",
    )
    rd.add_argument("-r", "--recibida", required=True, help="Pasta com os documentos recebidos.")
    rd.add_argument("-b", "--base", required=True, help="CSV da base de hallazgos (saída do harvest).")
    rd.add_argument("-o", "--out", help="Relatório de saída (.txt/.md; por omissão: stdout).")
    rd.add_argument("--excluir-obra", dest="excluir_obra",
                    help="Código de obra a excluir da base (ex. EXC2026-16883) — evita colar da própria resposta.")
    rd.add_argument("--so-pistas", dest="so_pistas", action="store_true",
                    help="Omite a lista dos documentos lidos sem sinal específico (relatório curto).")
    rd.set_defaults(func=_cmd_radar)

    gu = sub.add_parser("gui", help="Abre a janela gráfica (não precisa de terminal).")
    gu.set_defaults(func=_cmd_gui)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
