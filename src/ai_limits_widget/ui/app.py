"""Widget nativo para acompanhar limites do Codex, Claude Code e Gemini."""

from __future__ import annotations

import datetime as dt
import json
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from typing import Any

try:
    from ..config import load_config, save_config
    from ..models import AppConfig, Profile, RateLimitWindow
    from ..profiles import load_profiles, profile_is_available, profile_unavailable_reason
    from ..providers import (
        LimitsProvider,
        configured_executable,
        create_provider,
        provider_commands,
    )
except ImportError:  # Execução direta por scripts/start.ps1.
    from config import load_config, save_config
    from models import AppConfig, Profile, RateLimitWindow
    from profiles import load_profiles, profile_is_available, profile_unavailable_reason
    from providers import (
        LimitsProvider,
        configured_executable,
        create_provider,
        provider_commands,
    )

from .dynamic_island import DynamicIslandMixin
from .meters import CompactBatteryMeter, HoverTooltip, Meter
from .settings import SettingsDialog
from .theme import (
    BG,
    COLLAPSED_HEIGHT,
    COMPACT_BATTERY_SLOT_WIDTH,
    COMPACT_ISLAND_HEIGHT,
    COMPACT_ISLAND_MIN_WIDTH,
    COMPACT_METER_HEIGHT,
    COMPACT_METER_WIDTH,
    LINE,
    MUTED,
    ORANGE,
    PANEL_2,
    TEXT,
    TRANSPARENT_KEY,
    WINDOW_WIDTH,
    YELLOW,
    provider_visuals,
    remaining,
)

CODEX_CLI_DOCS = "https://learn.chatgpt.com/docs/codex/cli"
CLAUDE_CODE_DOCS = "https://docs.anthropic.com/en/docs/claude-code/getting-started"
AGY_DOCS = "https://antigravity.google/docs/cli/"


