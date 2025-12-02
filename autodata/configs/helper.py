"""Utilities for loading configuration sources and environment variables."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import toml
import yaml
from dotenv import load_dotenv

logger = logging.getLogger("AutoData.configs")

SUPPORTED_CONFIG_FORMATS = {".yaml", ".yml", ".json", ".toml"}
_DEFAULT_ENV_PATHS = [
    Path.cwd() / ".env",
    Path.cwd() / ".env.local",
    Path.home() / ".autodata" / ".env",
]


def verify_environment_variables() -> None:
    """Emit log statements describing discovered API credentials."""

    required_vars: dict[str, str] = {}
    optional_vars: dict[str, str] = {
        "OPENAI_API_KEY": "OpenAI API access",
        "ANTHROPIC_API_KEY": "Anthropic Claude API access",
        "GOOGLE_API_KEY": "Google AI API access",
        "OPENROUTER_API_KEY": "OpenRouter API access (third-party provider)",
        "OPENROUTER_BASE_URL": "OpenRouter base URL (default: https://openrouter.ai/api/v1)",
        "LANGSMITH_API_KEY": "LangSmith tracing and monitoring",
        "TAVILY_API_KEY": "Tavily search API access",
    }

    missing_vars: list[str] = []
    available_vars: list[str] = []

    for var, description in required_vars.items():
        if os.getenv(var):
            available_vars.append(f"  ✅ {var}: {description}")
        else:
            missing_vars.append(f"  ❌ {var}: {description}")

    for var, description in optional_vars.items():
        if os.getenv(var):
            available_vars.append(f"  ✅ {var}: {description}")

    if available_vars:
        logger.info("🔑 Available API keys:")
        for var in available_vars:
            logger.info(var)

    if missing_vars:
        logger.warning("⚠️ Missing optional API keys (functionality may be limited):")
        for var in missing_vars:
            logger.warning(var)
        logger.warning(
            "💡 Add these to your .env file or set as environment variables for full functionality."
        )


def load_environment_variables_from_file(env_path: Path | None = None) -> None:
    """Load environment variables from the provided path or default locations."""

    if env_path:
        if env_path.exists():
            load_dotenv(env_path)
            logger.info("✅ Loaded environment variables from: %s", env_path)
        else:
            logger.warning("⚠️ Environment file not found: %s", env_path)
    else:
        loaded = False
        for default_path in _DEFAULT_ENV_PATHS:
            if default_path.exists():
                load_dotenv(default_path)
                logger.info("✅ Loaded environment variables from: %s", default_path)
                loaded = True
                break

        if not loaded:
            logger.info(
                "ℹ️ No .env file found in default locations. Using system environment variables."
            )

    verify_environment_variables()


def normalize_config_format(config_format: str | None, config_path: Path) -> str:
    """Normalise a config format into a dotted, lowercase extension."""

    if config_format is None or str(config_format).strip() == "":
        fmt = config_path.suffix.lower()
    else:
        fmt = str(config_format).strip().lower()

    if fmt and not fmt.startswith("."):
        fmt = f".{fmt}"

    return fmt


def load_config_data(config_path: Path, config_format: str) -> dict[str, Any]:
    """Load raw configuration data from disk."""

    with open(config_path, encoding="utf-8") as fh:
        if config_format in {".yaml", ".yml"}:
            data = yaml.safe_load(fh)
        elif config_format == ".json":
            data = json.load(fh)
        elif config_format == ".toml":
            data = toml.load(fh)
        else:
            raise ValueError(f"Unsupported format: {config_format}")

    if isinstance(data, dict):
        return data
    return {}


def dump_config_data(
    config_data: dict[str, Any],
    config_path: Path,
    config_format: str,
) -> None:
    """Persist configuration data to disk in the requested format."""

    with open(config_path, "w", encoding="utf-8") as fh:
        if config_format in {".yaml", ".yml"}:
            yaml.dump(config_data, fh, default_flow_style=False, indent=2)
        elif config_format == ".json":
            json.dump(config_data, fh, indent=2, ensure_ascii=False)
        elif config_format == ".toml":
            toml.dump(config_data, fh)
        else:
            raise ValueError(f"Unsupported format: {config_format}")


def detect_config_override(
    args: list[str] | None = None,
    *,
    explicit_path: str | None = None,
    explicit_format: str | None = None,
) -> tuple[dict[str, Any], Path, str | None]:
    """Detect config overrides from CLI args and load the referenced file."""

    argv = list(args) if args is not None else sys.argv[1:]
    config_path = explicit_path or _extract_arg_value(argv, ["--config", "--config-path", "-c"])
    if not config_path:
        config_path = "configs/default.yaml"

    format_hint = explicit_format or _extract_arg_value(argv, ["--config-format"])
    path_obj = Path(config_path).expanduser()
    if not path_obj.exists():
        raise FileNotFoundError(f"Configuration file not found: {path_obj}")

    normalized_format = normalize_config_format(format_hint, path_obj)
    data = load_config_data(path_obj, normalized_format)
    stored_format = normalized_format.lstrip(".") if normalized_format else None
    return data, path_obj, stored_format


def _extract_arg_value(argv: list[str], flags: list[str]) -> str | None:
    """Extract a CLI option value by scanning for supported flags."""

    for index, token in enumerate(argv):
        for flag in flags:
            if token.startswith(f"{flag}="):
                return token.split("=", 1)[1]
            if token == flag:
                if index + 1 < len(argv):
                    return argv[index + 1]
                return ""
    return None


__all__ = [
    "SUPPORTED_CONFIG_FORMATS",
    "detect_config_override",
    "dump_config_data",
    "load_config_data",
    "load_environment_variables_from_file",
    "normalize_config_format",
    "verify_environment_variables",
]
