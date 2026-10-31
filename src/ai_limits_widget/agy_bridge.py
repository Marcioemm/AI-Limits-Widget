"""Entrada mínima executada pelo AGY para persistir somente a cota Gemini."""

from __future__ import annotations

import json
import pathlib
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from ai_limits_widget.agy_integration import save_statusline_payload


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if isinstance(payload, dict):
            save_statusline_payload(payload)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        # A statusline não deve poluir a interface nem interromper o AGY.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
