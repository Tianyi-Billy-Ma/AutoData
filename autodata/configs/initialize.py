"""AutoData initialization pipeline."""

from __future__ import annotations

import logging
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from easydict import EasyDict
from omegaconf import OmegaConf

from autodata.configs.args import AutoDataConfig
from autodata.configs.helper import detect_config_override, dump_config_data
from autodata.configs.parser import create_argument_parser, get_section_names
from autodata.configs.patch import patch_config
from autodata.configs.validate import validate_config
from autodata.core.exceptions import AutoDataInitializationError
from autodata.core.exceptions.storage import DirectoryCreationError
from autodata.utils.cli_utils import prompt_for_overwrite
from autodata.utils.log_utils import setup_logging
from autodata.utils.type_utils import convert_paths

logger = logging.getLogger("AutoData.configs")


def initialize(
    args: list | None = None,
    config_path: str | None = None,
    run_name: str | None = None,
) -> AutoDataConfig:
    """Initialize AutoData with configuration and CLI arguments.

    This is the main entry point for AutoData initialization.

    Args:
        args: Command-line arguments (if None, uses sys.argv)
        config_path: Override config file path
        run_name: Override run name

    Returns:
        Merged AutoDataConfig instance with CLI args included

    Raises:
        SystemExit: If initialization fails or help is requested
    """
    try:
        # Parse and merge configuration
        config = load_and_merge_configuration(args, config_path, run_name)

        # Validate configuration
        try:
            validate_config(config)
            logger.info("Configuration validation passed")
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise

        # Setup output directory first
        output_dir = setup_output_directory(config)

        # Setup logging with the loaded configuration and output directory
        setup_logging(config.log_config, config.log_dir)

        # Save the processed configuration to the output directory
        save_config(config, output_dir)

        # Log initialization success
        logger.info("AutoData initialized successfully")
        logger.info(f"Run name: {config.run_name}")
        logger.info(f"Output directory: {output_dir}")

        return config

    except Exception as e:
        logger.error("Initialization failed: %s", e)

        raise AutoDataInitializationError(
            str(e),
            details={"cause": str(e)},
            hint="Inspect the log output or re-run with --debug for full stack traces.",
        ) from e


def load_and_merge_configuration(
    args: list[str] | None = None,
    config_path: str | None = None,
    run_name: str | None = None,
) -> AutoDataConfig:
    """Load configuration from disk, merge CLI overrides, and patch sections."""

    parser = create_argument_parser()
    section_names = get_section_names()

    file_data, resolved_path, resolved_format = detect_config_override(
        args=args,
        explicit_path=config_path,
    )
    logger.info("Configuration loaded from %s", resolved_path)

    cli_instances = parser.parse_args_into_dataclasses(args=args)
    default_instances = parser.parse_args_into_dataclasses(args=[], look_for_args_file=False)

    cli_dict = _dataclasses_to_section_dict(section_names, cli_instances)
    default_dict = _dataclasses_to_section_dict(section_names, default_instances)

    cli_overrides = _compute_cli_overrides(section_names, cli_dict, default_dict)

    if resolved_path:
        cli_overrides.setdefault("task_config", {})["config"] = str(resolved_path)
    if resolved_format:
        cli_overrides.setdefault("task_config", {})["config_format"] = resolved_format
    if run_name:
        cli_overrides.setdefault("task_config", {})["run_name"] = run_name

    structured_file = _ensure_section_layout(section_names, file_data)
    merged = _merge_with_priority(structured_file, cli_overrides)
    flat_config = _flatten_sections(section_names, merged)

    parsed_sections = parser.parse_dict(flat_config)
    section_map = EasyDict(zip(section_names, parsed_sections))

    return patch_config(section_map)


def _dataclasses_to_section_dict(
    section_names: tuple[str, ...],
    instances: tuple[Any, ...],
) -> dict[str, dict[str, Any]]:
    """Convert parsed dataclasses into section-indexed dictionaries."""

    return {name: asdict(instance) for name, instance in zip(section_names, instances)}


