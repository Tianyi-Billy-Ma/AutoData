"""Checkpoint management CLI for AutoData."""

from __future__ import annotations

import argparse
import json
import logging
import time
from typing import Any

from autodata.core.autodata import AutoData
from autodata.core.checkpoint import CheckpointManager
from autodata.core.config import AutoDataConfig

logger = logging.getLogger("AutoData")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage AutoData checkpoints.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config-path",
        default="configs/default.yaml",
        help="Path to configuration file.",
    )
    parser.add_argument(
        "--run-name",
        default=None,
        help="Optional run name override.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available checkpoints.")
    list_parser.add_argument(
        "--json",
        action="store_true",
        help="Output manifest details as JSON.",
    )

    save_parser = subparsers.add_parser("save", help="Create a new checkpoint.")
    save_parser.add_argument("--name", help="Checkpoint name/filename.")
    save_parser.add_argument(
        "--stage",
        default="manual",
        help="Pipeline stage associated with the checkpoint.",
    )
    save_parser.add_argument(
        "--metadata",
        action="append",
        dest="metadata",
        help="Additional metadata key=value pairs.",
    )

    load_parser = subparsers.add_parser("load", help="Inspect a checkpoint payload.")
    load_parser.add_argument(
        "checkpoint",
        help="Checkpoint filename to inspect (relative to checkpoint directory unless absolute).",
    )
    load_parser.add_argument(
        "--json",
        action="store_true",
        help="Print payload summary as JSON.",
    )

    clean_parser = subparsers.add_parser(
        "clean", help="Remove checkpoints using retention settings."
    )
    clean_parser.add_argument(
        "--max-keep",
        type=int,
        help="Maximum number of checkpoints to retain after cleanup.",
    )
    clean_parser.add_argument(
        "--older-than-days",
        type=float,
        help="Remove checkpoints older than the specified number of days.",
    )
    clean_parser.add_argument(
        "--json",
        action="store_true",
        help="Output details of removed checkpoints as JSON.",
    )

    return parser


def parse_metadata(pairs: list[str] | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if not pairs:
        return metadata
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Metadata entry must be key=value, got: {pair}")
        key, value = pair.split("=", 1)
        metadata[key] = value
    return metadata


def load_config(config_path: str, run_name: str | None) -> AutoDataConfig:
    config = AutoDataConfig.from_file(config_path)
    if run_name:
        config.run_name = run_name
    return config


def cmd_list(manager: CheckpointManager, as_json: bool) -> None:
    manifest = manager.read_manifest()
    if as_json:
        print(json.dumps(manifest.to_dict(), indent=2))
        return

    if not manifest.checkpoints:
        print("No checkpoints found.")
        return

    print(f"Checkpoints for run: {manifest.run_name}")
    for entry in manifest.checkpoints:
        print(
            f"- {entry.filename} | stage={entry.pipeline_stage} | created_at={entry.created_at:.0f} | size≈{entry.file_size_mb}MB"
        )


def cmd_save(
    manager: CheckpointManager, config: AutoDataConfig, args: argparse.Namespace
) -> None:
    autodata = AutoData(config=config)
    autodata.build()
    metadata = parse_metadata(getattr(args, "metadata", None))
    active_manager = autodata.checkpoint_manager or CheckpointManager(config)
    path = active_manager.save(
        autodata,
        name=args.name,
        pipeline_stage=args.stage,
        metadata=metadata,
    )
    print(f"Checkpoint saved: {path}")


def cmd_load(manager: CheckpointManager, checkpoint: str, as_json: bool) -> None:
    payload = manager.load(checkpoint)
    summary = {
        "filename": payload.header.filename,
        "pipeline_stage": payload.header.pipeline_stage,
        "created_at": payload.header.created_at,
        "run_name": payload.header.run_name,
        "version": payload.header.version,
        "autodata_version": payload.header.autodata_version,
        "metadata": payload.metadata,
        "artifact_count": len(payload.artifacts),
        "message_count": len(payload.messages),
    }
    if as_json:
        print(json.dumps(summary, indent=2))
    else:
        for key, value in summary.items():
            print(f"{key}: {value}")


def cmd_clean(manager: CheckpointManager, args: argparse.Namespace) -> None:
    older_than = None
    if args.older_than_days is not None:
        older_than = time.time() - (args.older_than_days * 86400)

    removed = manager.cleanup(max_keep=args.max_keep, older_than=older_than)

    if args.json:
        print(json.dumps([entry.to_dict() for entry in removed], indent=2))
        return

    if not removed:
        print("No checkpoints removed.")
        return

    print("Removed checkpoints:")
    for entry in removed:
        print(
            f"- {entry.filename} | stage={entry.pipeline_stage} | created_at={entry.created_at:.0f}"
        )


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_config(args.config_path, args.run_name)
    manager = CheckpointManager(config)

    if args.command == "list":
        cmd_list(manager, args.json)
    elif args.command == "save":
        cmd_save(manager, config, args)
    elif args.command == "load":
        cmd_load(manager, args.checkpoint, args.json)
    elif args.command == "clean":
        cmd_clean(manager, args)
    else:  # pragma: no cover - argparse enforces command
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
