"""Deterministic UTF-8 JSON export helpers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class ExportSecurityError(ValueError):
    """Raised when an export contains a credential-like field."""


SENSITIVE_EXPORT_KEYS = frozenset({
    "oauthcode",
    "accesstoken",
    "refreshtoken",
    "authorization",
    "password",
    "passwd",
    "cookie",
    "credential",
    "credentials",
    "secret",
    "clientsecret",
})


def _normalized_key(value: Any) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def assert_no_sensitive_fields(data: Any, path: str = "$") -> None:
    """Reject credential-like dictionary keys anywhere in an export payload."""
    if isinstance(data, dict):
        for key, value in data.items():
            normalized = _normalized_key(key)
            if normalized in SENSITIVE_EXPORT_KEYS:
                raise ExportSecurityError(
                    f"Sensitive export field is not allowed at {path}.{key}"
                )
            assert_no_sensitive_fields(value, f"{path}.{key}")
    elif isinstance(data, (list, tuple)):
        for index, value in enumerate(data):
            assert_no_sensitive_fields(value, f"{path}[{index}]")


def encode_json(data: Any) -> bytes:
    """Serialize scanner output deterministically without changing its schema."""
    assert_no_sensitive_fields(data)
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
