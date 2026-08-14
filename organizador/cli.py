"""Interface de linha de comando do programa."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .arrumador import CRITERIOS, ErroDeOrganizacao, limpar_vazias, organizar
from .categorias import CATEGORIA_OUTROS, carregar_categorias
from .criador import ErroDeCriacao, criar_estrutura
from .desfazer import desfazer_operacao
from .historico import Historico, resumir
from .modelos import ErroDeModelo, carregar_arquivo, listar_modelos, obter_modelo
from .projetos import ErroDeProjeto, criar_envio, criar_projeto

MARCA_SIMULACAO = "[SIMULACAO] "


def _prefixo(simular: bool) -> str:
    return MARCA_SIMULACAO if simular else ""


def _relativo(caminho: Path, base: Path) -> str:
    try:
        return str(caminho.relative_to(base))
    except ValueError:
        return str(caminho)


# ----------------------------------------------------------------------- comandos
def comando_criar(args: argparse.Namespace, historico: Historico) -> int:
    fontes = [bool(args.modelo), bool(args.arquivo), bool(args.pastas)]
    if sum(fontes) != 1:
        print("Escolha exatamente uma origem: --modelo, --arquivo ou --pastas.", file=sys.stderr)
        return 2

    if args.modelo:
        caminhos = obter_modelo(args.modelo)
    elif args.arquivo:
        caminhos = carregar_arquivo(args.arquivo)
    else:
        caminhos = list(args.pastas)

    resultado = criar_estrutura(args.destino, caminhos, simular=args.simular)

    prefixo = _prefixo(args.simular)
    for pasta in resultado.criadas:
        print(f"{prefixo}+ {pasta}")
    if args.detalhado:
        for pasta in resultado.existentes:
            print(f"{prefixo}= {pasta} (ja existia)")

    print(
        f"\n{prefixo}{len(resultado.criadas)} pasta(s) criada(s), "
        f"{len(resultado.existentes)} ja existia(m), em {resultado.destino}"
    )

    if resultado.criadas and not args.simular and not args.sem_registro:
        identificador = historico.registrar(
            "criar",
            resultado.destino,
            pastas_criadas=[str(p) for p in resultado.criadas],
            detalhes={"modelo": args.modelo, "arquivo": args.arquivo},
        )
        print(f"Registrado no historico como {identificador} (use 'desfazer').")
    return 0


def comando_novo_projeto(args: argparse.Namespace, historico: Historico) -> int:
    resultado = criar_projeto(
        args.destino,
        args.ano,
        args.codigo,
        args.nome,
        simular=args.simular,
    )
    prefixo = _prefixo(args.simular)
    print(f"{prefixo}Projeto: {resultado.pasta.name}")
    for pasta in resultado.criacao.criadas:
        rotulo = _relativo(pasta, resultado.pasta.parent)
        print(f"{prefixo}+ {str(pasta) if rotulo == '.' else rotulo}")
    print(
        f"\n{prefixo}{len(resultado.criacao.criadas)} pasta(s) criada(s) em "
        f"{resultado.pasta.parent}"
    )

    if resultado.criacao.criadas and not args.simular and not args.sem_registro:
        identificador = historico.registrar(
            "criar",
            resultado.pasta,
            pastas_criadas=[str(p) for p in resultado.criacao.criadas],
            detalhes={"projeto": resultado.pasta.name},
        )
        print(f"Registrado no historico como {identificador} (use 'desfazer').")
    return 0


def comando_envio(args: argparse.Namespace, historico: Historico) -> int:
    pasta = criar_envio(
        args.projeto,
        data_envio=args.data,
        numero=args.numero,
        observacao=args.obs,
        simular=args.simular,
    )
    prefixo = _prefixo(args.simular)
    print(f"{prefixo}+ {pasta}")

    if not args.simular and not args.sem_registro:
        identificador = historico.registrar(
            "criar", pasta.parent, pastas_criadas=[str(pasta)]
        )
        print(f"Registrado no historico como {identificador} (use 'desfazer').")
    return 0


def comando_organizar(args: argparse.Namespace, historico: Historico) -> int:
    resultado = organizar(
        args.pasta,
        args.por,
        recursivo=args.recursivo,
        incluir_ocultos=args.incluir_ocultos,
        simular=args.simular,
        ignorar=tuple(args.ignorar or ()),
        arquivo_categorias=args.categorias,
        formato_data=args.formato_data,
    )

    prefixo = _prefixo(args.simular)
    base = resultado.base
    for movimento in resultado.movimentos:
        print(
            f"{prefixo}{_relativo(movimento.origem, base)}"
            f"  ->  {_relativo(movimento.destino, base)}"
        )
    if args.detalhado:
        for arquivo, motivo in resultado.ignorados:
            print(f"{prefixo}. {_relativo(arquivo, base)} ({motivo})")

    print(
        f"\n{prefixo}{len(resultado.movimentos)} arquivo(s) movido(s), "
        f"{len(resultado.pastas_criadas)} pasta(s) criada(s), "
        f"{len(resultado.ignorados)} ignorado(s). Criterio: {resultado.criterio}."
    )

    if resultado.movimentos and not args.simular and not args.sem_registro:
        identificador = historico.registrar(
            "organizar",
            base,
            movimentos=[
                {"de": str(m.origem), "para": str(m.destino)}
                for m in resultado.movimentos
            ],
            pastas_criadas=[str(p) for p in resultado.pastas_criadas],
            detalhes={"criterio": resultado.criterio},
        )
        print(f"Registrado no historico como {identificador} (use 'desfazer').")
    return 0


def comando_limpar(args: argparse.Namespace, historico: Historico) -> int:
    removidas = limpar_vazias(args.pasta, simular=args.simular)
    prefixo = _prefixo(args.simular)
    for pasta in removidas:
        print(f"{prefixo}- {pasta}")
    print(f"\n{prefixo}{len(removidas)} pasta(s) vazia(s) removida(s).")

    if removidas and not args.simular and not args.sem_registro:
        identificador = historico.registrar(
            "limpar", args.pasta, pastas_removidas=[str(p) for p in removidas]
        )
        print(f"Registrado no historico como {identificador} (use 'desfazer').")
    return 0


def comando_arvore(args: argparse.Namespace, _historico: Historico) -> int:
    base = Path(args.pasta).expanduser()
    if not base.is_dir():
        print(f"A pasta '{base}' nao existe.", file=sys.stderr)
        return 1

    print(base)
    total = _imprimir_arvore(base, "", args.nivel, args.arquivos)
    print(f"\n{total} item(ns) listado(s).")
    return 0


def _imprimir_arvore(base: Path, recuo: str, nivel: int, mostrar_arquivos: bool) -> int:
    if nivel == 0:
        return 0
    try:
        itens = sorted(
            (p for p in base.iterdir() if mostrar_arquivos or p.is_dir()),
            key=lambda p: (p.is_file(), p.name.lower()),
        )
    except OSError:
        return 0

    total = 0
    for posicao, item in enumerate(itens):
        ultimo = posicao == len(itens) - 1
        print(f"{recuo}{'└── ' if ultimo else '├── '}{item.name}")
        total += 1
        if item.is_dir():
            total += _imprimir_arvore(
                item, recuo + ("    " if ultimo else "│   "), nivel - 1, mostrar_arquivos
            )
    return total


def comando_modelos(_args: argparse.Namespace, _historico: Historico) -> int:
    print("Modelos disponiveis:\n")
    for nome, descricao, quantidade in listar_modelos():
        print(f"  {nome:<12} {descricao} ({quantidade} pastas)")
    print("\nUse: organizador criar <destino> --modelo <nome>")
    return 0


def comando_categorias(args: argparse.Namespace, _historico: Historico) -> int:
    categorias = carregar_categorias(args.categorias)
    for pasta, extensoes in categorias.items():
        print(f"  {pasta:<14} {' '.join(extensoes)}")
    print(f"\n  {CATEGORIA_OUTROS:<14} (qualquer extensao nao listada acima)")
    return 0


def comando_historico(args: argparse.Namespace, historico: Historico) -> int:
    if args.limpar:
        historico.limpar()
        print("Historico apagado.")
        return 0

    operacoes = historico.listar(args.limite)
    if not operacoes:
        print("Nenhuma operacao registrada.")
        return 0
    for operacao in operacoes:
        print(resumir(operacao))
    return 0


def comando_desfazer(args: argparse.Namespace, historico: Historico) -> int:
    operacao = historico.obter(args.id) if args.id else historico.ultima()
    if operacao is None:
        print(
            f"Operacao '{args.id}' nao encontrada." if args.id
            else "Nao ha nada para desfazer.",
            file=sys.stderr,
        )
        return 1

    print(f"Desfazendo: {resumir(operacao)}")
    resultado = desfazer_operacao(operacao, simular=args.simular)
    prefixo = _prefixo(args.simular)

    for destino_atual, alvo in resultado.restaurados:
        print(f"{prefixo}{destino_atual}  ->  {alvo}")
    for pasta in resultado.pastas_removidas:
        print(f"{prefixo}- {pasta}")
    for pasta in resultado.pastas_recriadas:
        print(f"{prefixo}+ {pasta}")
    for problema in resultado.problemas:
        print(f"{prefixo}! {problema}", file=sys.stderr)

    print(
        f"\n{prefixo}{len(resultado.restaurados)} arquivo(s) restaurado(s), "
        f"{len(resultado.pastas_removidas)} pasta(s) removida(s), "
        f"{len(resultado.pastas_recriadas)} pasta(s) recriada(s)."
    )

    if not args.simular:
        historico.remover(operacao["id"])
    return 0


# ---------------------------------------------------------------------- argumentos
def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="organizador",
        description="Cria e organiza pastas: modelos prontos, projetos de obra, "
        "arrumacao de arquivos por tipo/data/documento e desfazer.",
    )
    parser.add_argument("--versao", action="version", version=f"organizador {__version__}")
    parser.add_argument("--historico", help="arquivo de historico a usar")
    parser.add_argument(
        "--sem-registro",
        action="store_true",
        help="nao grava a operacao no historico (nao sera possivel desfazer)",
    )

    subs = parser.add_subparsers(dest="comando", required=True)

    def com_simulacao(sub: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sub.add_argument(
            "-s", "--simular", action="store_true",
            help="mostra o que seria feito, sem alterar nada",
        )
        return sub

    # criar
    criar = com_simulacao(subs.add_parser("criar", help="cria uma estrutura de pastas"))
    criar.add_argument("destino", help="pasta onde a estrutura sera criada")
    criar.add_argument("-m", "--modelo", help="nome de um modelo pronto")
    criar.add_argument("-a", "--arquivo", help="arquivo .json ou .txt com a estrutura")
    criar.add_argument("-p", "--pastas", nargs="+", help="lista de pastas a criar")
    criar.add_argument("-d", "--detalhado", action="store_true", help="mostra tambem o que ja existia")
    criar.set_defaults(funcao=comando_criar)

    # novo-projeto
    projeto = com_simulacao(
        subs.add_parser("novo-projeto", help="cria a pasta de um projeto AAAA-CODIGO-NOME")
    )
    projeto.add_argument("nome", help="nome do projeto, ex.: 'Estacion de Torre Pacheco (Apeadero)'")
    projeto.add_argument("-c", "--codigo", required=True, help="codigo do projeto, ex.: 16883")
    projeto.add_argument("-A", "--ano", required=True, help="ano do projeto, ex.: 2026")
    projeto.add_argument(
        "-e", "--destino", default=".", help="pasta onde o projeto sera criado (padrao: atual)"
    )
    projeto.set_defaults(funcao=comando_novo_projeto)

    # envio
    envio = com_simulacao(
        subs.add_parser("envio", help="cria a proxima pasta 'Envío N AAAAMMDD' em 2_Doc Recebida")
    )
    envio.add_argument("projeto", help="pasta do projeto (ou a propria 2_Doc Recebida)")
    envio.add_argument("-t", "--data", help="data do envio (AAAAMMDD, AAAA-MM-DD ou DD/MM/AAAA)")
    envio.add_argument("-n", "--numero", type=int, help="numero do envio (padrao: proximo livre)")
    envio.add_argument("-o", "--obs", help="observacao no fim do nome, ex.: 'sin revisar'")
    envio.set_defaults(funcao=comando_envio)

    # organizar
    org = com_simulacao(subs.add_parser("organizar", help="move arquivos para subpastas"))
    org.add_argument("pasta", help="pasta a organizar")
    org.add_argument(
        "-P", "--por", default="tipo", choices=CRITERIOS,
        help="criterio de agrupamento (padrao: tipo)",
    )
    org.add_argument("-r", "--recursivo", action="store_true", help="inclui subpastas")
    org.add_argument("--incluir-ocultos", action="store_true", help="inclui arquivos ocultos")
    org.add_argument("-i", "--ignorar", nargs="+", help="padroes a ignorar, ex.: '*.tmp' '~$*'")
    org.add_argument("--categorias", help="arquivo JSON com categorias personalizadas")
    org.add_argument("--formato-data", help="formato strftime para o criterio 'data', ex.: %%Y-%%m")
    org.add_argument("-d", "--detalhado", action="store_true", help="mostra tambem os ignorados")
    org.set_defaults(funcao=comando_organizar)

    # limpar
    limpar = com_simulacao(subs.add_parser("limpar", help="remove subpastas vazias"))
    limpar.add_argument("pasta", help="pasta a limpar")
    limpar.set_defaults(funcao=comando_limpar)

    # arvore
    arvore = subs.add_parser("arvore", help="mostra a estrutura de pastas")
    arvore.add_argument("pasta", nargs="?", default=".", help="pasta a exibir (padrao: atual)")
    arvore.add_argument("-n", "--nivel", type=int, default=3, help="profundidade maxima (padrao: 3)")
    arvore.add_argument("-f", "--arquivos", action="store_true", help="mostra tambem os arquivos")
    arvore.set_defaults(funcao=comando_arvore)

    # modelos / categorias
    subs.add_parser("modelos", help="lista os modelos prontos").set_defaults(funcao=comando_modelos)
    cat = subs.add_parser("categorias", help="lista as categorias de arquivos")
    cat.add_argument("--categorias", help="arquivo JSON com categorias personalizadas")
    cat.set_defaults(funcao=comando_categorias)

    # historico / desfazer
    hist = subs.add_parser("historico", help="mostra as operacoes registradas")
    hist.add_argument("-l", "--limite", type=int, default=20, help="quantas operacoes mostrar")
    hist.add_argument("--limpar", action="store_true", help="apaga o historico")
    hist.set_defaults(funcao=comando_historico)

    desf = com_simulacao(subs.add_parser("desfazer", help="reverte a ultima operacao"))
    desf.add_argument("id", nargs="?", help="id da operacao (padrao: a mais recente)")
    desf.set_defaults(funcao=comando_desfazer)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)
    historico = Historico(args.historico)

    try:
        return args.funcao(args, historico)
    except (ErroDeCriacao, ErroDeModelo, ErroDeOrganizacao, ErroDeProjeto) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    except FileNotFoundError as erro:
        print(f"Erro: arquivo ou pasta nao encontrado: {erro}", file=sys.stderr)
        return 1
    except PermissionError as erro:
        print(f"Erro: sem permissao: {erro}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuario.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