def _compute_cli_overrides(
    section_names: tuple[str, ...],
    cli_dict: dict[str, dict[str, Any]],
    default_dict: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Return only the CLI values that differ from defaults."""

    overrides: dict[str, dict[str, Any]] = {}
    for name in section_names:
        cli_section = cli_dict.get(name, {})
        default_section = default_dict.get(name, {})
        diffs: dict[str, Any] = {}
        for key, value in cli_section.items():
            if key not in default_section or value != default_section[key]:
                diffs[key] = value
        if diffs:
            overrides[name] = diffs
    return overrides


def _ensure_section_layout(
    section_names: tuple[str, ...],
    data: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Ensure the config dictionary has a dict per section."""

    structured: dict[str, dict[str, Any]] = {}
    for name in section_names:
        section = data.get(name, {})
        structured[name] = dict(section) if isinstance(section, dict) else {}

    # Handle legacy top-level keys for task config if present.
    legacy_keys = {
        "task",
        "run_name",
        "disable_human",
        "task_timeout",
        "execution_strategy",
        "dry_run",
        "verbose",
        "visualize_graph",
        "config",
        "config_format",
    }
    legacy_values = {k: data[k] for k in legacy_keys if k in data}
    if legacy_values:
        structured.setdefault("task_config", {}).update(legacy_values)

    return structured


def _merge_with_priority(
    file_data: dict[str, dict[str, Any]],
    cli_overrides: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Merge file and CLI data with CLI taking precedence."""

    file_conf = OmegaConf.create(file_data)
    if cli_overrides:
        cli_conf = OmegaConf.create(cli_overrides)
        merged = OmegaConf.merge(file_conf, cli_conf)
    else:
        merged = file_conf
    return OmegaConf.to_container(merged, resolve=True)  # type: ignore[return-value]


def _flatten_sections(
    section_names: tuple[str, ...],
    merged: dict[str, Any],
) -> dict[str, Any]:
    """Flatten section dictionaries for HfArgumentParser.parse_dict."""

    flat: dict[str, Any] = {}
    for name in section_names:
        section = merged.get(name, {})
        if isinstance(section, dict):
            flat.update(section)
    return flat


def setup_output_directory(config: AutoDataConfig) -> Path:
    """Setup output directory for the run.

    Args:
        config: Configuration instance (with storage.run_name set)

    Returns:
        Path to the run-specific output directory

    Raises:
        SystemExit: If user declines to overwrite existing directory
    """
    # Get run-specific output directory
    run_output_dir = config.run_dir

    def _handle_directory_error(target: Path, exc: Exception) -> None:
        hint = (
            "Ensure the storage_config output directory is writable or choose a "
            "different run_name/output_dir."
        )
        logger.error(
            "Failed to create required directory %s: %s. %s",
            target,
            exc,
            hint,
        )
        raise DirectoryCreationError(
            target,
            reason=str(exc),
            hint=hint,
        ) from exc

    # Check if directory exists and handle overwrite logic
    if run_output_dir.exists():
        overwrite = config.storage_config.overwrite
        force_overwrite = config.storage_config.force_overwrite

        if not overwrite:
            logger.info(
                "Run directory %s exists; append mode enabled (overwrite disabled).",
                run_output_dir,
            )
            return run_output_dir

        if force_overwrite:
            logger.warning(
                "⚠️ Run directory already exists and will be overwritten (force mode): %s",
                run_output_dir,
            )
        else:
            has_contents = any(run_output_dir.iterdir())
            if not force_overwrite and has_contents:
                if not prompt_for_overwrite(run_output_dir):
                    logger.info(
                        "User declined to overwrite existing directory. Continuing without overwrite."
                    )
                    force_overwrite = False
                    return run_output_dir
                else:
                    force_overwrite = True

            logger.warning(
                "⚠️ Run directory already exists and will be overwritten: %s",
                run_output_dir,
            )

        should_clear = force_overwrite and overwrite
        if should_clear:
            try:
                shutil.rmtree(run_output_dir)
            except FileNotFoundError:
                pass
            except Exception as exc:
                _handle_directory_error(run_output_dir, exc)

    try:
        run_output_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        _handle_directory_error(run_output_dir, exc)

    # Create subdirectories for different types of output
    subdirs = ["logs", "cache", "work", "results", "browser", "checkpoint"]
    for subdir in subdirs:
        path = run_output_dir / subdir
        try:
            path.mkdir(exist_ok=True)
        except Exception as exc:
            _handle_directory_error(path, exc)

    logger.info(f"Run output directory setup complete: {run_output_dir}")

    return run_output_dir


def save_config(config: AutoDataConfig, output_dir: Path) -> None:
    """Save the processed configuration to the output directory.

    This saves the final configuration (after CLI overrides and processing)
    to the task's output directory for reference and reproducibility.

    Args:
        config: Processed configuration instance
        output_dir: Task output directory
    """
    try:
        # Create simple config filename
        config_filename = "config.yaml"
        config_path = output_dir / config_filename

        # Convert config to dictionary
        config_dict = asdict(config)

        # Convert Path objects to strings for YAML serialization
        config_dict = convert_paths(config_dict)

        # Save to YAML file using dump_config_data
        dump_config_data(config_dict, config_path, "yaml")

        logger.info(f"Processed configuration saved to: {config_path}")

    except Exception as e:
        logger.warning(f"Failed to save processed configuration: {e}")
        # Don't fail the entire process if config saving fails
