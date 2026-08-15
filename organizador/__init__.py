"""Programa para criar e organizar pastas.

Pacote com duas funcionalidades principais:

* ``criar``    -- cria estruturas de pastas a partir de modelos prontos
                  ou de um arquivo de definicao (JSON ou texto).
* ``organizar``-- move os arquivos de uma pasta para subpastas, agrupando
                  por tipo, data, extensao ou letra inicial.

Todas as operacoes ficam registradas em um historico e podem ser
revertidas com ``desfazer``.
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
