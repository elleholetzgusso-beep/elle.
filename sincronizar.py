"""
sincronizar.py - Publica o banco deste PC numa pasta compartilhada
==================================================================

Copia o banco local (atividade.db) para uma pasta de sincronização, com o
nome desta máquina no arquivo (ex.: atividade-DESKTOP-ABC.db). Quando você
roda isto nos DOIS computadores, os dois arquivos ficam na mesma pasta e o
report_consolidado.py consegue juntar tudo num relatório só.

Por padrão a pasta de sync é a subpasta 'sync' do projeto (que fica no
OneDrive e portanto sincroniza entre os PCs automaticamente).

  ⚠️ ATENÇÃO DE PRIVACIDADE: ao sincronizar, os títulos de janela (que podem
  conter nomes de documentos, assuntos de e-mail, etc.) vão para essa pasta.
  Se for o OneDrive institucional, esses dados sobem para a nuvem da
  universidade. Se preferir manter tudo offline, aponte a pasta de sync para
  um pendrive ou pasta local e copie manualmente entre os PCs.

Como usar:
    python sincronizar.py                       # usa a pasta sync/ padrão (OneDrive)
    python sincronizar.py --pasta E:\\backup     # usa outra pasta (ex.: pendrive)
    set PRODUTIVIDADE_SYNC=E:\\backup            # ou define por variável de ambiente
"""

import argparse
import os
import socket
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DADOS_DIR = os.path.join(os.environ.get("LOCALAPPDATA", BASE_DIR), "produtividade", "dados")
DB_LOCAL = os.path.join(DADOS_DIR, "atividade.db")

# Pasta de sync padrão (subpasta do projeto -> sincroniza via OneDrive)
SYNC_PADRAO = os.path.join(BASE_DIR, "sync")


def pasta_sync(arg_pasta: str | None) -> str:
    return arg_pasta or os.environ.get("PRODUTIVIDADE_SYNC") or SYNC_PADRAO


def backup_seguro(origem: str, destino: str):
    """Copia o banco usando a API de backup do SQLite (seguro com o tracker rodando)."""
    src = sqlite3.connect(origem)
    dst = sqlite3.connect(destino)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()


def main():
    p = argparse.ArgumentParser(description="Sincroniza o banco deste PC para uma pasta compartilhada")
    p.add_argument("--pasta", help="Pasta de destino (padrão: subpasta sync/ no OneDrive)")
    args = p.parse_args()

    if not os.path.exists(DB_LOCAL):
        print(f"Banco local não encontrado em {DB_LOCAL}. Rode o tracker.py primeiro.")
        sys.exit(1)

    destino_dir = pasta_sync(args.pasta)
    os.makedirs(destino_dir, exist_ok=True)

    maquina = socket.gethostname()
    destino = os.path.join(destino_dir, f"atividade-{maquina}.db")

    backup_seguro(DB_LOCAL, destino)
    tam = os.path.getsize(destino) / 1024
    print(f"OK! Banco de '{maquina}' publicado em:")
    print(f"    {destino}  ({tam:.0f} KB)")
    print("\nRode o mesmo no outro PC e depois use:  python report_consolidado.py")


if __name__ == "__main__":
    main()
