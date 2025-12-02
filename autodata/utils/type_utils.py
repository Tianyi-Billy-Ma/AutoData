"""Type utilities for AutoData.

This module provides reusable helpers for:
* Converting objects into JSON/YAML serialisable structures
* Normalising configuration objects
* Pretty-printing arbitrary payloads
* Basic type coercions and safe casting
"""

from __future__ import annotations

import json
import logging
import textwrap
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any, Protocol, TypeVar

from easydict import EasyDict

try:  # pragma: no cover - optional during static analysis
    from pydantic import BaseModel
except ImportError:  # pragma: no cover
    BaseModel = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    from langchain_core.messages import BaseMessage
except ImportError:  # pragma: no cover
    BaseMessage = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    from langchain_core.messages import HumanMessage
except ImportError:  # pragma: no cover
    HumanMessage = None  # type: ignore[assignment]

try:  # pragma: no cover - optional import to avoid hard dependency during typing
    from autodata.core.ohcache.formatter import BaseResponse
except Exception:  # pragma: no cover
    BaseResponse = None  # type: ignore[assignment]


class ModelDumpProtocol(Protocol):
    """Protocol for objects exposing a ``model_dump`` method."""

    def model_dump(self) -> Any:  # pragma: no cover - structural protocol
        ...


T = TypeVar("T")

_DEFAULT_TRUTHY = frozenset({"true", "1", "yes", "on"})
_DEFAULT_FALSY = frozenset({"false", "0", "no", "off"})


def coerce_primitive(
    value: Any,
    target_type: type[T],
    *,
    truthy: Iterable[str] | None = None,
    falsy: Iterable[str] | None = None,
    allow_none: bool = False,
) -> T:
    """Coerce ``value`` into ``target_type`` using shared rules for primitives.

    Args:
        value: Input value to coerce.
        target_type: Primitive type to coerce to (bool, int, float, str, Path).
        truthy: Optional override for string tokens considered truthy.
        falsy: Optional override for string tokens considered falsy.
        allow_none: Return ``None`` when the input is ``None`` (default: False).

    Returns:
        Value coerced to ``target_type``.

    Raises:
        TypeError: If coercion is not possible.
    """

    if allow_none and value is None:
        return None  # type: ignore[return-value]
    if isinstance(value, target_type):
        return value

    if target_type is bool:
        if isinstance(value, bool):
            return value  # type: ignore[return-value]

        truthy_tokens = {token.lower() for token in (truthy or _DEFAULT_TRUTHY)}
        falsy_tokens = {token.lower() for token in (falsy or _DEFAULT_FALSY)}

        if isinstance(value, str):
            key = value.strip().lower()
            if key in truthy_tokens:
                return True  # type: ignore[return-value]
            if key in falsy_tokens:
                return False  # type: ignore[return-value]
            # Preserve historical behaviour: unknown strings evaluate to False.
            return False  # type: ignore[return-value]

        if isinstance(value, (int, float)):
            return bool(value)  # type: ignore[return-value]

        return bool(value)  # type: ignore[return-value]

    if target_type is int:
        if isinstance(value, bool):
            return int(value)  # type: ignore[return-value]
        return int(value)  # type: ignore[return-value]

    if target_type is float:
        return float(value)  # type: ignore[return-value]

    if target_type is str:
        if value is None:
            raise TypeError("Cannot convert None to str")
        return str(value)  # type: ignore[return-value]

    if target_type is Path:
        return ensure_path(value)  # type: ignore[return-value]

    raise TypeError(f"Unsupported primitive target type: {target_type!r}")


