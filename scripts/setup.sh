#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/.." && pwd)"
widget_python="${AI_LIMITS_PYTHON:-python3}"
venv_dir="${AI_LIMITS_VENV:-$project_root/.venv}"

if ! command -v "$widget_python" >/dev/null 2>&1; then
  echo "Python 3 não foi encontrado. Instale python3, python3-venv e python3-tk." >&2
  exit 1
fi

if ! "$widget_python" -c "import tkinter" >/dev/null 2>&1; then
  echo "Tkinter não foi encontrado. No Ubuntu, execute: sudo apt install python3-tk" >&2
  exit 1
fi

if [[ ! -x "$venv_dir/bin/python" ]]; then
  if ! "$widget_python" -m venv "$venv_dir"; then
    echo "Não foi possível criar o ambiente virtual. No Ubuntu, instale python3-venv." >&2
    exit 1
  fi
fi

venv_python="$venv_dir/bin/python"
if ! "$venv_python" -m pip install --disable-pip-version-check --editable "$project_root"; then
  echo "Não foi possível instalar o widget no ambiente virtual." >&2
  exit 1
fi

data_home="${XDG_DATA_HOME:-${HOME:?HOME não definido}/.local/share}"
applications_dir="$data_home/applications"
desktop_template="$project_root/packaging/linux/ai-limits-widget.desktop.in"
desktop_target="$applications_dir/ai-limits-widget.desktop"
entrypoint="$venv_dir/bin/ai-limits-widget"

mkdir -p "$applications_dir"
escaped_entrypoint="$(printf '%s' "$entrypoint" | sed 's/[&|]/\\&/g')"
sed "s|@AI_LIMITS_EXECUTABLE@|$escaped_entrypoint|g" "$desktop_template" > "$desktop_target"
chmod 0644 "$desktop_target"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
fi

echo "AI Limits Widget instalado para este usuário."
echo "Menu: procure por AI Limits Widget."
echo "Terminal: $entrypoint"
