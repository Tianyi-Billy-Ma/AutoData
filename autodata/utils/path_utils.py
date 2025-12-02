"""Helpers for resolving output/log directories with run-name support."""

from __future__ import annotations

DEFAULT_RUN_NAME = "default_run"


def resolve_run_name(
    value: str | None = None, *, default: str = DEFAULT_RUN_NAME
) -> str:
    """Normalise a run name, falling back to the provided default."""

    candidate = (value or default).strip()
    return candidate or default

