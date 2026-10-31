"""Medidores reutilizáveis da interface."""

from __future__ import annotations

import math
import tkinter as tk
from typing import Any

from .geometry import virtual_screen_bounds
from .theme import (
    BG,
    COMPACT_METER_HEIGHT,
    COMPACT_METER_WIDTH,
    LINE,
    MUTED,
    PANEL,
    RED,
    TEXT,
    YELLOW,
    format_reset,
    remaining,
)


class Meter(tk.Frame):
    def __init__(self, master: tk.Misc, title: str, accent: str) -> None:
        super().__init__(master, bg=PANEL, highlightbackground=accent, highlightthickness=1)
        self.accent = accent
        self.columnconfigure(0, weight=1)
        self.title = tk.Label(self, text=title.upper(), bg=PANEL, fg=accent, font=("Segoe UI", 9, "bold"))
        self.title.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        self.value = tk.Label(self, text="—", bg=PANEL, fg=TEXT, font=("Segoe UI", 22, "bold"))
        self.value.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 2))
        self.canvas = tk.Canvas(self, height=13, bg=PANEL, highlightthickness=0)
        self.canvas.grid(row=2, column=0, sticky="ew", padx=12)
        self.reset = tk.Label(self, text="Carregando…", bg=PANEL, fg=MUTED, font=("Segoe UI", 8), anchor="w")
        self.reset.grid(row=3, column=0, sticky="ew", padx=12, pady=(5, 10))
        self.percent: int | None = None
        self.canvas.bind("<Configure>", lambda _event: self._draw())

    def set_data(self, used: Any, resets_at: Any) -> None:
        self.percent = remaining(used)
        self.value.configure(text="—" if self.percent is None else f"{self.percent}%")
        self.reset.configure(text=format_reset(resets_at), fg=MUTED)
        self._draw()

    def set_error(self, message: str) -> None:
        self.percent = None
        self.value.configure(text="—")
        self.reset.configure(text=message, fg=RED)
        self._draw()

    def set_unavailable(self, message: str) -> None:
        """Mostra que a CLI respondeu, mas não publicou aquela janela."""
        self.percent = None
        self.value.configure(text="—")
        self.reset.configure(text=message, fg=MUTED)
        self._draw()

    def _draw(self) -> None:
        self.canvas.delete("all")
        width = max(24, self.canvas.winfo_width())
        height = 13
        body_end = width - 7
        self.canvas.create_rectangle(1, 1, body_end, height - 2, outline=self.accent, width=1)
        self.canvas.create_rectangle(body_end + 1, 4, width - 1, height - 5, fill=self.accent, outline=self.accent)
        if self.percent is None:
            return
        color = RED if self.percent < 15 else YELLOW if self.percent < 35 else self.accent
        fill_width = max(0, (body_end - 5) * self.percent / 100)
        self.canvas.create_rectangle(3, 3, 3 + fill_width, height - 4, fill=color, outline="")
        for fraction in (0.25, 0.5, 0.75):
            x = 3 + (body_end - 5) * fraction
            self.canvas.create_line(x, 3, x, height - 4, fill=PANEL, width=2)


class CircularMeter(tk.Canvas):
    """Medidor circular segmentado usado pelas ilhas do modo compacto."""

    def __init__(self, master: tk.Misc, accent: str, background: str = BG) -> None:
        super().__init__(master, width=92, height=92, bg=background, highlightthickness=0, cursor="hand2")
        self.accent = accent
        self.percent: int | None = None
        self.error = False
        self.bind("<Configure>", lambda _event: self._draw())

    def set_hover_handlers(self, on_enter: Any, on_leave: Any) -> None:
        """Permite revelar detalhes sem acoplar o medidor à janela principal."""
        self.bind("<Enter>", lambda _event: on_enter(self))
        self.bind("<Motion>", lambda _event: on_enter(self))
        self.bind("<Leave>", lambda _event: on_leave(self))

    def set_data(self, used: Any, _resets_at: Any) -> None:
        self.percent = remaining(used)
        self.error = False
        self._draw()

    def set_error(self, _message: str) -> None:
        self.percent = None
        self.error = True
        self._draw()

    def set_unavailable(self, _message: str) -> None:
        self.percent = None
        self.error = False
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width = max(44, self.winfo_width())
        height = max(44, self.winfo_height())
        size = min(width, height)
        center_x, center_y = width / 2, height / 2
        small = size < 70
        radius = (size - (12 if small else 18)) / 2
        inner_radius = radius - (7 if small else 10)
        self.create_oval(
            center_x - radius - 5,
            center_y - radius - 5,
            center_x + radius + 5,
            center_y + radius + 5,
            outline=RED if self.error else LINE,
            width=1,
        )
        label = "—" if self.percent is None else f"{self.percent}%"
        segment_count = 28
        active_segments = 0 if self.percent is None else round(segment_count * self.percent / 100)
        active_color = (
            RED
            if self.error
            else (
                RED
                if self.percent is not None and self.percent < 15
                else YELLOW
                if self.percent is not None and self.percent < 35
                else self.accent
            )
        )
        for index in range(segment_count):
            angle = math.radians(-90 + index * 360 / segment_count)
            outer_x = center_x + radius * math.cos(angle)
            outer_y = center_y + radius * math.sin(angle)
            inner_x = center_x + inner_radius * math.cos(angle)
            inner_y = center_y + inner_radius * math.sin(angle)
            self.create_line(
                inner_x,
                inner_y,
                outer_x,
                outer_y,
                fill=active_color if index < active_segments else LINE,
                width=4 if small else 6,
                capstyle=tk.ROUND,
            )
        self.create_text(
            center_x,
            center_y,
            text=label,
            fill=TEXT,
            font=("Segoe UI", 11 if small else 17, "bold"),
        )


