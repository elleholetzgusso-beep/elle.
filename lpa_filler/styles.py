"""Utilitários para clonar estilos de células e gerir regiões/mesclas.

A estratégia do filler é *regenerar* as regiões de dados (para suportar qualquer
número de puntos/documentos) clonando o estilo de linhas-modelo do template.
"""
from __future__ import annotations

import copy
from typing import Iterable

from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


def snapshot_row_styles(ws: Worksheet, row: int, max_col: int) -> dict[int, object]:
    """Captura o _style de cada célula de uma linha-modelo (por índice de coluna)."""
    return {c: copy.copy(ws.cell(row=row, column=c)._style) for c in range(1, max_col + 1)}


def apply_row_styles(ws: Worksheet, row: int, styles: dict[int, object]) -> None:
    """Aplica um snapshot de estilos a uma linha."""
    for col, style in styles.items():
        ws.cell(row=row, column=col)._style = copy.copy(style)


def clear_region(ws: Worksheet, first_row: int, last_row: int, max_col: int) -> None:
    """Limpa valores e desfaz mesclas numa região (inclusive), preservando o resto."""
    # Desfazer mesclas que tocam a região.
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row >= first_row and rng.max_row <= last_row:
            ws.unmerge_cells(str(rng))
    for r in range(first_row, last_row + 1):
        for c in range(1, max_col + 1):
            ws.cell(row=r, column=c).value = None


def merge(ws: Worksheet, col: int, r1: int, r2: int) -> None:
    """Mescla verticalmente uma coluna entre r1 e r2 (se houver mais de uma linha)."""
    if r2 > r1:
        letter = get_column_letter(col)
        ws.merge_cells(f"{letter}{r1}:{letter}{r2}")


def copy_row_height(ws: Worksheet, src_row: int, dst_row: int) -> None:
    src = ws.row_dimensions.get(src_row)
    if src is not None and src.height is not None:
        ws.row_dimensions[dst_row].height = src.height


def cols_to_indexes(letters: Iterable[str]) -> list[int]:
    from openpyxl.utils import column_index_from_string

    return [column_index_from_string(l) for l in letters]
