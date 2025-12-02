"""Canonical API metadata shared across agents and tooling."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class APIMetadata:
    """Describe an environment variable carrying API credentials."""

    key: str
    description: str
    docs_url: str | None = None
    category: str | None = None

    def to_payload(self) -> dict[str, str | None]:
        """Return a serialisable payload describing this entry."""

        return {
            "key": self.key,
            "description": self.description,
            "docs_url": self.docs_url,
            "category": self.category,
        }


_API_METADATA: dict[str, APIMetadata] = {
    "TIINGO_API_KEY": APIMetadata(
        key="TIINGO_API_KEY",
        description=(
            "Tiingo API key used for retrieving historical and real-time market data."
        ),
        docs_url="https://www.tiingo.com/documentation/general/overview",
        category="finance",
    ),
}


def iter_api_metadata() -> Iterable[APIMetadata]:
    """Yield all known API metadata entries."""

    return _API_METADATA.values()


def get_api_info() -> dict[str, str]:
    """Return the legacy API info mapping (env var -> description)."""

    return {key: meta.description for key, meta in _API_METADATA.items()}


API_INFO = get_api_info()

__all__ = ["APIMetadata", "API_INFO", "get_api_info", "iter_api_metadata"]
