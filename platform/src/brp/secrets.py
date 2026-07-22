"""Secret-reference resolution that never persists credential values."""

from __future__ import annotations

import os
from pathlib import Path


class SecretResolutionError(RuntimeError):
    pass


def resolve_secret(reference: str) -> str:
    """Resolve ``ENV_NAME`` or ``file:/mounted/path`` without logging its value."""
    if reference.startswith("file:"):
        path = Path(reference.removeprefix("file:"))
        if not path.is_absolute() or not path.is_file():
            raise SecretResolutionError("secret file reference is unavailable")
        value = path.read_text(encoding="utf-8").strip()
    else:
        value = os.getenv(reference, "").strip()
    if not value:
        raise SecretResolutionError(f"secret reference {reference!r} is unavailable")
    return value
