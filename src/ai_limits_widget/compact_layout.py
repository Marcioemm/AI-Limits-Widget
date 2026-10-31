"""Regras puras de geometria e animação da Ilha Dinâmica."""

from __future__ import annotations

import math


def animation_easing(progress: float, expanding: bool, upward: bool) -> float:
    """Calcula o progresso visual sem depender de Tkinter ou relógio."""
    progress = max(0.0, min(1.0, progress))
    if expanding and not upward:
        return 1 - (1 - progress) ** 3
    return progress * progress * (3 - 2 * progress)


def should_expand_upward(
    target_height: int,
    current_y: int,
    current_height: int,
    work_top: int,
    work_height: int,
) -> bool:
    """Escolhe o topo quando falta espaço abaixo e há mais espaço acima."""
    work_bottom = work_top + work_height
    space_below = work_bottom - current_y
    space_above = current_y + current_height - work_top
    return target_height > space_below and space_above > space_below


def anchored_window_y(
    current_y: int,
    current_height: int,
    target_height: int,
    anchor_bottom: bool,
) -> int:
    """Preserva a borda superior ou inferior durante o redimensionamento."""
    if not anchor_bottom:
        return current_y
    return current_y + current_height - target_height


def compact_grid_position(
    index: int,
    column_count: int,
    item_count: int,
    upward: bool,
) -> tuple[int, int]:
    """Posiciona linhas extras acima da linha principal quando necessário."""
    if column_count < 1:
        raise ValueError("column_count deve ser maior que zero")
    if item_count < 1:
        raise ValueError("item_count deve ser maior que zero")
    if not 0 <= index < item_count:
        raise IndexError("index fora da grade compacta")
    source_row = index // column_count
    row_count = math.ceil(item_count / column_count)
    row = row_count - 1 - source_row if upward else source_row
    return row, index % column_count
