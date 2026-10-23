#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "$script_dir/.." && pwd)"
venv_python="$project_root/.venv/bin/python"

if [[ -n "${AI_LIMITS_PYTHON:-}" ]]; then
  widget_python="$AI_LIMITS_PYTHON"
elif [[ -x "$venv_python" ]]; then
  widget_python="$venv_python"
elif command -v python3 >/dev/null 2>&1; then
  widget_python="$(command -v python3)"
else
  echo "Python 3 não foi encontrado. Instale python3 e python3-tk." >&2
  exit 1
fi

if ! "$widget_python" -c "import tkinter" >/dev/null 2>&1; then
  echo "Tkinter não foi encontrado. No Ubuntu, execute: sudo apt install python3-tk" >&2
  exit 1
fi

export PYTHONPATH="$project_root/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$widget_python" -m ai_limits_widget "$@"
