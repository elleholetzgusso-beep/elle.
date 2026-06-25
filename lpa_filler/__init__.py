"""lpa_filler — preenchimento automático do Excel padrão de LPA (Listado de Puntos Abiertos).

Fluxo típico:
    1. `scan`    -> percorre pastas de documentos e gera a secção `documentos` do YAML.
    2. (editar)  -> o utilizador completa os `puntos` (hallazgos) e metadados.
    3. `fill`    -> preenche o template .xlsm preservando macros, estilos e dropdowns.

Também existe `extract` para fazer o caminho inverso (xlsm -> YAML), útil para
arrancar de um LPA já existente.
"""

__version__ = "0.1.0"
