"""Minimal .env loader for local development."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(env_path: str | None = None) -> None:
    """Load key=value pairs from a .env file into os.environ if not set."""
    path = Path(env_path) if env_path else Path(__file__).with_name(".env")
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value