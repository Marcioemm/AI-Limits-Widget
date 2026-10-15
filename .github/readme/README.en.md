# AI Limits Widget

🇺🇸 English · [🇪🇸 Español](README.es.md) · [🇧🇷 Português](../../README.md)

A lightweight Windows widget that shows the remaining usage limits for Codex
Claude Code, and Gemini through AGY directly on your desktop.

> This independent project is not affiliated with, endorsed by, or maintained
> by OpenAI, Anthropic, or Google.

## What it does

- Displays the remaining percentage for each usage window rather than making
  up a conversion to “tokens remaining”.
- Refreshes Codex, Claude Code, and the Gemini cache at configurable intervals (five minutes by
  default).
- Works locally and can remain always on top.
- Keeps the last valid Claude value during a temporary rate-limit response.
- Clearly reports an expired session, a missing tool, or an unavailable service.

## What it does not do

- It does not create, increase, or bypass account limits.
- It does not send your data to a server operated by this project.
- It does not store passwords, API keys, or authentication tokens.
- It does not require any subscription beyond the accounts you already have.

## Requirements

- Windows 10 or 11.
- Python 3.10 or later with Tkinter (included with the official Python installer).
- Optional: an authenticated Codex CLI installation, to display Codex.
- Optional: an authenticated Claude Code installation, to display Claude Code.
- Optional: an authenticated Antigravity CLI (`agy`) installation, to display the active Gemini model.

Install only the integrations you plan to use. If a CLI is not installed or is
not authenticated, the widget keeps working and explains why in that provider's
section.

## Install with the installer

Download `AI-Limits-Widget-Setup-<version>.exe` from the
[Releases](https://github.com/Marcioemm/AI-Limits-Widget/releases) page, run
it, and choose the Desktop shortcut if you want one. The installer bundles the
runtime required by the widget, so Python is not needed to use it.

The Codex CLI, Claude Code, and Antigravity CLI (`agy`) remain optional and must be installed and
authenticated under the same Windows account for their limits to appear. The
installer neither copies nor requests credentials.

The Codex desktop app alone does not provide the local integration used by the
widget: also install the [Codex CLI](https://learn.chatgpt.com/docs/codex/cli)
to monitor your limits. For Claude, follow the official
[Claude Code installation guide](https://docs.anthropic.com/en/docs/claude-code/getting-started).
For Gemini, install the [Antigravity CLI](https://antigravity.google/docs/cli/)
and enable **Gemini (AGY)** in Settings. The widget installs a local statusline
bridge that receives the official quota for the active Gemini model.
When neither CLI is available, the widget shows installation links and a
**Check again** button; restarting the app is unnecessary.

## Install from source

1. Clone the repository:

   ```powershell
   git clone https://github.com/Marcioemm/AI-Limits-Widget.git
   cd ai-limits-widget
   ```

2. Start the widget:

   ```powershell
   .\scripts\start.ps1
   ```

   Open **⚙ Settings** in the widget to choose providers, change the refresh
   interval, provide an executable outside `PATH`, and add additional profiles.
   No credentials are requested or stored.

3. Stop only this widget:

   ```powershell
   .\scripts\stop.ps1
   ```

You can drag the widget using its title bar. Its controls let you refresh/check
again, open Settings, copy safe diagnostics, pin, collapse, and close it. Hover
over a title-bar icon to see a short description of its action.

Use the layout button (`⊟`/`⊞`) next to the **AI LIMITS** title to switch
between **Cards** and **Compact**. The choice is saved only on this computer.
In compact mode, each profile is represented by a segmented battery with charge
cells and a percentage inside; up to two batteries appear on each row. It
represents the five-hour window, or the weekly window when the CLI does not
provide a five-hour window. Compact mode does not show a footer or refresh time.
Hover over a battery for one second to expand the widget and quickly see the
profile, tracked window, reset time, and last refresh without making another
request.

The widget always opens on the primary monitor. You can move it freely while
using it, but it returns to the primary monitor the next time it opens.

### Script configuration (optional)

To automate installation, pass options directly:

```powershell
.\scripts\setup.ps1 -Providers both -RefreshMinutes 5 -CreateDesktopShortcut -Start
```

Accepted `-Providers` values are `codex`, `claude`, `gemini`, `both`, and `all`. If the CLI is
not on `PATH`, provide its executable — for example,
`-ClaudePath 'D:\tools\claude.cmd'` or `-AgyPath 'D:\tools\agy.exe'`. Paths are optional: the widget attempts to
find the tools again whenever it opens.

### Multiple accounts

The widget shows a card for every local profile it can identify. The installer
creates default profiles and lets you add others in guided mode. For a second
account, provide a display name and the configuration directory it uses:

- Codex: the directory set as `CODEX_HOME` for that profile.
- Claude Code: the directory set as `CLAUDE_CONFIG_DIR` for that profile,
  containing the local credentials file.

If a CLI or a profile's configuration does not exist, it remains hidden — there
is no empty bar for unavailable providers. The application never searches for
credentials in arbitrary folders: it uses only the default profile or
directories explicitly supplied through the installer.

## Provider configuration

### Codex

Install and authenticate the Codex CLI under the same Windows account. The
widget starts the local Codex process only while checking limits and stops it
immediately afterward to reduce idle memory consumption.

### Claude Code

Install and authenticate Claude Code under the same Windows account. If the
session expires, the widget asks the CLI itself to renew it locally. During
temporary rate-limit responses, the last valid balance is preserved and a new
attempt is automatically scheduled.

### Gemini through Antigravity CLI

The widget uses AGY's official statusline integration. The collector keeps only
the active Gemini model name, weekly percentage, reset time, and collection
time. Claude or GPT models selected in AGY are ignored, and an existing custom
statusline is never overwritten automatically.

Integrations depend on the interfaces offered by the CLIs and may require
changes when those interfaces change.

## Privacy and security

The application checks only the processes and services necessary for the
enabled providers. There are no analytics, remote database, or credentials sent
to this repository. Local data is stored in `%LOCALAPPDATA%\LimitesIA` and
contains only preferences, percentages, and refresh times.

Before opening an issue, read [SECURITY.md](../../SECURITY.md). Never submit
authentication files, tokens, complete logs, or screenshots with private
information. The widget's `?` button copies diagnostics containing only CLI
versions, refresh configuration, and available windows; it does not include
tokens, account IDs, or local paths.

## Troubleshooting

To check limits without opening the window:

```powershell
python .\src\ai_limits_widget\app.py --once
```

If Claude Code reports that the session has expired, run:

```powershell
claude login
```

If Codex cannot be found, verify that the `codex` command works in PowerShell,
then restart the widget.

## Development

The project has no third-party dependencies. For a basic verification:

```powershell
python -m compileall .\src
python -m unittest discover -s .\tests -v
python .\src\ai_limits_widget\app.py --once
```

Contributions are welcome. See [CONTRIBUTING.md](../../CONTRIBUTING.md) for the
fork and pull-request workflow, and use `git commit -s` to sign commits under
the [DCO](../../DCO.md).

## License

Copyright © 2026 Marcio Emmanuel. Distributed under the [MIT License](../../LICENSE).
Also see the [third-party component notices](../../THIRD_PARTY_NOTICES.md).