def convert_paths(obj: Path | dict | list | tuple | set) -> Any:
    """Convert Path objects to strings recursively for serialization.

    This function recursively traverses dictionaries, lists, and other containers
    to convert any Path objects to string representations, making them suitable
    for YAML/JSON serialization.

    Args:
        obj: The object to convert (can be dict, list, Path, or any other type)

    Returns:
        The converted object with Path instances replaced by strings

    Examples:
        >>> from pathlib import Path
        >>> data = {"path": Path("/home/user"), "list": [Path("/tmp")]}
        >>> convert_paths(data)
        {"path": "/home/user", "list": ["/tmp"]}
    """
    if isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: convert_paths(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_paths(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_paths(item) for item in obj)
    elif isinstance(obj, set):
        return {convert_paths(item) for item in obj}
    return obj


def to_easydict(
    config: Any,
    *,
    include_attrs: tuple[str, ...] = (
        "work_dir",
        "run_dir",
        "log_dir",
        "cache_dir",
        "checkpoint_dir",
    ),
) -> EasyDict:
    """Convert configuration-like objects to ``EasyDict`` instances.

    Args:
        config: Configuration object, mapping, pydantic model, or ``None``.
        include_attrs: Attribute names to extract from the original object when
            available (useful for properties that are not part of serialized
            representations).

    Returns:
        EasyDict: Configuration data normalised for downstream consumers.
    """

    if isinstance(config, EasyDict):
        return config

    if config is None:
        return EasyDict()

    data: dict[str, Any]

    if BaseModel is not None and isinstance(config, BaseModel):
        data = config.model_dump()
        for attr in include_attrs:
            try:
                data[attr] = getattr(config, attr)
            except (AttributeError, ValueError):  # pragma: no cover - defensive
                continue
    elif isinstance(config, dict):
        data = dict(config)
    else:
        if hasattr(config, "dict") and callable(config.dict):
            data = config.dict()  # type: ignore[assignment]
        elif hasattr(config, "__dict__"):
            data = {
                key: value
                for key, value in vars(config).items()
                if not key.startswith("_")
            }
        else:
            data = {"value": config}

        for attr in include_attrs:
            if attr not in data:
                try:
                    data[attr] = getattr(config, attr)
                except (AttributeError, ValueError):  # pragma: no cover
                    continue

    normalised = convert_paths(data)
    return EasyDict(normalised)


def ensure_serializable(value: Any) -> Any:
    """Convert arbitrary objects into Python built-ins for persistence.

    The function preserves rich object metadata when possible while ensuring
    the return value can be safely stored in JSON/YAML or cached structures.
    """

    if BaseResponse is not None and isinstance(value, BaseResponse):
        return {
            "type": value.__class__.__name__,
            "payload": value.to_dict(),
        }

    if BaseMessage is not None and isinstance(value, BaseMessage):
        return {
            "type": value.__class__.__name__,
            "payload": {
                "content": getattr(value, "content", None),
                "additional_kwargs": getattr(value, "additional_kwargs", {}) or {},
                "response_metadata": getattr(value, "response_metadata", {}) or {},
                "name": getattr(value, "name", None),
                "tool_calls": getattr(value, "tool_calls", None),
            },
        }

    if isinstance(value, dict | list | str | int | float | bool) or value is None:
        return value

    if isinstance(value, bytes | bytearray):
        return value.decode("utf-8", errors="replace")

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return model_dump()
        except Exception:
            pass

    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        try:
            return dict_method()
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        return {
            "type": value.__class__.__name__,
            "payload": {
                key: ensure_serializable(inner)
                for key, inner in vars(value).items()
                if not key.startswith("_")
            },
            "source": "attrs",
        }

    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError):
        return {
            "type": type(value).__name__,
            "payload": repr(value),
            "source": "repr",
        }


def pretty_format_object(obj: object) -> str:
    """Return a human-friendly string representation of ``obj``."""

    def _json_default(value: object) -> Any:
        serialised = ensure_serializable(value)
        if (
            isinstance(serialised, dict | list | str | int | float | bool)
            or serialised is None
        ):
            return serialised
        return repr(value)

    target = obj
    if BaseModel is not None and isinstance(obj, BaseModel):
        target = obj.model_dump()

    if isinstance(target, dict | list):
        pretty = json.dumps(target, ensure_ascii=False, indent=2, default=_json_default)
        return "\n" + textwrap.indent(pretty, prefix="    ")

    if hasattr(target, "to_message"):
        target = str(target.to_message())

    if isinstance(target, str):
        try:
            parsed = json.loads(target)
            target = json.dumps(parsed, ensure_ascii=False, indent=2)
        except Exception:
            pass

    result = str(getattr(target, "__dict__", target))
    if "\n" in result:
        return "\n" + textwrap.indent(result, prefix="    ")

    wrapped = textwrap.fill(result, width=100, subsequent_indent="    ")
    return "\n" + textwrap.indent(wrapped, prefix="    ")


