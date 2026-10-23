"""Comportamento, animação e interação da Ilha Dinâmica."""

from __future__ import annotations

import os
import time
import tkinter as tk
from typing import Any

try:
    from ..compact_layout import anchored_window_y, animation_easing, compact_grid_position, should_expand_upward
    from ..models import Profile
except ImportError:  # Execução direta de app.py.
    from compact_layout import anchored_window_y, animation_easing, compact_grid_position, should_expand_upward
    from models import Profile
from .meters import CompactBatteryMeter
from .theme import (
    COLLAPSED_HEIGHT,
    COMPACT_ANIMATION_FRAME_MS,
    COMPACT_COLLAPSE_DURATION_MS,
    COMPACT_EXPAND_DURATION_MS,
    COMPACT_ISLAND_HEIGHT,
    COMPACT_METER_HEIGHT,
    COMPACT_METER_WIDTH,
    LINE,
    MUTED,
    PANEL_2,
    RED,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    format_reset,
    provider_visuals,
)


def primary_work_area(root: tk.Misc) -> tuple[int, int, int, int]:
    """Retorna a área útil do monitor principal, sem a barra de tarefas."""
    if os.name == "nt":
        try:
            import ctypes
            import ctypes.wintypes

            rect = ctypes.wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
                return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        except (AttributeError, OSError):
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def monitor_work_area(root: tk.Misc, x: int, y: int, width: int, height: int) -> tuple[int, int, int, int]:
    """Retorna a área útil do monitor mais próximo da janela informada."""
    if os.name == "nt":
        try:
            import ctypes
            import ctypes.wintypes

            class MonitorInfo(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.wintypes.DWORD),
                    ("rcMonitor", ctypes.wintypes.RECT),
                    ("rcWork", ctypes.wintypes.RECT),
                    ("dwFlags", ctypes.wintypes.DWORD),
                ]

            rect = ctypes.wintypes.RECT(x, y, x + width, y + height)
            monitor_from_rect = ctypes.windll.user32.MonitorFromRect
            monitor_from_rect.restype = ctypes.c_void_p
            monitor = monitor_from_rect(ctypes.byref(rect), 2)  # MONITOR_DEFAULTTONEAREST
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(MonitorInfo)
            if monitor and ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                work = info.rcWork
                return work.left, work.top, work.right - work.left, work.bottom - work.top
        except (AttributeError, OSError):
            pass
    return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight()


def fit_to_bounds(x: int, y: int, bounds: tuple[int, int, int, int]) -> tuple[int, int]:
    """Desloca a janela para dentro da área visível, preservando a posição quando possível."""
    left, top, width, height = bounds
    x = max(left, min(x, left + width - WINDOW_WIDTH))
    y = max(top, min(y, top + height - WINDOW_HEIGHT))
    return x, y


def is_on_monitor(x: int, y: int) -> bool:
    """Confere se a barra de título cai em algum monitor (a área virtual pode ter lacunas)."""
    if os.name != "nt":
        return True
    try:
        import ctypes
        import ctypes.wintypes

        rect = ctypes.wintypes.RECT(x, y, x + WINDOW_WIDTH, y + COLLAPSED_HEIGHT)
        monitor_from_rect = ctypes.windll.user32.MonitorFromRect
        monitor_from_rect.restype = ctypes.c_void_p
        return bool(monitor_from_rect(ctypes.byref(rect), 0))  # MONITOR_DEFAULTTONULL
    except (AttributeError, OSError):
        return True


