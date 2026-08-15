"""Ponto de entrada do executável.

O PyInstaller corre o script de entrada como ``__main__``, e nesse caso os
imports relativos do pacote (``from . import pipeline``) não têm pacote-pai e
rebentam. Por isso o executável arranca por aqui, que importa ``lpa_filler``
pelo nome, e não diretamente por ``lpa_filler/gui.py``.
"""
from lpa_filler.gui import main

raise SystemExit(main())