def ensure_path(obj: Any) -> Path:
    """Ensure an object is a Path instance.

    Args:
        obj: Object to convert to Path (str, Path, or path-like)

    Returns:
        Path instance

    Raises:
        TypeError: If obj cannot be converted to Path

    Examples:
        >>> ensure_path("/home/user")
        PosixPath('/home/user')
        >>> ensure_path(Path("/home/user"))
        PosixPath('/home/user')
    """
    if isinstance(obj, Path):
        return obj
    elif isinstance(obj, str | bytes):
        return Path(obj)
    else:
        raise TypeError(f"Cannot convert {type(obj)} to Path")


def is_path_like(obj: Any) -> bool:
    """Check if an object is path-like (str, bytes, or Path).

    Args:
        obj: Object to check

    Returns:
        True if object is path-like, False otherwise

    Examples:
        >>> is_path_like("/home/user")
        True
        >>> is_path_like(Path("/home/user"))
        True
        >>> is_path_like(123)
        False
    """
    return isinstance(obj, str | bytes | Path)


def normalize_type(obj: Any, target_type: type) -> Any:
    """Normalize an object to a target type with common conversions.

    Args:
        obj: Object to normalize
        target_type: Target type to convert to

    Returns:
        Converted object

    Raises:
        TypeError: If conversion is not possible

    Examples:
        >>> normalize_type("123", int)
        123
        >>> normalize_type("true", bool)
        True
    """
    if isinstance(obj, target_type):
        return obj

    # Common type conversions
    if target_type is bool:
        return coerce_primitive(obj, bool)
    elif target_type is int:
        return coerce_primitive(obj, int)
    elif target_type is float:
        return coerce_primitive(obj, float)
    elif target_type is str:
        return coerce_primitive(obj, str)
    elif target_type is Path:
        return coerce_primitive(obj, Path)
    else:
        raise TypeError(f"Cannot convert {type(obj)} to {target_type}")


def safe_cast(obj: Any, target_type: type, default: Any = None) -> Any:
    """Safely cast an object to a target type with fallback.

    Args:
        obj: Object to cast
        target_type: Target type
        default: Default value if casting fails

    Returns:
        Casted object or default value

    Examples:
        >>> safe_cast("123", int, 0)
        123
        >>> safe_cast("invalid", int, 0)
        0
    """
    try:
        return normalize_type(obj, target_type)
    except (TypeError, ValueError):
        return default


def is_empty_value(value: Any) -> bool:
    """Check if a value should be considered empty for override purposes.

    This function determines whether a value is "empty" and should be ignored
    when applying configuration overrides. Empty values include None, empty
    strings (after stripping whitespace), and empty collections.

    Args:
        value: The value to check for emptiness

    Returns:
        True if the value is considered empty, False otherwise

    Examples:
        >>> is_empty_value(None)
        True
        >>> is_empty_value("")
        True
        >>> is_empty_value("  ")
        True
        >>> is_empty_value([])
        True
        >>> is_empty_value("hello")
        False
        >>> is_empty_value([1, 2, 3])
        False
    """
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, list | dict | tuple) and len(value) == 0:
        return True
    return False