class UsageWidget(DynamicIslandMixin):
    def __init__(self) -> None:
        self.clients: dict[str, LimitsProvider] = {}
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.last_provider_at: dict[str, float] = {}
        self.warnings: dict[str, str | None] = {}
        self.last_windows: dict[str, dict[str, int | None]] = {}
        self.last_meter_data: dict[str, tuple[RateLimitWindow | None, RateLimitWindow | None]] = {}
        self.last_meter_errors: dict[str, str] = {}
        self.compact_details: dict[str, dict[str, Any]] = {}
        self.last_refresh_text = "Última atualização: —"
        self.refresh_scheduled = False
        self._discover_profiles()
        self.window_height = max(102 if self.layout == "compact" else 168, 114 + 142 * len(self.profiles))
        self.root = tk.Tk()
        self.root.title("Limites de IA")
        self.root.configure(bg=BG)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.97)
        if os.name == "nt":
            try:
                self.root.attributes("-transparentcolor", TRANSPARENT_KEY)
            except tk.TclError:
                pass
        self.root.resizable(False, False)
        self.refreshing = False
        self.collapsed = False
        self.topmost = True
        self._initialize_dynamic_island_state()
        self.button_tooltips: dict[tk.Button, HoverTooltip] = {}
        self._place_window()
        self._build()
        # A quantidade de cartões e as métricas de fonte do Windows variam.
        # Mede o layout pronto para que o rodapé nunca seja cortado.
        self.root.update_idletasks()
        self._resize_to_content()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._drain_events)
        self.root.after(200, self._poll_hover_target)
        if self.profiles:
            self.root.after(250, lambda: self.refresh(force=True))
            self._schedule_refresh()

    def _discover_profiles(self) -> None:
        self.config: AppConfig = load_config()
        self.layout = self.config["layout"]
        self.configured_profiles = load_profiles()
        self.unavailable_profiles = [
            (profile, reason) for profile in self.configured_profiles if (reason := profile_unavailable_reason(profile))
        ]
        self.profiles = [profile for profile in self.configured_profiles if profile_is_available(profile)]
        self.compact_primary_profile_id = self.config.get("compactPrimaryProfileId")
        self.compact_visible_count = self.config.get("compactVisibleCount", 1)
        self.refresh_seconds = self.config["refreshMinutes"] * 60
        self.clients = {}
        for profile in self.profiles:
            self.clients[profile["id"]] = create_provider(profile)
        self.last_provider_at = {}
        self.warnings = {profile["id"]: None for profile in self.profiles}
        self.last_windows = {}
        self.last_meter_data = {}
        self.last_meter_errors = {}

    def _compact_primary_profile(self) -> Profile | None:
        return next(
            (profile for profile in self.profiles if profile["id"] == self.compact_primary_profile_id),
            self.profiles[0] if self.profiles else None,
        )

    def _compact_collapsed_count(self) -> int:
        return max(1, min(3, self.compact_visible_count, len(self.profiles)))

    def _compact_expanded_count(self) -> int:
        """Usa uma coluna por perfil ao abrir, até o limite suportado pela ilha."""
        return max(1, min(3, len(self.profiles)))

    def _compact_island_width(self) -> int:
        return COMPACT_ISLAND_MIN_WIDTH + (self._compact_collapsed_count() - 1) * COMPACT_BATTERY_SLOT_WIDTH

    def _compact_expanded_width(self) -> int:
        return COMPACT_ISLAND_MIN_WIDTH + (self._compact_expanded_count() - 1) * COMPACT_BATTERY_SLOT_WIDTH

    def _close_clients(self) -> None:
        for client in self.clients.values():
            client.close()

    def _resize_to_content(self) -> None:
        self.root.update_idletasks()
        if self.layout == "compact" and self.profiles and self.compact_island:
            self._resize_compact_island(self.compact_expanded)
            return
        minimum_height = 102 if self.layout == "compact" else 168
        self.window_height = max(minimum_height, self.root.winfo_reqheight())
        if not self.collapsed:
            if self.root.winfo_width() != WINDOW_WIDTH:
                self._set_window_size_from_right(WINDOW_WIDTH, self.window_height)
            else:
                self.root.geometry(f"{WINDOW_WIDTH}x{self.window_height}+{self.root.winfo_x()}+{self.root.winfo_y()}")

    def _schedule_refresh(self) -> None:
        if self.refresh_scheduled:
            return
        self.refresh_scheduled = True
        self.root.after(self.refresh_seconds * 1000, self._scheduled_refresh)

    def _build(self) -> None:
        self.titlebar = tk.Frame(self.root, bg=PANEL_2, height=42, highlightbackground=LINE, highlightthickness=1)
        self.titlebar.pack_propagate(False)
        label = tk.Label(self.titlebar, text="LIMITES DE IA", bg=PANEL_2, fg=TEXT, font=("Segoe UI", 10, "bold"))
        label.pack(side="left", padx=12)
        self._button(self.titlebar, "×", self.close, "Fechar").pack(side="right", padx=(0, 5))
        self.collapse_button = self._button(self.titlebar, "–", self.toggle_collapse, "Recolher")
        self.collapse_button.pack(side="right")
        self.pin_button = self._button(self.titlebar, "●", self.toggle_topmost, "Desafixar da frente")
        self.pin_button.configure(fg=ORANGE)
        self.pin_button.pack(side="right")
        layout_hint = "Usar modo compacto" if self.layout == "cards" else "Mostrar detalhes"
        self.layout_button = self._button(
            self.titlebar, "⊟" if self.layout == "cards" else "⊞", self.toggle_layout, layout_hint
        )
        self.layout_button.pack(side="right")
        self._button(self.titlebar, "⚙", self.open_settings, "Configurações").pack(side="right")
        self._button(self.titlebar, "?", self.copy_diagnostics, "Copiar diagnóstico").pack(side="right")
        self._button(self.titlebar, "↻", self.refresh_or_rescan, "Atualizar ou verificar integrações").pack(
            side="right"
        )
        for widget in (self.titlebar, label):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
            widget.bind("<ButtonRelease-1>", self._save_position)

        self.body = tk.Frame(self.root, bg=BG)
        self._build_body()
        self._apply_layout_chrome()

    def _apply_layout_chrome(self) -> None:
        self.titlebar.pack_forget()
        self.body.pack_forget()
        if self.layout == "compact" and self.profiles:
            self.body.pack(fill="both", expand=True)
        else:
            self.titlebar.pack(fill="x")
            self.body.pack(fill="both", expand=True, padx=12, pady=(6, 10))

    def _build_body(self) -> None:
        self.meters: dict[
            str,
            tuple[Meter | CompactBatteryMeter, Meter | CompactBatteryMeter | None],
        ] = {}
        self.compact_expanded = False
        self.compact_island = None
        self.compact_content = None
        self.compact_content_window = None
        self.compact_grid = None
        self.compact_meter_order = []
        self.compact_cells = {}
        self.compact_detail_widgets = {}
        self.compact_menu = None
        self.hover_panel = None
        self.hover_title = None
        self.hover_window = None
        self.hover_value = None
        self.hover_reset = None
        self.hover_updated = None
        if not self.profiles:
            instructions = "Para acompanhar seus limites, instale e autentique pelo menos uma CLI:\n\n"
            instructions += "\n".join(f"• {reason}" for _, reason in self.unavailable_profiles)
            instructions += "\n\nDepois de instalar ou entrar, use Verificar novamente."
            tk.Label(
                self.body,
                text=instructions,
                bg=BG,
                fg=YELLOW,
                justify="left",
                font=("Segoe UI", 9),
                wraplength=WINDOW_WIDTH - 40,
            ).pack(anchor="w", pady=16)
            missing = {profile["provider"] for profile, _ in self.unavailable_profiles}
            actions = tk.Frame(self.body, bg=BG)
            actions.pack(anchor="w", pady=(0, 5))
            if "codex" in missing:
                self._action_button(actions, "Instalar Codex CLI", lambda: webbrowser.open(CODEX_CLI_DOCS)).pack(
                    side="left"
                )
            if "claude" in missing:
                self._action_button(actions, "Instalar Claude Code", lambda: webbrowser.open(CLAUDE_CODE_DOCS)).pack(
                    side="left", padx=(6, 0)
                )
            if "gemini" in missing and not configured_executable(
                self.config["executables"].get("gemini"), provider_commands("gemini")
            ):
                self._action_button(actions, "Instalar AGY", lambda: webbrowser.open(AGY_DOCS)).pack(
                    side="left", padx=(6, 0)
                )
            self._action_button(self.body, "Verificar novamente", self.rescan_integrations).pack(
                anchor="w", pady=(2, 0)
            )
        display_profiles = self.profiles
        if self.layout == "compact" and self.profiles:
            primary = self._compact_primary_profile()
            display_profiles = ([primary] if primary else []) + [
                profile for profile in self.profiles if not primary or profile["id"] != primary["id"]
            ]
            collapsed_width = self._compact_island_width()
            self.compact_island = tk.Canvas(
                self.body,
                width=collapsed_width,
                height=COMPACT_ISLAND_HEIGHT,
                bg=TRANSPARENT_KEY if os.name == "nt" else BG,
                highlightthickness=0,
                cursor="hand2",
            )
            self.compact_island.pack()
            self.compact_content = tk.Frame(self.compact_island, bg=PANEL_2)
            self.compact_content_window = self.compact_island.create_window(
                7, 7, anchor="nw", width=collapsed_width - 14, window=self.compact_content
            )
            self.compact_grid = tk.Frame(self.compact_content, bg=PANEL_2)
            self.compact_grid.pack(anchor="center")

        for index, profile in enumerate(display_profiles):
            accent, title, company = provider_visuals(profile["provider"])
            if self.layout == "compact":
                assert self.compact_grid is not None
                cell = tk.Frame(self.compact_grid, bg=PANEL_2)
                cell.grid(row=0, column=index, padx=3)
                if index >= self._compact_collapsed_count():
                    cell.grid_remove()
                meter_slot = tk.Frame(
                    cell,
                    width=COMPACT_METER_WIDTH,
                    height=COMPACT_METER_HEIGHT,
                    bg=PANEL_2,
                )
                meter_slot.pack(anchor="center")
                meter_slot.pack_propagate(False)
                short = CompactBatteryMeter(meter_slot, accent, PANEL_2)
                short.pack(fill="both", expand=True)
                detail_panel = tk.Frame(cell, bg=PANEL_2, highlightbackground=accent, highlightthickness=1)
                detail_title = tk.Label(
                    detail_panel,
                    bg=PANEL_2,
                    fg=accent,
                    font=("Segoe UI", 8, "bold"),
                    anchor="w",
                    justify="left",
                    wraplength=76,
                )
                detail_title.grid(row=0, column=0, sticky="nsew", padx=7, pady=(6, 1))
                detail_window = tk.Label(detail_panel, bg=PANEL_2, fg=MUTED, font=("Segoe UI", 7, "bold"), anchor="w")
                detail_window.grid(row=1, column=0, sticky="nsew", padx=7)
                detail_value = tk.Label(
                    detail_panel,
                    bg=PANEL_2,
                    fg=TEXT,
                    font=("Segoe UI", 10, "bold"),
                    anchor="w",
                    justify="left",
                    wraplength=76,
                )
                detail_value.grid(row=2, column=0, sticky="nsew", padx=7, pady=(1, 1))
                detail_reset = tk.Label(
                    detail_panel,
                    bg=PANEL_2,
                    fg=MUTED,
                    font=("Segoe UI", 7),
                    anchor="w",
                    justify="left",
                    wraplength=76,
                )
                detail_reset.grid(row=3, column=0, sticky="nsew", padx=7, pady=(0, 6))
                detail_panel.columnconfigure(0, weight=1)
                self.compact_cells[profile["id"]] = cell
                self.compact_detail_widgets[profile["id"]] = {
                    "panel": detail_panel,
                    "title": detail_title,
                    "window": detail_window,
                    "value": detail_value,
                    "reset": detail_reset,
                }
                self.compact_meter_order.append((profile, short))
                week = None
            else:
                self._provider_title(f"{title} · {profile['label'].upper()}", company, accent)
                grid = tk.Frame(self.body, bg=BG)
                grid.pack(fill="x")
                grid.columnconfigure(0, weight=1, uniform="meters")
                grid.columnconfigure(1, weight=1, uniform="meters")
                short = Meter(grid, "Modelo ativo" if profile["provider"] == "gemini" else "5 horas", accent)
                short.grid(row=0, column=0, sticky="ew", padx=(0, 4))
                if profile["provider"] == "gemini":
                    short.grid_configure(columnspan=2, padx=0)
                    week = None
                else:
                    week = Meter(grid, "Semana", accent)
                    week.grid(row=0, column=1, sticky="ew", padx=(4, 0))
            self.meters[profile["id"]] = (short, week)

        if self.layout == "compact" and self.profiles:
            self.compact_menu = tk.Menu(self.root, tearoff=False, bg=PANEL_2, fg=TEXT)
            self.compact_menu.add_command(label="Mostrar cartões", command=self.toggle_layout)
            self.compact_menu.add_command(label="Atualizar", command=self.refresh_or_rescan)
            self.compact_menu.add_command(label="Configurações", command=self.open_settings)
            self.compact_menu.add_command(label="Fixar/desafixar", command=self.toggle_topmost)
            self.compact_menu.add_separator()
            self.compact_menu.add_command(label="Fechar", command=self.close)
            self._bind_compact_interactions(self.compact_island)
            self._bind_compact_interactions(self.compact_content)
            self._bind_compact_interactions(self.compact_grid)
            for profile, meter in self.compact_meter_order:
                cell = self.compact_cells[profile["id"]]
                self._bind_compact_interactions(cell)
                self._bind_compact_interactions(meter)
                widgets = self.compact_detail_widgets[profile["id"]]
                panel = widgets["panel"]
                self._bind_compact_interactions(panel)
                for child in panel.winfo_children():
                    self._bind_compact_interactions(child)

        status_text = "Conectando…" if self.profiles else "Aguardando uma CLI disponível"
        status_color = MUTED if self.profiles else YELLOW
        self.status = tk.Label(self.body, text=status_text, bg=BG, fg=status_color, font=("Segoe UI", 8), anchor="w")
        if self.layout != "compact":
            self.status.pack(fill="x", pady=(12, 0))
        self.last_updated = tk.Label(
            self.body,
            text="Última atualização: —",
            bg=BG,
            fg="#62685b",
            font=("Segoe UI", 8),
            anchor="w",
        )
        if self.layout != "compact":
            self.last_updated.pack(fill="x", pady=(2, 0))

    def _action_button(self, master: tk.Misc, text: str, command: Any) -> tk.Button:
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=PANEL_2,
            fg=TEXT,
            activebackground=LINE,
            activeforeground=TEXT,
            bd=0,
            padx=9,
            pady=4,
            font=("Segoe UI", 8),
            cursor="hand2",
        )

    def _button(self, master: tk.Misc, text: str, command: Any, tooltip: str) -> tk.Button:
        button = tk.Button(
            master,
            text=text,
            command=command,
            bg=PANEL_2,
            fg=MUTED,
            activebackground=LINE,
            activeforeground=TEXT,
            bd=0,
            width=3,
            font=("Segoe UI Symbol", 10),
            cursor="hand2",
        )
        self.button_tooltips[button] = HoverTooltip(button, tooltip)
        return button

    def _provider_title(self, text: str, company: str, accent: str) -> None:
        row = tk.Frame(self.body, bg=BG)
        row.pack(fill="x", pady=(8, 5))
        tk.Frame(row, bg=accent, width=4, height=13).pack(side="left", padx=(0, 7))
        tk.Label(row, text=text, bg=BG, fg=accent, font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(row, text=f"  /  {company}", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(side="left")

    def toggle_collapse(self) -> None:
        self._hide_hover_details()
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.body.pack_forget()
            self.root.geometry(f"{WINDOW_WIDTH}x{COLLAPSED_HEIGHT}")
        else:
            self.body.pack(fill="both", expand=True, padx=12, pady=(6, 10))
            self.root.geometry(f"{WINDOW_WIDTH}x{self.window_height}")
        self.button_tooltips[self.collapse_button].set_text("Expandir" if self.collapsed else "Recolher")

    def toggle_topmost(self) -> None:
        self.topmost = not self.topmost
        self.root.attributes("-topmost", self.topmost)
        self.pin_button.configure(fg=ORANGE if self.topmost else MUTED)
        self.button_tooltips[self.pin_button].set_text(
            "Desafixar da frente" if self.topmost else "Manter sempre visível"
        )

    def toggle_layout(self) -> None:
        # A troca de aparência não inicia uma consulta: reaproveita o último
        # resultado recebido, inclusive enquanto uma atualização está em curso.
        self._collapse_compact_island(animate=False)
        status_text, status_color = self.status.cget("text"), self.status.cget("fg")
        updated_text = self.last_updated.cget("text")
        self.layout = "compact" if self.layout == "cards" else "cards"
        self.config["layout"] = self.layout
        try:
            self.config = save_config(self.config)
        except OSError:
            pass
        for child in self.body.winfo_children():
            child.destroy()
        self._build_body()
        self._apply_layout_chrome()
        for profile in self.profiles:
            saved = self.last_meter_data.get(profile["id"])
            if saved:
                self._render_profile_meters(profile, *saved)
            if message := self.last_meter_errors.get(profile["id"]):
                self._render_profile_error(profile, message)
        self.layout_button.configure(text="⊟" if self.layout == "cards" else "⊞")
        self.button_tooltips[self.layout_button].set_text(
            "Usar modo compacto" if self.layout == "cards" else "Mostrar detalhes"
        )
        self.status.configure(text=status_text, fg=status_color)
        self.last_updated.configure(text=updated_text)
        self._resize_to_content()

    def _scheduled_refresh(self) -> None:
        self.refresh_scheduled = False
        self.refresh(force=False)
        self._schedule_refresh()

    def refresh_or_rescan(self) -> None:
        # Permite terminar uma instalação ou login sem reiniciar o aplicativo.
        if self.unavailable_profiles or not self.profiles:
            self.rescan_integrations()
        else:
            self.refresh(force=True)

    def rescan_integrations(self) -> None:
        if self.refreshing:
            return
        self._collapse_compact_island(animate=False)
        self._close_clients()
        self._discover_profiles()
        for child in self.body.winfo_children():
            child.destroy()
        self._build_body()
        self._apply_layout_chrome()
        self._resize_to_content()
        if self.profiles:
            self._schedule_refresh()
            self.refresh(force=True)

    def open_settings(self) -> None:
        SettingsDialog(self)

    def copy_diagnostics(self) -> None:
        """Copia informações úteis de suporte, deliberadamente sem IDs ou credenciais."""
        cli: dict[str, dict[str, Any]] = {}
        for provider, commands in {
            "codex": ("codex.exe", "codex.cmd", "codex"),
            "claude": ("claude.exe", "claude.cmd", "claude"),
            "gemini": ("agy.exe", "agy.cmd", "agy"),
        }.items():
            executable = configured_executable(self.config["executables"].get(provider), commands)
            info: dict[str, Any] = {"encontrado": bool(executable)}
            if executable:
                try:
                    result = subprocess.run(
                        [executable, "--version"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=5,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                    output = (result.stdout or result.stderr).strip().splitlines()
                    info["versao"] = output[0][:160] if output and result.returncode == 0 else "não informada"
                except (OSError, subprocess.SubprocessError):
                    info["versao"] = "não informada"
            cli[provider] = info
        report = {
            "aplicativo": "AI Limits Widget",
            "versao": "0.1.15",
            "atualizacaoMinutos": self.config["refreshMinutes"],
            "cli": cli,
            "perfis": [
                {
                    "provedor": profile["provider"],
                    "disponivel": profile_is_available(profile),
                    "janelasMinutos": self.last_windows.get(profile["id"], {}),
                    "teveAviso": bool(self.warnings.get(profile["id"])),
                }
                for profile in self.configured_profiles
            ],
        }
        self.root.clipboard_clear()
        self.root.clipboard_append(json.dumps(report, ensure_ascii=False, indent=2))
        self.status.configure(text="Diagnóstico seguro copiado", fg=MUTED)

    def refresh(self, force: bool = False) -> None:
        if not self.profiles:
            self.status.configure(text="Instale e autentique uma CLI; depois, use Verificar novamente.", fg=YELLOW)
            return
        if self.refreshing:
            return
        self.refreshing = True
        self.status.configure(text="Atualizando…", fg=MUTED)
        threading.Thread(target=self._refresh_worker, args=(force,), daemon=True).start()

    def _refresh_worker(self, force: bool) -> None:
        for profile in self.profiles:
            profile_id = profile["id"]
            client = self.clients[profile_id]
            try:
                interval = self.refresh_seconds if client.minimum_refresh_interval_seconds else 0
                if not force and time.monotonic() - self.last_provider_at.get(profile_id, 0.0) < interval:
                    continue
                self.events.put(("profile", (profile, client.read_limits())))
                self.last_provider_at[profile_id] = time.monotonic()
            except Exception as exc:
                self.events.put(("profile_error", (profile, str(exc))))
        self.events.put(("done", None))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "profile":
                    profile, data = payload
                    short, week = self.meters[profile["id"]]
                    first, second = data.get("five_hour"), data.get("weekly")
                    self.last_meter_data[profile["id"]] = (first, second)
                    self.last_meter_errors.pop(profile["id"], None)
                    self._render_profile_meters(profile, first, second)
                    self.last_windows[profile["id"]] = {
                        "cincoHoras": (first or {}).get("windowDurationMins"),
                        "semana": (second or {}).get("windowDurationMins"),
                    }
                    if data.get("stale"):
                        fetched = dt.datetime.fromtimestamp(data.get("fetchedAt", 0)).strftime("%H:%M")
                        retry = dt.datetime.fromtimestamp(data.get("nextRetryAt", 0)).strftime("%H:%M")
                        self.warnings[profile["id"]] = (
                            f"{profile['label']}: dados de {fetched} · nova tentativa {retry}"
                        )
                    else:
                        self.warnings[profile["id"]] = None
                elif kind == "profile_error":
                    profile, message = payload
                    self._render_profile_error(profile, message)
                    self.last_meter_errors[profile["id"]] = message
                    self.warnings[profile["id"]] = message
                elif kind == "done":
                    self.refreshing = False
                    self.last_refresh_text = f"Última atualização: {dt.datetime.now():%H:%M}"
                    self.last_updated.configure(text=self.last_refresh_text)
                    for profile in self.profiles:
                        self._render_compact_detail(profile)
                    warnings = [warning for warning in self.warnings.values() if warning]
                    if warnings:
                        self.status.configure(text=" · ".join(warnings), fg=YELLOW)
                    else:
                        self.status.configure(text="Atualização concluída", fg=MUTED)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    @staticmethod
    def _update_meter(meter: Meter | CompactBatteryMeter, data: RateLimitWindow | None) -> None:
        if data and data.get("usedPercent") is not None:
            meter.set_data(data.get("usedPercent"), data.get("resetsAt"))
        else:
            meter.set_unavailable("Não informado pela CLI")

    def _render_profile_meters(
        self,
        profile: Profile,
        first: RateLimitWindow | None,
        second: RateLimitWindow | None,
    ) -> None:
        short, week = self.meters[profile["id"]]
        if self.layout == "compact":
            if first and first.get("usedPercent") is not None:
                data, window = first, "5 HORAS"
            elif second:
                data, window = second, "SEMANA"
            else:
                data, window = first, "5 HORAS"
            self._update_meter(short, data)
            self.compact_details[profile["id"]] = {
                "window": window,
                "percent": remaining((data or {}).get("usedPercent")),
                "resetsAt": (data or {}).get("resetsAt"),
            }
            if profile["provider"] == "gemini":
                model_name = str((data or {}).get("modelName") or "Gemini")
                self.compact_details[profile["id"]].update(
                    {
                        "title": f"GEMINI · {model_name.upper()}",
                    }
                )
            self._render_compact_detail(profile)
            return
        if profile["provider"] == "gemini":
            self._update_meter(short, second)
            model_name = str((second or {}).get("modelName") or "Gemini")
            short.title.configure(text=model_name.upper()[:42])
            return
        self._update_meter(short, first)
        if week:
            self._update_meter(week, second)

    def _render_profile_error(self, profile: Profile, message: str) -> None:
        short, week = self.meters[profile["id"]]
        short.set_error(message)
        if self.layout == "compact":
            self.compact_details[profile["id"]] = {
                "window": "LIMITE",
                "percent": None,
                "message": message,
                "error": True,
            }
            self._render_compact_detail(profile)
        if week:
            week.set_error(f"{profile['label']} indisponível")

    def close(self) -> None:
        self._collapse_compact_island(animate=False)
        self._save_position()
        self._close_clients()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
