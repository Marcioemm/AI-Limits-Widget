"""Janela de preferências do widget."""

from __future__ import annotations

import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from typing import Any, Protocol

try:
    from ..agy_integration import bridge_command, install_statusline, remove_statusline
    from ..config import save_config
    from ..models import PROVIDERS, AppConfig, Profile
    from ..startup import set_start_with_windows
except ImportError:  # Execução direta de app.py.
    from agy_integration import bridge_command, install_statusline, remove_statusline
    from config import save_config
    from models import PROVIDERS, AppConfig, Profile
    from startup import set_start_with_windows
from .theme import BG, LINE, MUTED, PANEL, PANEL_2, TEXT, provider_visuals


class SettingsHost(Protocol):
    root: tk.Tk
    config: AppConfig
    layout: str

    def rescan_integrations(self) -> None: ...


class SettingsDialog(tk.Toplevel):
    """Configuração local. Nunca lê ou grava tokens, apenas caminhos e perfis."""

    def __init__(self, widget: SettingsHost) -> None:
        super().__init__(widget.root)
        self.widget = widget
        self.config: AppConfig = widget.config.copy()
        self.title("Configurações — Limites de IA")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(widget.root)
        self.grab_set()

        enabled = set(self.config["providers"])
        self.provider_vars = {
            "codex": tk.BooleanVar(value="codex" in enabled),
            "claude": tk.BooleanVar(value="claude" in enabled),
            "gemini": tk.BooleanVar(value="gemini" in enabled),
        }
        self.path_vars = {
            provider: tk.StringVar(value=self.config["executables"].get(provider) or "") for provider in PROVIDERS
        }
        self.refresh_var = tk.StringVar(value=str(self.config["refreshMinutes"]))
        self.start_with_windows_var = tk.BooleanVar(value=self.config["startWithWindows"])
        self.primary_profile_var = tk.StringVar()
        self.compact_visible_count_var = tk.IntVar(value=self.config["compactVisibleCount"])
        self.primary_choice_ids: dict[str, str] = {}
        self.extra_profiles: list[Profile] = [
            dict(item)
            for item in self.config.get("profiles", [])
            if isinstance(item, dict) and item.get("id") not in {"codex-default", "claude-default", "gemini-default"}
        ]
        self._build()

    def _label(self, master: tk.Misc, text: str) -> tk.Label:
        label = tk.Label(master, text=text, bg=BG, fg=TEXT, font=("Segoe UI", 9))
        label.pack(anchor="w", pady=(8, 2))
        return label

    def _build(self) -> None:
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=12)
        tk.Label(body, text="CONFIGURAÇÕES", bg=BG, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(
            body,
            text="Os caminhos são opcionais: em branco, o widget procura a CLI instalada no sistema.",
            bg=BG,
            fg=MUTED,
            justify="left",
            wraplength=480,
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(3, 5))

        providers = tk.Frame(body, bg=BG)
        providers.pack(anchor="w")
        tk.Checkbutton(
            providers,
            text="Codex CLI",
            variable=self.provider_vars["codex"],
            bg=BG,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=BG,
            activeforeground=TEXT,
            command=self._refresh_primary_choices,
        ).pack(side="left", padx=(0, 14))
        tk.Checkbutton(
            providers,
            text="Claude Code",
            variable=self.provider_vars["claude"],
            bg=BG,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=BG,
            activeforeground=TEXT,
            command=self._refresh_primary_choices,
        ).pack(side="left", padx=(0, 14))
        tk.Checkbutton(
            providers,
            text="Gemini (AGY)",
            variable=self.provider_vars["gemini"],
            bg=BG,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=BG,
            activeforeground=TEXT,
            command=self._refresh_primary_choices,
        ).pack(side="left")

        for provider, title in (
            ("codex", "Executável do Codex CLI"),
            ("claude", "Executável do Claude Code"),
            ("gemini", "Executável do Antigravity CLI (agy)"),
        ):
            self._label(body, title)
            row = tk.Frame(body, bg=BG)
            row.pack(fill="x")
            tk.Entry(
                row,
                textvariable=self.path_vars[provider],
                width=51,
                bg=PANEL,
                fg=TEXT,
                insertbackground=TEXT,
                relief="flat",
            ).pack(side="left", ipady=4)
            self._action_button(row, "Procurar…", lambda key=provider: self._choose_executable(key)).pack(
                side="left", padx=(6, 0)
            )

        self._label(body, "Intervalo de atualização (minutos, de 5 a 120)")
        tk.Entry(
            body, textvariable=self.refresh_var, width=8, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat"
        ).pack(anchor="w", ipady=4)

        tk.Checkbutton(
            body,
            text="Abrir o widget automaticamente ao iniciar o Windows",
            variable=self.start_with_windows_var,
            bg=BG,
            fg=TEXT,
            selectcolor=PANEL_2,
            activebackground=BG,
            activeforeground=TEXT,
        ).pack(anchor="w", pady=(10, 0))

        tk.Label(
            body,
            text="Gemini usa a statusline oficial do AGY. Ao salvar, o widget ativa um coletor local que guarda somente modelo, percentual e renovação.",
            bg=BG,
            fg=MUTED,
            justify="left",
            wraplength=480,
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(8, 0))

        self._label(body, "Perfis adicionais")
        profile_row = tk.Frame(body, bg=BG)
        profile_row.pack(fill="x")
        self.profile_list = tk.Listbox(
            profile_row,
            height=4,
            width=53,
            bg=PANEL,
            fg=TEXT,
            selectbackground=LINE,
            relief="flat",
            highlightthickness=0,
        )
        self.profile_list.pack(side="left", fill="x", expand=True)
        side = tk.Frame(profile_row, bg=BG)
        side.pack(side="left", padx=(6, 0))
        self._action_button(side, "Adicionar", self._add_profile).pack(fill="x")
        self._action_button(side, "Remover", self._remove_profile).pack(fill="x", pady=(5, 0))
        self._refresh_profile_list()

        self._label(body, "Indicador principal da ilha compacta")
        self.primary_menu_button = tk.Menubutton(
            body,
            textvariable=self.primary_profile_var,
            bg=PANEL,
            fg=TEXT,
            activebackground=LINE,
            activeforeground=TEXT,
            relief="flat",
            anchor="w",
            width=42,
            padx=8,
            pady=5,
        )
        self.primary_menu = tk.Menu(self.primary_menu_button, tearoff=False, bg=PANEL_2, fg=TEXT)
        self.primary_menu_button.configure(menu=self.primary_menu)
        self.primary_menu_button.pack(anchor="w")
        self._refresh_primary_choices()

        self._label(body, "Baterias visíveis na pílula reduzida")
        tk.Spinbox(
            body,
            from_=1,
            to=3,
            textvariable=self.compact_visible_count_var,
            width=5,
            bg=PANEL,
            fg=TEXT,
            buttonbackground=PANEL_2,
            insertbackground=TEXT,
            relief="flat",
        ).pack(anchor="w", ipady=3)

        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x", pady=(14, 0))
        self._action_button(actions, "Cancelar", self.destroy).pack(side="right")
        self._action_button(actions, "Salvar e verificar", self._save).pack(side="right", padx=(0, 6))

    @staticmethod
    def _action_button(master: tk.Misc, text: str, command: Any) -> tk.Button:
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

    def _choose_executable(self, provider: str) -> None:
        filename = filedialog.askopenfilename(
            parent=self,
            title=f"Selecione o executável do {provider.title()}",
            filetypes=[("Executáveis", "*.exe *.cmd"), ("Todos os arquivos", "*.*")],
        )
        if filename:
            self.path_vars[provider].set(filename)

    def _refresh_profile_list(self) -> None:
        self.profile_list.delete(0, tk.END)
        for profile in self.extra_profiles:
            directory = profile.get("configDir") or "padrão"
            self.profile_list.insert(
                tk.END, f"{profile.get('provider', 'codex').upper()} · {profile.get('label', 'Perfil')} · {directory}"
            )

    def _refresh_primary_choices(self) -> None:
        if not hasattr(self, "primary_menu"):
            return
        previous_id = self.primary_choice_ids.get(
            self.primary_profile_var.get(), self.config.get("compactPrimaryProfileId")
        )
        profiles = [
            {"id": f"{provider}-default", "provider": provider, "label": "Padrão"}
            for provider, variable in self.provider_vars.items()
            if variable.get()
        ]
        profiles.extend(profile for profile in self.extra_profiles if profile.get("provider") in {"codex", "claude"})
        self.primary_choice_ids = {}
        self.primary_menu.delete(0, tk.END)
        for profile in profiles:
            _accent, provider_name, _company = provider_visuals(profile["provider"])
            label = f"{provider_name.title()} · {profile.get('label', 'Perfil')}"
            if label in self.primary_choice_ids:
                label = f"{label} · {profile['id']}"
            self.primary_choice_ids[label] = profile["id"]
            self.primary_menu.add_command(
                label=label,
                command=lambda value=label: self.primary_profile_var.set(value),
            )
        selected_label = next(
            (label for label, profile_id in self.primary_choice_ids.items() if profile_id == previous_id),
            next(iter(self.primary_choice_ids), "Nenhum perfil disponível"),
        )
        self.primary_profile_var.set(selected_label)

    def _add_profile(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Adicionar perfil")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        provider = tk.StringVar(value="codex")
        label = tk.StringVar()
        config_dir = tk.StringVar()
        frame = tk.Frame(dialog, bg=BG)
        frame.pack(padx=14, pady=12)
        for text, variable in (
            ("Provedor (codex ou claude)", provider),
            ("Nome do perfil", label),
            ("Pasta de configuração (opcional)", config_dir),
        ):
            tk.Label(frame, text=text, bg=BG, fg=TEXT, font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 2))
            tk.Entry(
                frame, textvariable=variable, width=48, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat"
            ).pack(ipady=4)

        def choose_dir() -> None:
            directory = filedialog.askdirectory(parent=dialog, title="Selecione a pasta de configuração")
            if directory:
                config_dir.set(directory)

        self._action_button(frame, "Escolher pasta…", choose_dir).pack(anchor="w", pady=(5, 0))

        def add() -> None:
            provider_name = provider.get().strip().lower()
            profile_label = label.get().strip()
            if provider_name not in {"codex", "claude"} or not profile_label:
                messagebox.showerror("Perfil", "Informe codex ou claude e um nome para o perfil.", parent=dialog)
                return
            safe_label = (
                "".join(char if char.isalnum() else "-" for char in profile_label.lower()).strip("-") or "perfil"
            )
            self.extra_profiles.append(
                {
                    "id": f"{provider_name}-{safe_label}-{len(self.extra_profiles) + 1}",
                    "provider": provider_name,
                    "label": profile_label[:40],
                    "executable": self.path_vars[provider_name].get().strip() or None,
                    "configDir": config_dir.get().strip() or None,
                }
            )
            self._refresh_profile_list()
            self._refresh_primary_choices()
            dialog.destroy()

        self._action_button(frame, "Adicionar perfil", add).pack(anchor="e", pady=(12, 0))

    def _remove_profile(self) -> None:
        selection = self.profile_list.curselection()
        if selection:
            del self.extra_profiles[selection[0]]
            self._refresh_profile_list()
            self._refresh_primary_choices()

    def _save(self) -> None:
        providers = [name for name, variable in self.provider_vars.items() if variable.get()]
        if not providers:
            messagebox.showerror("Configurações", "Selecione pelo menos um provedor.", parent=self)
            return
        try:
            refresh_minutes = max(5, min(120, int(self.refresh_var.get())))
        except ValueError:
            messagebox.showerror("Configurações", "O intervalo deve ser um número entre 5 e 120.", parent=self)
            return
        executables = {provider: variable.get().strip() or None for provider, variable in self.path_vars.items()}
        start_with_windows = self.start_with_windows_var.get()
        primary_profile_id = self.primary_choice_ids.get(self.primary_profile_var.get())
        try:
            compact_visible_count = max(1, min(3, int(self.compact_visible_count_var.get())))
        except (tk.TclError, TypeError, ValueError):
            messagebox.showerror("Configurações", "Escolha entre 1 e 3 baterias visíveis.", parent=self)
            return
        profiles = [
            {
                "id": f"{provider}-default",
                "provider": provider,
                "label": "Padrão",
                "executable": executables[provider],
                "configDir": None,
            }
            for provider in providers
        ]
        profiles.extend(profile for profile in self.extra_profiles if profile.get("provider") != "gemini")
        integration: str | None = None
        remove_agy_after_save = "gemini" not in providers
        if "gemini" in providers:
            try:
                integration = install_statusline(command=bridge_command())
            except RuntimeError as exc:
                messagebox.showerror("Integração com AGY", str(exc), parent=self)
                return
            if integration == "conflict":
                messagebox.showerror(
                    "Integração com AGY",
                    "O AGY já possui uma statusline personalizada. Ela não foi sobrescrita. "
                    "Remova ou integre essa configuração manualmente antes de ativar o Gemini.",
                    parent=self,
                )
                return
        try:
            set_start_with_windows(start_with_windows)
        except OSError as exc:
            if integration == "installed":
                remove_statusline()
            messagebox.showerror(
                "Inicialização automática",
                f"Não foi possível atualizar a inicialização do Windows: {exc}",
                parent=self,
            )
            return
        try:
            save_config(
                {
                    "providers": providers,
                    "refreshMinutes": refresh_minutes,
                    "layout": self.widget.layout,
                    "executables": executables,
                    "profiles": profiles,
                    "startWithWindows": start_with_windows,
                    "compactPrimaryProfileId": primary_profile_id,
                    "compactVisibleCount": compact_visible_count,
                }
            )
        except OSError as exc:
            if integration == "installed":
                remove_statusline()
            try:
                set_start_with_windows(self.config["startWithWindows"])
            except OSError:
                pass
            messagebox.showerror("Configurações", f"Não foi possível salvar as configurações: {exc}", parent=self)
            return
        if remove_agy_after_save:
            remove_statusline()
        self.widget.rescan_integrations()
        self.destroy()
