"""Shared tool metadata for AutoData agents."""

from __future__ import annotations

TOOL_INFO: dict[str, str] = {
    "PerplexitySearchTool": (
        "Performs web search via Perplexity to gather up-to-date context, returning a "
        "concise summary and model metadata."
    ),
}


def merge_tool_info(*additional_sources: dict[str, str]) -> dict[str, str]:
    """Return TOOL_INFO merged with any additional plugin-provided descriptions."""

    merged = dict(TOOL_INFO)
    for info in additional_sources:
        if not info:
            continue
        merged.update(info)
    return merged


__all__ = ["TOOL_INFO", "merge_tool_info"]