class CompactBatteryMeter(tk.Canvas):
    """Bateria horizontal segmentada usada somente pela Ilha Dinâmica."""

    def __init__(self, master: tk.Misc, accent: str, background: str = BG) -> None:
        super().__init__(
            master,
            width=COMPACT_METER_WIDTH,
            height=COMPACT_METER_HEIGHT,
            bg=background,
            borderwidth=0,
            highlightthickness=0,
            relief=tk.FLAT,
            cursor="hand2",
        )
        self.accent = accent
        self.percent: int | None = None
        self.error = False
        self.bind("<Configure>", lambda _event: self._draw())

    def set_data(self, used: Any, _resets_at: Any) -> None:
        self.percent = remaining(used)
        self.error = False
        self._draw()

    def set_error(self, _message: str) -> None:
        self.percent = None
        self.error = True
        self._draw()

    def set_unavailable(self, _message: str) -> None:
        self.percent = None
        self.error = False
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        # A grade pode distribuir um pixel excedente entre colunas no Windows.
        # O desenho permanece idêntico para todos os provedores.
        width = COMPACT_METER_WIDTH
        height = COMPACT_METER_HEIGHT
        left, top = 3, 3
        right, bottom = width - 9, height - 3
        outline = RED if self.error else self.accent
        self.create_rectangle(left, top, right, bottom, outline=outline, width=2)
        terminal_height = max(8, (bottom - top) * 0.38)
        terminal_top = height / 2 - terminal_height / 2
        self.create_rectangle(
            right + 2,
            terminal_top,
            width - 2,
            terminal_top + terminal_height,
            fill=outline,
            outline=outline,
        )

        label = "—" if self.percent is None else f"{self.percent}%"
        active_color = (
            RED
            if self.error
            else (
                RED
                if self.percent is not None and self.percent < 15
                else YELLOW
                if self.percent is not None and self.percent < 35
                else self.accent
            )
        )
        segment_count = 5
        active_segments = 0 if self.percent is None else int((self.percent * segment_count + 50) // 100)
        inner_left, inner_right = left + 4, right - 4
        inner_top, inner_bottom = top + 4, bottom - 4
        gap = 2
        segment_width = (inner_right - inner_left - gap * (segment_count - 1)) / segment_count
        for index in range(segment_count):
            x1 = inner_left + index * (segment_width + gap)
            self.create_rectangle(
                x1,
                inner_top,
                x1 + segment_width,
                inner_bottom,
                fill=active_color if index < active_segments else LINE,
                outline="",
            )
        self.create_text(
            (left + right) / 2,
            height / 2,
            text=label,
            fill=TEXT,
            font=("Segoe UI", 13 if width >= 110 else 10, "bold"),
        )


class HoverTooltip:
    """Balão curto para explicar os ícones da barra superior."""

    def __init__(self, widget: tk.Misc, text: str, delay_ms: int = 550) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.after_id: str | None = None
        self.window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def set_text(self, text: str) -> None:
        self.text = text
        if self.window:
            self._hide()

    def _schedule(self, _event: tk.Event | None = None) -> None:
        self._cancel_timer()
        self.after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel_timer(self) -> None:
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

    def _show(self) -> None:
        self.after_id = None
        if not self.widget.winfo_exists() or self.window:
            return
        tip = tk.Toplevel(self.widget)
        self.window = tip
        tip.withdraw()
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        label = tk.Label(
            tip,
            text=self.text,
            bg="#292d25",
            fg=TEXT,
            bd=1,
            relief="solid",
            padx=7,
            pady=4,
            font=("Segoe UI", 8),
        )
        label.pack()
        tip.update_idletasks()
        left, top, width, height = virtual_screen_bounds(self.widget)
        tip_width, tip_height = tip.winfo_reqwidth(), tip.winfo_reqheight()
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() - tip_width) // 2
        x = max(left + 4, min(x, left + width - tip_width - 4))
        below = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        y = below if below + tip_height <= top + height - 4 else self.widget.winfo_rooty() - tip_height - 6
        tip.geometry(f"+{x}+{max(top + 4, y)}")
        tip.deiconify()
        tip.lift()

    def _hide(self, _event: tk.Event | None = None) -> None:
        self._cancel_timer()
        if self.window:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None