def normalize_messages(
    messages: Sequence[Any] | None,
    *,
    sender: str | None = None,
    message_cls: type | None = None,
) -> list:
    """Normalise a sequence of messages into LangChain ``BaseMessage`` objects.

    Strings and ``BaseResponse`` instances are converted into ``HumanMessage``
    instances by default. Existing ``BaseMessage`` objects are deep-copied to
    avoid mutating caller state.

    Args:
        messages: Sequence containing ``BaseMessage``, ``BaseResponse``, or ``str``.
        sender: Optional sender name applied to newly created messages.
        message_cls: Override for the message class used when synthesising
            messages. Defaults to LangChain's ``HumanMessage`` when available.

    Returns:
        List of ``BaseMessage`` instances.
    """

    if not messages:
        return []

    if BaseMessage is None:
        raise RuntimeError(
            "langchain_core is required to normalise messages; install the "
            "dependency or provide ready-made BaseMessage instances."
        )

    resolved_cls = message_cls
    if resolved_cls is None:
        if HumanMessage is None:
            raise RuntimeError(
                "HumanMessage is unavailable; provide 'message_cls' explicitly."
            )
        resolved_cls = HumanMessage

    normalised: list[BaseMessage] = []
    for item in messages:
        if isinstance(item, BaseMessage):
            normalised.append(deepcopy(item))
            continue

        if BaseResponse is not None and isinstance(item, BaseResponse):
            content = item.to_message()
            normalised.append(resolved_cls(content=content, name=sender))
            continue

        if isinstance(item, str):
            normalised.append(resolved_cls(content=item, name=sender))
            continue

        if isinstance(item, Mapping):
            payload = dict(item)
            content = payload.get("content")
            if content is None:
                content = json.dumps(payload, ensure_ascii=False, indent=2)
            normalised.append(
                resolved_cls(content=content, name=payload.get("name", sender))
            )
            continue

        model_dump = getattr(item, "model_dump", None)
        if callable(model_dump):
            try:
                payload = model_dump()
            except Exception:  # pragma: no cover - defensive
                payload = {"content": str(item)}
            content = payload.get("content")
            if content is None:
                content = json.dumps(payload, ensure_ascii=False, indent=2)
            normalised.append(resolved_cls(content=content, name=sender))
            continue

        raise TypeError(
            f"Unsupported message payload type: {type(item).__name__}. "
            "Expected BaseMessage, BaseResponse, str, or mapping."
        )

    return normalised


def coerce_cache_descriptor(
    descriptor: Mapping[str, Any] | None,
    *,
    inline_payload_key: str = "payload",
) -> dict[str, Any]:
    """Normalise cache descriptor payloads for persistence and inspection."""

    if not descriptor:
        return {}

    normalised: dict[str, Any] = {}
    for key, value in dict(descriptor).items():
        if key == "metadata":
            normalised[key] = ensure_serializable(convert_paths(value))
        elif key == "tags":
            if isinstance(value, (set, frozenset)):
                normalised[key] = sorted(value)
            elif isinstance(value, list | tuple):
                normalised[key] = list(value)
            else:
                normalised[key] = value
        elif key == inline_payload_key:
            normalised[key] = ensure_serializable(convert_paths(value))
        elif key == "stored_inline":
            normalised[key] = bool(value)
        else:
            normalised[key] = value

    return normalised


def normalize_cache_descriptor(
    descriptor: Mapping[str, Any] | None,
    *,
    inline_payload_key: str = "payload",
) -> dict[str, Any]:
    """Alias for ``coerce_cache_descriptor`` for backwards compatibility."""

    return coerce_cache_descriptor(descriptor, inline_payload_key=inline_payload_key)


def handle_browser_use_record(record: logging.LogRecord) -> logging.LogRecord:
    """Handle a browser-use log record.

    Args:
        record: The log record to handle

    Returns:
        The handled log record
    """
    if isinstance(record.name, str) and record.name.startswith("browser_use."):
        # Extract clean component names from logger names
        if "Agent" in record.name:
            record.name = "browser_use.Agent"
        elif "BrowserSession" in record.name:
            record.name = "browser_use.BrowserSession"
        elif "tools" in record.name:
            record.name = "browser_use.tools"
        elif "dom" in record.name:
            record.name = "browser_use.dom"
        elif record.name.startswith("browser_use."):
            # For other browser_use modules, use the last part
            parts = record.name.split(".")
            if len(parts) >= 2:
                record.name = "browser_use." + parts[-1]
    return record


__all__ = [
    "ModelDumpProtocol",
    "coerce_cache_descriptor",
    "coerce_primitive",
    "ensure_serializable",
    "convert_paths",
    "ensure_path",
    "is_empty_value",
    "is_path_like",
    "normalize_cache_descriptor",
    "normalize_messages",
    "normalize_type",
    "pretty_format_object",
    "safe_cast",
    "to_easydict",
    "handle_browser_use_record",
]
