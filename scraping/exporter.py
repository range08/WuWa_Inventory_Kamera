"""Deterministic UTF-8 JSON export helpers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def encode_json(data: Any) -> bytes:
    """Serialize scanner output deterministically without changing its schema."""
    return (
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            sort_keys=isinstance(data, dict),
        )
        + "\n"
    ).encode("utf-8")


def write_json_atomic(path: Path | str, data: Any) -> None:
    """Atomically replace a JSON export after the full payload is written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = encode_json(data)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "wb") as temp:
            temp.write(payload)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
