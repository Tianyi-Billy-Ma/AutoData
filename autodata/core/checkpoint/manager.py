"""Checkpoint manager for saving and restoring AutoData pipeline state."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path

from autodata import __version__ as AUTODATA_VERSION
from autodata.core.config import (
    AutoDataConfig,
    BrowserUseAgentConfig,
    BrowserUseBrowserConfig,
    CheckpointConfig,
    LLMConfig,
    LogConfig,
    OHCacheConfig,
    PluginConfig,
    StorageConfig,
    TaskConfig,
    ToolConfig,
)
from autodata.core.exceptions import (
    AutoDataError,
    CheckpointIntegrityError,
    CheckpointValidationError,
)
from autodata.core.ohcache.cache import CacheEntry, LocalCacheSystem
from autodata.core.ohcache.hypergraph import OrientedMessageHypergraph
from autodata.utils.type_utils import convert_paths, ensure_serializable

from .models import (
    CheckpointEntry,
    CheckpointManifest,
    CheckpointMetadata,
    CheckpointPayload,
)
from .serialization import (
    dump_checkpoint_json,
    dump_checkpoint_payload,
    load_checkpoint_payload,
    read_checkpoint_manifest,
    write_checkpoint_manifest,
)

SCHEMA_VERSION = "1.0.0"

logger = logging.getLogger("AutoData.core")


class CheckpointManager:
    """Coordinates checkpoint lifecycle including save, load, and manifest management."""

    def __init__(
        self,
        config: AutoDataConfig,
        *,
        checkpoint_dir: Path | None = None,
    ) -> None:
        self.config = config
        self._checkpoint_dir = Path(checkpoint_dir or config.checkpoint_dir)
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def checkpoint_dir(self) -> Path:
        return self._checkpoint_dir

    @property
    def manifest_path(self) -> Path:
        return self.checkpoint_dir / "manifest.json"

    def read_manifest(self) -> CheckpointManifest:
        if self.manifest_path.exists():
            return read_checkpoint_manifest(self.manifest_path)
        return CheckpointManifest(
            run_name=self.config.run_name or "default_run",
            checkpoint_dir=self.checkpoint_dir,
        )

    def list_checkpoints(self) -> Sequence[CheckpointEntry]:
        return self.read_manifest().checkpoints

    def cleanup(
        self,
        *,
        max_keep: int | None = None,
        older_than: float | None = None,
    ) -> list[CheckpointEntry]:
        """Remove checkpoints based on retention rules."""

        manifest = self.read_manifest()
        removed: list[CheckpointEntry] = []

        if older_than is not None:
            removed.extend(manifest.remove_older_than(older_than))

        keep_limit = (
            max_keep
            if max_keep is not None
            else self.config.checkpoint_config.max_checkpoints
        )
        removed.extend(manifest.prune(keep_limit))

        unique_removed: dict[str, CheckpointEntry] = {}
        for entry in removed:
            unique_removed.setdefault(entry.filename, entry)

        removed_entries = list(unique_removed.values())
        for entry in removed_entries:
            file_path = self.checkpoint_dir / entry.filename
            for candidate in (file_path, file_path.with_suffix(".json")):
                if candidate.exists():
                    candidate.unlink()
            self._cleanup_checkpoint_folder(file_path.parent)

        if removed_entries:
            write_checkpoint_manifest(self.manifest_path, manifest)
            logger.info("[CHECKPOINT] Cleaned up %d checkpoints", len(removed_entries))

        return removed_entries

    def save(  # noqa: PLR0913 - arguments intentional for CLI ergonomics
        self,
        autodata: object,
        *,
        name: str | None = None,
        pipeline_stage: str | None = None,
        metadata: Mapping[str, object] | None = None,
        export_json: bool | None = None,
    ) -> Path:
        """Persist a checkpoint for the provided AutoData instance."""

        if not self.config.checkpoint_enabled:
            raise CheckpointValidationError(
                "Checkpointing is disabled in the configuration.",
                details={"run_name": self.config.run_name},
            )

        timestamp = time.time()
        timestamp_slug = datetime.fromtimestamp(timestamp, tz=UTC).strftime(
            "%Y%m%dT%H%M%S"
        )
        checkpoint_root = self.checkpoint_dir / timestamp_slug
        checkpoint_root.mkdir(parents=True, exist_ok=True)

        stem = name or "checkpoint"
        filename = stem if stem.endswith(".pkl") else f"{stem}.pkl"
        checkpoint_path = checkpoint_root / filename
        relative_filename = str(checkpoint_path.relative_to(self.checkpoint_dir))

        checkpoint_metadata = CheckpointMetadata(
            version=SCHEMA_VERSION,
            autodata_version=AUTODATA_VERSION,
            created_at=timestamp,
            run_name=self.config.run_name or "default_run",
            pipeline_stage=pipeline_stage or "unknown",
            filename=relative_filename,
            metadata=dict(metadata or {}),
        )

        payload = CheckpointPayload(
            header=checkpoint_metadata,
            config_dict=self._snapshot_config(autodata),
            artifacts=self._snapshot_artifacts(autodata),
            messages=self._snapshot_messages(autodata),
            metadata=checkpoint_metadata.metadata,
        )

        logger.info("[CHECKPOINT] Writing checkpoint to %s", checkpoint_path)
        dump_checkpoint_payload(checkpoint_path, payload)

        export_json_flag = (
            export_json if export_json is not None else bool(cp_config.export_json)
        )
        if export_json_flag:
            dump_checkpoint_json(
                checkpoint_path.with_suffix(".json"),
                payload,
            )

        self._update_manifest(
            checkpoint_path=checkpoint_path,
            checkpoint_metadata=checkpoint_metadata,
        )

        logger.info("[CHECKPOINT] Checkpoint saved: %s", checkpoint_metadata.filename)
        return checkpoint_path

    def load(self, checkpoint_path: str | Path) -> CheckpointPayload:
        """Load checkpoint payload from disk."""

        resolved = self._resolve_checkpoint_path(checkpoint_path)
        logger.info("[CHECKPOINT] Loading checkpoint from %s", resolved)
        return load_checkpoint_payload(resolved)

    def restore(self, autodata: object, payload: CheckpointPayload) -> None:
        """Apply checkpoint payload onto an AutoData instance."""

        logger.info(
            "[CHECKPOINT] Restoring checkpoint stage=%s", payload.header.pipeline_stage
        )
        self._restore_config(autodata, payload.config_dict)
        self._restore_artifacts(autodata, payload.artifacts)
        self._restore_messages(autodata, payload.messages)
        logger.info("[CHECKPOINT] Restore complete")

    def resume(self, autodata: Any, checkpoint_name: str | Path) -> CheckpointPayload:
        """Load and immediately restore a checkpoint."""

        payload = self.load(checkpoint_name)
        self.restore(autodata, payload)
        return payload

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------

    def _snapshot_config(self, autodata: object) -> dict[str, object]:
        config = getattr(autodata, "config", None)
        if config is None:
            raise CheckpointValidationError("AutoData instance missing config.")
        if hasattr(config, "model_dump"):
            data = config.model_dump()
            return convert_paths(data)
        if is_dataclass(config):
            return convert_paths(asdict(config))
        if isinstance(config, dict):
            return convert_paths(dict(config))
        raise CheckpointValidationError(
            "Unsupported config type.", details={"type": type(config).__name__}
        )

    def _snapshot_artifacts(self, autodata: object) -> dict[str, object]:
        """Snapshot OHCache artifacts without mutating runtime state."""

        graph = getattr(autodata, "graph", None)
        ohcache = getattr(graph, "ohcache", None)
        if ohcache is None or not getattr(ohcache, "enable_ohcache", False):
            return {}

        cache_system: LocalCacheSystem = ohcache.cache_system
        cache_snapshot: dict[str, object] = {}

        for hashed_key, entry in cache_system._cache.items():  # noqa: SLF001
            cache_snapshot[hashed_key] = {
                "key": entry.key,
                "value": ensure_serializable(entry.value),
                "cache_type": entry.cache_type,
                "metadata": ensure_serializable(entry.metadata),
                "tags": list(entry.tags),
                "created_at": entry.created_at,
                "last_accessed": entry.last_accessed,
                "access_count": entry.access_count,
                "ttl": entry.ttl,
            }

        return {
            "cache": cache_snapshot,
            "stats": dict(cache_system._stats),  # noqa: SLF001
            "type_index": {k: list(v) for k, v in cache_system._type_index.items()},  # noqa: SLF001
            "tag_index": {k: list(v) for k, v in cache_system._tag_index.items()},  # noqa: SLF001
            "cache_dir": str(cache_system._cache_dir)
            if cache_system._cache_dir
            else None,  # noqa: SLF001
            "auto_cleanup": cache_system._auto_cleanup,  # noqa: SLF001
        }

    def _snapshot_messages(self, autodata: object) -> dict[str, object]:
        """Snapshot hypergraph structure and message history."""

        graph = getattr(autodata, "graph", None)
        ohcache = getattr(graph, "ohcache", None)
        if ohcache is None or not getattr(ohcache, "enable_ohcache", False):
            return {}

        hypergraph: OrientedMessageHypergraph = ohcache.hypergraph
        edges = []
        for edge_id, edge in hypergraph.hyperedges.items():
            edges.append(
                {
                    "edge_id": edge_id,
                    "source_agents": list(edge.source_agents),
                    "target_agents": list(edge.target_agents),
                    "message_type": edge.message_type,
                    "metadata": ensure_serializable(edge.metadata),
                    "created_at": edge.created_at,
                    "delivered_targets": list(edge.delivered_targets),
                }
            )

        return {
            "nodes": list(hypergraph.nodes),
            "edges": edges,
            "agent_to_hyperedges": {
                agent: list(edge_ids)
                for agent, edge_ids in hypergraph.agent_to_hyperedges.items()
            },
            "message_history": [dict(record) for record in hypergraph.message_history],
        }

    # ------------------------------------------------------------------
    # Restore helpers
    # ------------------------------------------------------------------

    def _restore_config(self, autodata: Any, config_dict: Mapping[str, Any]) -> None:
        if not hasattr(autodata, "config"):
            raise CheckpointIntegrityError(
                "AutoData instance missing config attribute."
            )
        autodata.config = AutoDataConfig(
            task_config=TaskConfig(**config_dict.get("task_config", {})),
            storage_config=StorageConfig(**config_dict.get("storage_config", {})),
            log_config=LogConfig(**config_dict.get("log_config", {})),
            llm_config=LLMConfig(**config_dict.get("llm_config", {})),
            tool_config=ToolConfig(**config_dict.get("tool_config", {})),
            ohcache_config=OHCacheConfig(**config_dict.get("ohcache_config", {})),
            checkpoint_config=CheckpointConfig(**config_dict.get("checkpoint_config", {})),
            plugin_config=PluginConfig(**config_dict.get("plugin_config", {})),
            browser_use_browser_config=BrowserUseBrowserConfig(
                **config_dict.get("browser_use_browser_config", {})
            ),
            browser_use_agent_config=BrowserUseAgentConfig(
                **config_dict.get("browser_use_agent_config", {})
            ),
        )
        legacy_plugins = config_dict.get("enabled_plugins")
        if legacy_plugins:
            autodata.config.plugin_config.enabled_plugins = list(legacy_plugins)

    def _restore_artifacts(self, autodata: Any, artifacts: Mapping[str, Any]) -> None:
        """Restore OHCache artifacts captured in a checkpoint payload."""

        if not artifacts:
            return

        graph = getattr(autodata, "graph", None)
        ohcache = getattr(graph, "ohcache", None)
        if ohcache is None or not hasattr(ohcache, "cache_system"):
            raise CheckpointIntegrityError("AutoData graph missing ohcache for restore")

        cache_system: LocalCacheSystem = ohcache.cache_system
        cache_system._cache.clear()  # noqa: SLF001
        cache_system._type_index.clear()  # noqa: SLF001
        cache_system._tag_index.clear()  # noqa: SLF001

        for hashed_key, entry_state in artifacts.get("cache", {}).items():
            entry = CacheEntry(
                key=entry_state.get("key", hashed_key),
                value=entry_state.get("value"),
                cache_type=entry_state.get("cache_type", "general"),
                metadata=entry_state.get("metadata") or {},
                ttl=entry_state.get("ttl"),
                tags=set(entry_state.get("tags", [])),
            )
            entry.created_at = entry_state.get("created_at", entry.created_at)
            entry.last_accessed = entry_state.get("last_accessed", entry.created_at)
            entry.access_count = entry_state.get("access_count", 0)
            cache_system._cache[hashed_key] = entry  # noqa: SLF001
            cache_system._type_index.setdefault(entry.cache_type, set()).add(  # noqa: SLF001
                hashed_key
            )
            for tag in entry.tags:
                cache_system._tag_index.setdefault(tag, set()).add(hashed_key)  # noqa: SLF001

        cache_system._stats = dict(artifacts.get("stats", {}))  # noqa: SLF001
        auto_cleanup = artifacts.get("auto_cleanup")
        if auto_cleanup is not None:
            cache_system._auto_cleanup = auto_cleanup  # noqa: SLF001
        cache_dir = artifacts.get("cache_dir")
        if cache_dir:
            cache_system._cache_dir = Path(cache_dir)  # noqa: SLF001

        logger.info(
            "[CHECKPOINT] Restored %d cached artifacts",
            len(artifacts.get("cache", {})),
        )

    def _restore_messages(self, autodata: Any, messages: Mapping[str, Any]) -> None:
        """Restore hypergraph structure from checkpoint payload."""

        if not messages:
            return

        graph = getattr(autodata, "graph", None)
        ohcache = getattr(graph, "ohcache", None)
        if ohcache is None:
            raise CheckpointIntegrityError("AutoData graph missing ohcache for restore")

        hypergraph = OrientedMessageHypergraph()
        for node in messages.get("nodes", []):
            hypergraph.add_node(node)

        for edge_state in messages.get("edges", []):
            edge_id = edge_state.get("edge_id")
            if not edge_id:
                continue
            source_agents = set(edge_state.get("source_agents", []))
            target_agents = set(edge_state.get("target_agents", []))
            hypergraph.add_nodes(list(source_agents | target_agents))
            hypergraph.add_hyperedge(
                edge_id=edge_id,
                source_agents=source_agents,
                target_agents=target_agents,
                message_type=edge_state.get("message_type", "default"),
                metadata=edge_state.get("metadata"),
            )
            edge = hypergraph.hyperedges[edge_id]
            edge.created_at = edge_state.get("created_at", edge.created_at)
            edge.delivered_targets = set(edge_state.get("delivered_targets", []))

        hypergraph.agent_to_hyperedges = {
            agent: set(edge_ids)
            for agent, edge_ids in messages.get("agent_to_hyperedges", {}).items()
        }
        hypergraph.message_history = [
            dict(record) for record in messages.get("message_history", [])
        ]

        ohcache.hypergraph = hypergraph
        logger.info(
            "[CHECKPOINT] Restored hypergraph with %d edges",
            len(messages.get("edges", [])),
        )

    # ------------------------------------------------------------------
    # Manifest helpers
    # ------------------------------------------------------------------

    def _update_manifest(
        self,
        *,
        checkpoint_path: Path,
        checkpoint_metadata: CheckpointMetadata,
    ) -> CheckpointManifest:
        if self.manifest_path.exists():
            manifest = read_checkpoint_manifest(self.manifest_path)
        else:
            manifest = CheckpointManifest(
                run_name=checkpoint_metadata.run_name,
                checkpoint_dir=self.checkpoint_dir,
            )

        file_size = checkpoint_path.stat().st_size if checkpoint_path.exists() else 0
        manifest.add_entry(
            CheckpointEntry.from_metadata(
                checkpoint_metadata,
                file_size_bytes=file_size,
            )
        )

        removed_entries = manifest.prune(self.config.checkpoint_config.max_checkpoints)
        for removed in removed_entries:
            remove_path = self.checkpoint_dir / removed.filename
            if remove_path.exists():
                remove_path.unlink()
            json_path = remove_path.with_suffix(".json")
            if json_path.exists():
                json_path.unlink()
            self._cleanup_checkpoint_folder(remove_path.parent)

        write_checkpoint_manifest(self.manifest_path, manifest)
        logger.debug(
            "[CHECKPOINT] Manifest updated (%d entries)", len(manifest.checkpoints)
        )
        return manifest

    def _resolve_checkpoint_path(self, checkpoint_path: str | Path) -> Path:
        candidate = Path(checkpoint_path)
        if candidate.is_absolute():
            return candidate
        potential = self.checkpoint_dir / candidate
        if potential.exists():
            return potential
        for subdir in self.checkpoint_dir.iterdir():
            if not subdir.is_dir():
                continue
            nested = subdir / candidate
            if nested.exists():
                return nested
        raise AutoDataError(
            f"Checkpoint file not found: {candidate}",
            code="checkpoint_not_found",
            details={"path": str(candidate)},
        )

    def _cleanup_checkpoint_folder(self, folder: Path) -> None:
        try:
            if folder != self.checkpoint_dir:
                folder.rmdir()
        except OSError:
            pass


__all__ = ["CheckpointManager", "SCHEMA_VERSION"]