class DynamicIslandMixin:
    def _initialize_dynamic_island_state(self) -> None:
        self.drag_origin = (0, 0)
        self.hover_after: str | None = None
        self.hide_hover_after: str | None = None
        self.compact_expand_after: str | None = None
        self.compact_collapse_after: str | None = None
        self.compact_animation_after: str | None = None
        self.compact_expanded = False
        self.compact_expand_upward = False
        self.compact_upward_bottom_inset = 7
        self.compact_pointer_pressed = False
        self.hover_meter: CompactBatteryMeter | None = None
        self.hover_panel: tk.Frame | None = None
        self.hover_title: tk.Label | None = None
        self.hover_window: tk.Label | None = None
        self.hover_value: tk.Label | None = None
        self.hover_reset: tk.Label | None = None
        self.hover_updated: tk.Label | None = None
        self.compact_island: tk.Canvas | None = None
        self.compact_content: tk.Frame | None = None
        self.compact_content_window: int | None = None
        self.compact_grid: tk.Frame | None = None
        self.compact_meter_order: list[tuple[Profile, CompactBatteryMeter]] = []
        self.compact_cells: dict[str, tk.Frame] = {}
        self.compact_detail_widgets: dict[str, dict[str, tk.Widget]] = {}
        self.compact_menu: tk.Menu | None = None

    def _place_window(self) -> None:
        left, top, width, _height = primary_work_area(self.root)
        x, y = left + max(12, width - WINDOW_WIDTH - 24), top + 70
        self.root.geometry(f"{WINDOW_WIDTH}x{self.window_height}+{x}+{y}")

    def _set_window_size_from_right(self, width: int, height: int, anchor_bottom: bool = False) -> None:
        current_width = max(1, self.root.winfo_width())
        current_height = max(1, self.root.winfo_height())
        right = self.root.winfo_x() + current_width
        current_y = self.root.winfo_y()
        target_y = anchored_window_y(current_y, current_height, height, anchor_bottom)
        self.root.geometry(f"{width}x{height}+{right - width}+{target_y}")

    def _draw_compact_pill(self) -> None:
        if not self.compact_island or not self.compact_island.winfo_exists():
            return
        canvas = self.compact_island
        canvas.delete("pill")
        width = max(1, int(canvas.cget("width")))
        height = max(1, int(canvas.cget("height")))
        # O raio cresce junto com a altura, sem trocar bruscamente de formato.
        radius = min(height / 2 - 2, 30)
        points = [
            2 + radius,
            2,
            width - 2 - radius,
            2,
            width - 2,
            2,
            width - 2,
            2 + radius,
            width - 2,
            height - 2 - radius,
            width - 2,
            height - 2,
            width - 2 - radius,
            height - 2,
            2 + radius,
            height - 2,
            2,
            height - 2,
            2,
            height - 2 - radius,
            2,
            2 + radius,
            2,
            2,
        ]
        canvas.create_polygon(points, smooth=True, splinesteps=24, fill=PANEL_2, outline=LINE, width=1, tags="pill")
        canvas.tag_lower("pill")

    def _resize_compact_island(self, expanded: bool) -> None:
        if not all((self.compact_island, self.compact_content, self.compact_content_window)):
            return
        if expanded:
            self.compact_content.update_idletasks()
            height = max(COMPACT_ISLAND_HEIGHT, self.compact_content.winfo_reqheight() + 14)
        else:
            height = COMPACT_ISLAND_HEIGHT
        self._set_compact_island_height(height)

    def _set_compact_island_height(self, height: int) -> None:
        if not all((self.compact_island, self.compact_content, self.compact_content_window)):
            return
        width = self._compact_island_width()
        content_width, inset = width - 14, 7
        if self.compact_expand_upward:
            self.compact_island.itemconfigure(self.compact_content_window, width=content_width, anchor="sw")
            self.compact_island.coords(
                self.compact_content_window,
                inset,
                height - self.compact_upward_bottom_inset,
            )
        else:
            self.compact_island.itemconfigure(self.compact_content_window, width=content_width, anchor="nw")
            self.compact_island.coords(self.compact_content_window, inset, 7)
        self.compact_island.configure(width=width, height=height)
        self._draw_compact_pill()
        self._set_window_size_from_right(width, height, anchor_bottom=self.compact_expand_upward)

    def _choose_compact_expansion_direction(self, target_height: int) -> None:
        """Expande para cima quando os detalhes seriam cortados abaixo."""
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        current_width = max(1, self.root.winfo_width())
        current_height = max(1, self.root.winfo_height())
        _left, work_top, _work_width, work_height = monitor_work_area(
            self.root, current_x, current_y, current_width, current_height
        )
        self.compact_expand_upward = should_expand_upward(
            target_height,
            current_y,
            current_height,
            work_top,
            work_height,
        )

    def _cancel_compact_animation(self) -> None:
        if self.compact_animation_after:
            self.root.after_cancel(self.compact_animation_after)
            self.compact_animation_after = None

    def _animate_compact_height(
        self,
        target_height: int,
        duration_ms: int,
        on_complete: Any | None = None,
    ) -> None:
        """Anima a altura e permite inverter a direção a partir do quadro atual."""
        if not self.compact_island or not self.compact_island.winfo_exists():
            return
        self._cancel_compact_animation()
        start_height = max(1, int(float(self.compact_island.cget("height"))))
        if start_height == target_height:
            self._set_compact_island_height(target_height)
            if on_complete:
                on_complete()
            return
        started_at = time.perf_counter()
        expanding = target_height > start_height

        def animate_frame() -> None:
            if not self.compact_island or not self.compact_island.winfo_exists():
                self.compact_animation_after = None
                return
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            progress = min(1.0, elapsed_ms / max(1, duration_ms))
            eased = animation_easing(progress, expanding, self.compact_expand_upward)
            height = round(start_height + (target_height - start_height) * eased)
            current_height = int(float(self.compact_island.cget("height")))
            if height != current_height:
                self._set_compact_island_height(height)
            if progress < 1:
                self.compact_animation_after = self.root.after(COMPACT_ANIMATION_FRAME_MS, animate_frame)
                return
            self.compact_animation_after = None
            if on_complete:
                on_complete()

        animate_frame()

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())
        if self.layout == "compact":
            self.compact_pointer_pressed = True
            self._collapse_compact_island()

    def _drag(self, event: tk.Event) -> None:
        self.root.geometry(f"+{event.x_root - self.drag_origin[0]}+{event.y_root - self.drag_origin[1]}")

    def _save_position(self, _event: tk.Event | None = None) -> None:
        # A posição vale durante esta execução. Na próxima abertura, o widget
        # volta ao monitor principal para nunca iniciar fora da tela.
        return

    def _finish_drag(self, event: tk.Event | None = None) -> None:
        self._save_position(event)
        self.compact_pointer_pressed = False
        if self.layout != "compact" or not self.compact_island:
            return
        try:
            target = self.root.winfo_containing(self.root.winfo_pointerx(), self.root.winfo_pointery())
            if self._is_descendant(target, self.compact_island):
                self._schedule_compact_expand()
        except tk.TclError:
            return

    def _bind_compact_interactions(self, widget: tk.Misc) -> None:
        widget.bind("<ButtonPress-1>", self._start_drag, add="+")
        widget.bind("<B1-Motion>", self._drag, add="+")
        widget.bind("<ButtonRelease-1>", self._finish_drag, add="+")
        widget.bind("<Button-3>", self._show_compact_menu, add="+")

    def _show_compact_menu(self, event: tk.Event) -> None:
        if not self.compact_menu:
            return
        try:
            self.compact_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.compact_menu.grab_release()

    def _cancel_hover_timer(self) -> None:
        if self.hover_after:
            self.root.after_cancel(self.hover_after)
            self.hover_after = None

    def _cancel_hide_hover_timer(self) -> None:
        if self.hide_hover_after:
            self.root.after_cancel(self.hide_hover_after)
            self.hide_hover_after = None

    def _cancel_compact_timers(self) -> None:
        for attribute in ("compact_expand_after", "compact_collapse_after"):
            after_id = getattr(self, attribute)
            if after_id:
                self.root.after_cancel(after_id)
                setattr(self, attribute, None)

    @staticmethod
    def _is_descendant(target: tk.Misc | None, ancestor: tk.Misc | None) -> bool:
        current = target
        while current:
            if current is ancestor:
                return True
            current = current.master
        return False

    def _schedule_compact_expand(self) -> None:
        if self.compact_pointer_pressed or self.compact_expanded or self.compact_expand_after:
            return
        if self.compact_collapse_after:
            self.root.after_cancel(self.compact_collapse_after)
            self.compact_collapse_after = None
        self.compact_expand_after = self.root.after(300, self._expand_compact_island)

    def _schedule_compact_collapse(self) -> None:
        if self.compact_expand_after:
            self.root.after_cancel(self.compact_expand_after)
            self.compact_expand_after = None
        if not self.compact_expanded or self.compact_collapse_after:
            return
        delay_ms = 80 if self.compact_animation_after else 400
        self.compact_collapse_after = self.root.after(delay_ms, self._collapse_compact_island)

    def _prepare_compact_expanded_layout(self) -> int:
        """Monta o conteúdo expandido e devolve sua altura final."""
        if not self.compact_grid:
            return COMPACT_ISLAND_HEIGHT
        self.compact_grid.pack_configure(fill="x", anchor="e")
        column_count = self._compact_collapsed_count()
        for column in range(3):
            self.compact_grid.columnconfigure(
                column,
                weight=1 if column < column_count else 0,
                uniform="compact-island" if column < column_count else "",
            )
        for index, (profile, meter) in enumerate(self.compact_meter_order):
            meter.configure(width=COMPACT_METER_WIDTH, height=COMPACT_METER_HEIGHT)
            cell = self.compact_cells[profile["id"]]
            cell.grid(
                row=index // column_count,
                column=index % column_count,
                padx=3,
                pady=2,
                sticky="nsew",
            )
            panel = self.compact_detail_widgets[profile["id"]]["panel"]
            panel.pack(fill="x", padx=2, pady=(2, 0))
            self._render_compact_detail(profile, resize=False, align=False)
        self._align_compact_detail_rows()
        assert self.compact_content is not None
        self.compact_content.update_idletasks()
        return max(COMPACT_ISLAND_HEIGHT, self.compact_content.winfo_reqheight() + 14)

    def _arrange_compact_content(self, upward: bool) -> None:
        """Mantém as pilhas na borda de origem e posiciona os detalhes do outro lado."""
        column_count = self._compact_collapsed_count()
        for index, (profile, meter) in enumerate(self.compact_meter_order):
            cell = self.compact_cells[profile["id"]]
            row, column = compact_grid_position(
                index,
                column_count,
                len(self.compact_meter_order),
                upward,
            )
            cell.grid_configure(
                row=row,
                column=column,
                pady=(2, 0) if upward else 2,
            )
            meter_slot = meter.master
            panel = self.compact_detail_widgets[profile["id"]]["panel"]
            meter_slot.pack_forget()
            panel.pack_forget()
            if upward:
                panel.pack(fill="x", padx=2, pady=(0, 2))
                meter_slot.pack(anchor="center")
            else:
                meter_slot.pack(anchor="center")
                panel.pack(fill="x", padx=2, pady=(2, 0))

    def _expand_compact_island(self, animate: bool = True) -> None:
        self.compact_expand_after = None
        if self.layout != "compact" or not self.compact_grid or not self.compact_meter_order:
            return
        self.root.update_idletasks()
        anchor_meter = self.compact_meter_order[0][1]
        self.compact_upward_bottom_inset = max(
            0,
            self.root.winfo_y() + self.root.winfo_height() - anchor_meter.winfo_rooty() - anchor_meter.winfo_height(),
        )
        self.compact_expanded = True
        target_height = self._prepare_compact_expanded_layout()
        self._choose_compact_expansion_direction(target_height)
        self._arrange_compact_content(self.compact_expand_upward)
        assert self.compact_content is not None
        self.compact_content.update_idletasks()
        target_height = max(COMPACT_ISLAND_HEIGHT, self.compact_content.winfo_reqheight() + 14)
        if animate:
            self._animate_compact_height(target_height, COMPACT_EXPAND_DURATION_MS)
        else:
            self._cancel_compact_animation()
            self._set_compact_island_height(target_height)

    def _finalize_compact_collapsed_layout(self) -> None:
        if not self.compact_grid or not self.compact_grid.winfo_exists() or not self.compact_meter_order:
            return
        for column in range(3):
            self.compact_grid.columnconfigure(column, weight=0, minsize=0, uniform="")
        visible_count = self._compact_collapsed_count()
        for index, (profile, meter) in enumerate(self.compact_meter_order):
            cell = self.compact_cells[profile["id"]]
            panel = self.compact_detail_widgets[profile["id"]]["panel"]
            panel.pack_forget()
            if index < visible_count:
                meter.configure(width=COMPACT_METER_WIDTH, height=COMPACT_METER_HEIGHT)
                cell.grid(row=0, column=index, padx=3, pady=0)
            else:
                cell.grid_remove()
        self.compact_grid.pack_configure(fill="none", anchor="center")
        self.compact_expand_upward = False
        if self.compact_island and self.compact_content_window:
            width = self._compact_island_width()
            self.compact_island.itemconfigure(self.compact_content_window, width=width - 14, anchor="nw")
            self.compact_island.coords(self.compact_content_window, 7, 7)

    def _collapse_compact_island(self, animate: bool = True) -> None:
        self._cancel_compact_timers()
        self._cancel_hover_timer()
        self._cancel_hide_hover_timer()
        self.compact_expanded = False
        self.hover_meter = None
        if self.layout != "compact" or not self.compact_island:
            self._cancel_compact_animation()
            return
        if animate:
            self._animate_compact_height(
                COMPACT_ISLAND_HEIGHT,
                COMPACT_COLLAPSE_DURATION_MS,
                self._finalize_compact_collapsed_layout,
            )
        else:
            self._cancel_compact_animation()
            self._set_compact_island_height(COMPACT_ISLAND_HEIGHT)
            self._finalize_compact_collapsed_layout()

    def _schedule_hover_details(self, profile: Profile, meter: CompactBatteryMeter) -> None:
        """Atualiza os detalhes quando o cursor muda de indicador."""
        panel_visible = bool(self.hover_panel and self.hover_panel.winfo_manager())
        if self.hover_meter is meter and (self.hover_after or panel_visible):
            return
        self._cancel_hover_timer()
        self._cancel_hide_hover_timer()
        self.hover_meter = meter
        self.hover_after = self.root.after(120, lambda: self._show_hover_details(profile, meter))

    def _poll_hover_target(self) -> None:
        """Expande a pílula e acompanha o indicador sob o cursor."""
        try:
            target = self.root.winfo_containing(self.root.winfo_pointerx(), self.root.winfo_pointery())
            inside_island = self._is_descendant(target, self.compact_island)
            if self.layout == "compact" and self.compact_island and inside_island:
                if self.compact_collapse_after:
                    self.root.after_cancel(self.compact_collapse_after)
                    self.compact_collapse_after = None
                if not self.compact_pointer_pressed:
                    self._schedule_compact_expand()
            elif self.layout == "compact":
                self._schedule_compact_collapse()
        except tk.TclError:
            return
        self.root.after(200, self._poll_hover_target)

    def _is_inside_hover_panel(self, target: tk.Misc | None) -> bool:
        return self._is_descendant(target, self.hover_panel)

    def _defer_hide_hover_details(self, meter: CompactBatteryMeter | None) -> None:
        if meter is None or meter is not self.hover_meter:
            return
        self._cancel_hover_timer()
        self._cancel_hide_hover_timer()
        # Dá tempo de o cursor atravessar da ilha para o painel expandido.
        self.hide_hover_after = self.root.after(180, self._hide_hover_details)

    def _hide_hover_details(self) -> None:
        self._cancel_hover_timer()
        self._cancel_hide_hover_timer()
        self.hover_meter = None
        if self.hover_panel and self.hover_panel.winfo_exists() and self.hover_panel.winfo_manager():
            self.hover_panel.pack_forget()
            if self.root.winfo_exists() and self.compact_expanded:
                self._resize_compact_island(True)

    def _show_hover_details(self, profile: Profile, meter: CompactBatteryMeter) -> None:
        self.hover_after = None
        if self.layout != "compact" or meter is not self.hover_meter or not meter.winfo_exists():
            return
        details = self.compact_details.get(profile["id"], {})
        accent, provider, _company = provider_visuals(profile["provider"])
        percent = details.get("percent")
        value = "—" if percent is None else f"{percent}% restante"
        message = details.get("message") or format_reset(details.get("resetsAt"))
        if not all(
            (
                self.hover_panel,
                self.hover_title,
                self.hover_window,
                self.hover_value,
                self.hover_reset,
                self.hover_updated,
            )
        ):
            return
        self.hover_panel.configure(highlightbackground=accent)
        hover_title = details.get("title") or f"{provider} · {profile['label'].upper()}"
        self.hover_title.configure(text=hover_title, fg=accent)
        self.hover_window.configure(text=details.get("window", "LIMITE"))
        self.hover_value.configure(text=value)
        self.hover_reset.configure(text=message, fg=RED if details.get("error") else MUTED)
        self.hover_updated.configure(text=details.get("updated") or self.last_refresh_text)
        if not self.hover_panel.winfo_manager():
            self.hover_panel.pack(fill="x", pady=(2, 6))
            if self.compact_expanded:
                self._resize_compact_island(True)

    def _render_compact_detail(self, profile: Profile, resize: bool = True, align: bool = True) -> None:
        widgets = self.compact_detail_widgets.get(profile["id"])
        if not widgets:
            return
        details = self.compact_details.get(profile["id"], {})
        accent, provider, _company = provider_visuals(profile["provider"])
        percent = details.get("percent")
        value = "—" if percent is None else f"{percent}% restante"
        message = details.get("message") or format_reset(details.get("resetsAt"))
        title = details.get("title") or f"{provider} · {profile['label'].upper()}"
        widgets["panel"].configure(highlightbackground=accent)
        widgets["title"].configure(text=title, fg=accent)
        widgets["window"].configure(text=details.get("window", "LIMITE"))
        widgets["value"].configure(text=value)
        widgets["reset"].configure(text=message, fg=RED if details.get("error") else MUTED)
        if align:
            self._align_compact_detail_rows()
        if resize and self.compact_expanded and not self.compact_animation_after and widgets["panel"].winfo_manager():
            self._resize_compact_island(True)

    def _align_compact_detail_rows(self) -> None:
        """Reserva a mesma altura para cada informação em todos os detalhes."""
        if not self.compact_detail_widgets:
            return
        self.root.update_idletasks()
        fields = (("title", 0), ("window", 1), ("value", 2), ("reset", 3))
        for _field, row in fields:
            height = max(int(widgets["panel"].grid_bbox(0, row)[3]) for widgets in self.compact_detail_widgets.values())
            for widgets in self.compact_detail_widgets.values():
                widgets["panel"].grid_rowconfigure(row, minsize=height)
