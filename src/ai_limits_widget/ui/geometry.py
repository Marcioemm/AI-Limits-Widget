"""Geometria de tela compartilhada pelos componentes visuais."""

from __future__ import annotations

import os
import tkinter as tk


def virtual_screen_bounds(root: tk.Misc) -> tuple[int, int, int, int]:
    """Retorna a área que cobre todos os monitores."""
    if os.name == "nt":
        try:
            import ctypes

            metrics = ctypes.windll.user32.GetSystemMetrics
            left, top, width, height = (metrics(index) for index in (76, 77, 78, 79))
            if width > 0 and height > 0:
                return left, top, width, height
        except (AttributeError, OSError):
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()
