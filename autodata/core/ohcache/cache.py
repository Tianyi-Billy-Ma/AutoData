"""
Local Cache System for OHCache.

This module provides the LocalCacheSystem class for storing and retrieving
reusable artifacts in the AutoData multi-agent system. The cache system
enables agents to store and retrieve data, code, configurations, and other
artifacts for efficient collaboration and reduced redundant work.
"""

# TODO: Extend artifact serializers to support binary payloads (images, PDFs).

import builtins
import hashlib
import json
import logging
import pickle
import re
import time
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from easydict import EasyDict

from autodata.utils.type_utils import ensure_serializable

logger = logging.getLogger("AutoData.core")


class CacheEntry:
    """Represents a single cache entry with metadata and expiration."""

    def __init__(
        self,
        key: str,
        value: Any,
        cache_type: str = "general",
        metadata: dict[str, Any] | None = None,
        ttl: int | None = None,
        tags: set[str] | None = None,
        *,
        created_at: float | None = None,
        last_accessed: float | None = None,
        access_count: int | None = None,
    ) -> None:
        """Initialize a cache entry."""

        self.key = key
        self.value = value
        self.cache_type = cache_type
        self.metadata = metadata or {}
        self.tags = tags or set()
        now = time.time()
        self.created_at = created_at or now
        self.last_accessed = last_accessed or self.created_at
        self.access_count = access_count if access_count is not None else 0
        self.ttl = ttl

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""

        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def access(self) -> Any:
        """Access the cache entry and update access statistics."""

        self.last_accessed = time.time()
        self.access_count += 1
        return self.value

    def to_dict(self) -> dict[str, Any]:
        """Convert the cache entry to a dictionary representation."""

        return {
            "key": self.key,
            "cache_type": self.cache_type,
            "metadata": self.metadata,
            "tags": list(self.tags),
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "ttl": self.ttl,
            "is_expired": self.is_expired(),
        }


@dataclass(frozen=True)
class _Serializer:
    """Serializer descriptor used by the LocalCacheSystem."""

    name: str
    extension: str
    predicate: Callable[[Any, str, dict[str, Any] | None], bool]
    dump: Callable[[Any, Path], None]
    load: Callable[[Path], Any]


def _dump_json(value: Any, path: Path) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(ensure_serializable(value), fh, indent=2, ensure_ascii=False)


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _dump_text(value: Any, path: Path) -> None:
    text = value if isinstance(value, str) else str(value)
    path.write_text(text, encoding="utf-8")


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extension_hint(metadata: dict[str, Any] | None) -> str | None:
    if not metadata:
        return None
    for key in ("extension", "serializer", "serializer_hint"):
        hint = metadata.get(key)
        if isinstance(hint, str) and hint.strip():
            return hint.lower().lstrip(".")
    return None


def _prefers_html(value: Any, cache_type: str, metadata: dict[str, Any] | None) -> bool:
    if not isinstance(value, str):
        return False
    ext_hint = _extension_hint(metadata)
    if ext_hint == "html":
        return True
    if cache_type and "html" in cache_type.lower():
        return True
    return "<html" in value.lower()


def _prefers_python(value: Any, cache_type: str, metadata: dict[str, Any] | None) -> bool:
    if not isinstance(value, str):
        return False
    ext_hint = _extension_hint(metadata)
    if ext_hint == "py":
        return True
    language = None
    if metadata:
        language = metadata.get("language")
    if isinstance(language, str) and language.lower() == "python":
        return True
    if cache_type and "python" in cache_type.lower():
        return True
    return False


def _prefers_json(value: Any, cache_type: str, metadata: dict[str, Any] | None) -> bool:
    if isinstance(value, dict | list):
        return True
    ext_hint = _extension_hint(metadata)
    if ext_hint == "json":
        return True
    if cache_type and "json" in cache_type.lower():
        return True
    return False


def _prefers_text(value: Any, _cache_type: str, _metadata: dict[str, Any] | None) -> bool:
    return isinstance(value, str)


def _always_true(_value: Any, _cache_type: str, _metadata: dict[str, Any] | None) -> bool:
    return True


_SERIALIZERS: tuple[_Serializer, ...] = (
    _Serializer("html", "html", _prefers_html, _dump_text, _load_text),
    _Serializer("python", "py", _prefers_python, _dump_text, _load_text),
    _Serializer("json", "json", _prefers_json, _dump_json, _load_json),
    _Serializer("text", "txt", _prefers_text, _dump_text, _load_text),
    _Serializer("json_fallback", "json", _always_true, _dump_json, _load_json),
)


class LocalCacheSystem:
    """Local cache system for storing reusable artifacts in multi-agent collaboration."""

    _SERIALIZERS: tuple[_Serializer, ...] = _SERIALIZERS
    _SERIALIZERS_BY_NAME: dict[str, _Serializer] = {
        serializer.name.lower(): serializer for serializer in _SERIALIZERS
    }
    _SERIALIZERS_BY_EXTENSION: dict[str, _Serializer] = {}
    for serializer in _SERIALIZERS:
        _SERIALIZERS_BY_EXTENSION.setdefault(
            serializer.extension.lower(), serializer
        )

    INLINE_PAYLOAD_KEY = "payload"

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        max_memory_entries: int = 1000,
        auto_cleanup: bool = True,
    ) -> None:
        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._artifact_dir: Path | None = None
        self._meta_dir: Path | None = None
        self._max_memory_entries = max_memory_entries
        self._auto_cleanup = auto_cleanup

        self._cache: dict[str, CacheEntry] = {}
        self._type_index: dict[str, set[str]] = {}
        self._tag_index: dict[str, set[str]] = {}
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "cleanups": 0}

        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._artifact_dir = self._cache_dir / "artifacts"
            self._meta_dir = self._cache_dir / "meta"
            self._artifact_dir.mkdir(parents=True, exist_ok=True)
            self._meta_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

        logger.info("Initialized LocalCacheSystem with %d entries", len(self._cache))

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------

    def _generate_key(self, key: str, cache_type: str = "general") -> str:
        _ = cache_type  # cache_type is metadata only; hash uses key for stability
        return hashlib.md5(key.encode()).hexdigest()

    def _slugify_key(self, key: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", key).strip("-")
        return slug.lower() or "artifact"

    def _artifact_filename(self, original_key: str, serializer: _Serializer) -> str:
        slug = self._slugify_key(original_key)
        digest = hashlib.md5(original_key.encode()).hexdigest()[:8]
        return f"{slug}-{digest}.{serializer.extension}"

    def _update_indexes(
        self, entry: CacheEntry, old_entry: CacheEntry | None = None
    ) -> None:
        if old_entry:
            bucket = self._type_index.get(old_entry.cache_type)
            if bucket:
                bucket.discard(entry.key)
                if not bucket:
                    self._type_index.pop(old_entry.cache_type, None)
            for tag in old_entry.tags:
                tag_bucket = self._tag_index.get(tag)
                if tag_bucket:
                    tag_bucket.discard(entry.key)
                    if not tag_bucket:
                        self._tag_index.pop(tag, None)

        self._type_index.setdefault(entry.cache_type, set()).add(entry.key)
        for tag in entry.tags:
            self._tag_index.setdefault(tag, set()).add(entry.key)

    def _cleanup_expired(self) -> None:
        expired_keys = [key for key, entry in self._cache.items() if entry.is_expired()]
        if not expired_keys:
            return

        for key in expired_keys:
            self._remove_entry(key)

        self._stats["cleanups"] += 1
        logger.debug("Cleaned up %d expired entries", len(expired_keys))

    def _remove_entry(self, key: str, *, remove_files: bool = True) -> CacheEntry | None:
        entry = self._cache.pop(key, None)
        if entry is None:
            return None

        bucket = self._type_index.get(entry.cache_type)
        if bucket:
            bucket.discard(key)
            if not bucket:
                self._type_index.pop(entry.cache_type, None)

        for tag in list(entry.tags):
            tag_bucket = self._tag_index.get(tag)
            if tag_bucket:
                tag_bucket.discard(key)
                if not tag_bucket:
                    self._tag_index.pop(tag, None)

        if remove_files:
            self._remove_artifact_files(entry)

        return entry

    def _enforce_memory_limit(self) -> None:
        if len(self._cache) <= self._max_memory_entries:
            return

        surplus = len(self._cache) - self._max_memory_entries
        sorted_entries = sorted(self._cache.items(), key=lambda item: item[1].last_accessed)
        for i in range(surplus):
            key, _ = sorted_entries[i]
            self._remove_entry(key)

        logger.debug("Removed %d entries to enforce memory limit", surplus)

    def _select_serializer(
        self,
        value: Any,
        cache_type: str,
        metadata: dict[str, Any] | None,
    ) -> _Serializer:
        metadata = metadata or {}

        serializer_hint = metadata.get("serializer") or metadata.get("serializer_hint")
        if isinstance(serializer_hint, str):
            serializer = self._SERIALIZERS_BY_NAME.get(serializer_hint.lower())
            if serializer:
                return serializer

        extension_hint = metadata.get("extension")
        if isinstance(extension_hint, str):
            serializer = self._SERIALIZERS_BY_EXTENSION.get(extension_hint.lower().lstrip("."))
            if serializer:
                return serializer

        for serializer in self._SERIALIZERS:
            try:
                if serializer.predicate(value, cache_type, metadata):
                    return serializer
            except Exception:  # pragma: no cover - defensive predicate safety
                logger.debug(
                    "Serializer predicate '%s' raised unexpectedly", serializer.name,
                    exc_info=True,
                )
                continue

        return self._SERIALIZERS[-1]

    def _store_payload(
        self,
        *,
        original_key: str,
        value: Any,
        serializer: _Serializer,
    ) -> tuple[dict[str, Any], str | None, int | None, _Serializer]:
        if not self._artifact_dir:
            descriptor = {
                "filename": None,
                "file_path": None,
                "serializer": serializer.name,
                "extension": serializer.extension,
                "original_key": original_key,
                "size": None,
                "stored_inline": True,
                self.INLINE_PAYLOAD_KEY: ensure_serializable(value),
            }
            return descriptor, None, None, serializer

        data_filename = self._artifact_filename(original_key, serializer)
        data_path = (self._artifact_dir / data_filename).resolve()
        data_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = data_path.with_suffix(data_path.suffix + ".tmp")

        effective_serializer = serializer
        try:
            serializer.dump(value, temp_path)
        except Exception as exc:  # pragma: no cover - serializer failure fallback
            logger.debug(
                "Primary serializer '%s' failed for key '%s': %s",
                serializer.name,
                original_key,
                exc,
            )
            fallback = self._SERIALIZERS_BY_NAME.get("text")
            if not fallback:
                raise
            fallback.dump(value, temp_path)
            effective_serializer = fallback

        temp_path.replace(data_path)
        size = data_path.stat().st_size

        descriptor = {
            "filename": data_filename,
            "file_path": str(data_path),
            "serializer": effective_serializer.name,
            "extension": effective_serializer.extension,
            "original_key": original_key,
            "size": size,
            "stored_inline": False,
        }
        return descriptor, data_filename, size, effective_serializer

    def _write_metadata_file(
        self,
        *,
        cache_key: str,
        original_key: str,
        entry: CacheEntry,
        serializer: _Serializer,
        data_filename: str | None,
        size: int | None,
    ) -> None:
        if not self._meta_dir or not data_filename:
            return

        metadata_path = self._meta_dir / f"{data_filename}.meta.json"
        payload = {
            "cache_key": cache_key,
            "original_key": original_key,
            "cache_type": entry.cache_type,
            "serializer": serializer.name,
            "extension": serializer.extension,
            "filename": data_filename,
            "size": size,
            "metadata": ensure_serializable(entry.metadata),
            "tags": sorted(entry.tags),
            "ttl": entry.ttl,
            "created_at": entry.created_at,
            "last_accessed": entry.last_accessed,
            "access_count": entry.access_count,
        }

        temp_path = metadata_path.with_suffix(metadata_path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        temp_path.replace(metadata_path)

    def _remove_artifact_files(self, entry: CacheEntry) -> None:
        if not self._artifact_dir and not self._meta_dir and not self._cache_dir:
            return

        descriptor = entry.value if isinstance(entry.value, dict) else {}
        filename = descriptor.get("filename")
        if not filename:
            return

        paths: set[Path] = set()
        if self._artifact_dir:
            paths.add(self._artifact_dir / filename)
        if self._cache_dir:
            paths.add(self._cache_dir / filename)
            paths.add(self._cache_dir / f"{filename}.meta.json")
        if self._meta_dir:
            paths.add(self._meta_dir / f"{filename}.meta.json")
        for path in paths:
            with suppress(FileNotFoundError):
                path.unlink()

    def _resolve_artifact_value(self, entry: CacheEntry, default: Any) -> Any:
        descriptor = entry.value if isinstance(entry.value, dict) else None
        if not descriptor:
            return entry.value

        if descriptor.get("stored_inline"):
            return descriptor.get(self.INLINE_PAYLOAD_KEY, default)

        artifact_root = self._artifact_dir or self._cache_dir
        if not artifact_root:
            return descriptor.get(self.INLINE_PAYLOAD_KEY, default)

        filename = descriptor.get("filename")
        if not filename:
            return default

        data_path = artifact_root / filename
        if not data_path.exists() and self._cache_dir:
            legacy_path = self._cache_dir / filename
            if legacy_path.exists():
                data_path = legacy_path
        if not data_path.exists():
            logger.warning("Cache artifact missing on disk: %s", data_path)
            return default

        serializer_name = (descriptor.get("serializer") or "").lower()
        serializer = self._SERIALIZERS_BY_NAME.get(serializer_name)
        if serializer is None:
            extension = (descriptor.get("extension") or "").lower()
            serializer = self._SERIALIZERS_BY_EXTENSION.get(extension, self._SERIALIZERS[-1])

        try:
            return serializer.load(data_path)
        except Exception as exc:  # pragma: no cover - I/O failure
            logger.error(
                "Failed to load cache artifact '%s' via serializer '%s': %s",
                filename,
                serializer.name,
                exc,
            )
            return default

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set(
        self,
        key: str,
        value: Any,
        cache_type: str = "general",
        metadata: dict[str, Any] | None = None,
        ttl: int | None = None,
        tags: set[str] | None = None,
    ) -> None:
        cache_key = self._generate_key(key, cache_type)
        self._persist_entry(
            cache_key=cache_key,
            original_key=key,
            value=value,
            cache_type=cache_type,
            metadata=metadata,
            ttl=ttl,
            tags=tags,
        )

    def _persist_entry(
        self,
        *,
        cache_key: str,
        original_key: str,
        value: Any,
        cache_type: str,
        metadata: dict[str, Any] | None,
        ttl: int | None,
        tags: Iterable[str] | None,
        created_at: float | None = None,
        last_accessed: float | None = None,
        access_count: int | None = None,
        overwrite: bool = True,
    ) -> None:
        serializer = self._select_serializer(value, cache_type, metadata)
        descriptor, data_filename, size, effective_serializer = self._store_payload(
            original_key=original_key,
            value=value,
            serializer=serializer,
        )

        entry = CacheEntry(
            key=cache_key,
            value=descriptor,
            cache_type=cache_type,
            metadata=metadata,
            ttl=ttl,
            tags=set(tags or set()),
            created_at=created_at,
            last_accessed=last_accessed,
            access_count=access_count,
        )

        old_entry = self._cache.get(cache_key)
        if old_entry and not overwrite:
            return

        self._cache[cache_key] = entry
        self._update_indexes(entry, old_entry if overwrite else None)
        self._write_metadata_file(
            cache_key=cache_key,
            original_key=original_key,
            entry=entry,
            serializer=effective_serializer,
            data_filename=data_filename,
            size=size,
        )

        if old_entry and overwrite:
            self._remove_artifact_files(old_entry)

        self._stats["sets"] += 1
        self._enforce_memory_limit()
        if self._auto_cleanup:
            self._cleanup_expired()

        logger.debug("Cached entry: %s (type: %s)", cache_key, cache_type)

    def get(self, key: str, cache_type: str = "general", default: Any = None) -> Any:
        cache_key = self._generate_key(key, cache_type)
        entry = self._cache.get(cache_key)
        if entry is None:
            self._stats["misses"] += 1
            return default

        if entry.is_expired():
            self._remove_entry(cache_key)
            self._stats["misses"] += 1
            return default

        entry.access()
        self._stats["hits"] += 1
        return self._resolve_artifact_value(entry, default)

    def get_entry(self, key: str, cache_type: str = "general") -> CacheEntry | None:
        cache_key = self._generate_key(key, cache_type)
        entry = self._cache.get(cache_key)
        if entry is None:
            return None
        if entry.is_expired():
            self._remove_entry(cache_key)
            return None
        return entry

    def delete(self, key: str, cache_type: str = "general") -> bool:
        cache_key = self._generate_key(key, cache_type)
        entry = self._remove_entry(cache_key)
        if entry is None:
            return False
        self._stats["deletes"] += 1
        logger.debug("Deleted cache entry: %s", cache_key)
        return True

    def get_by_type(self, cache_type: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        keys = list(self._type_index.get(cache_type, set()))
        for key in keys:
            entry = self._cache.get(key)
            if entry is None:
                continue
            if entry.is_expired():
                self._remove_entry(key)
                continue
            entry.access()
            result[key] = self._resolve_artifact_value(entry, None)
        return result

    def get_entries_by_type(self, cache_type: str) -> list[CacheEntry]:
        entries: list[CacheEntry] = []
        keys = list(self._type_index.get(cache_type, set()))
        for key in keys:
            entry = self._cache.get(key)
            if entry is None:
                continue
            if entry.is_expired():
                self._remove_entry(key)
                continue
            entry.access()
            entries.append(entry)
        return entries

    def get_by_tags(
        self,
        tags: builtins.set[str],
        match_all: bool = True,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        tags = set(tags)
        if not tags:
            return result

        if match_all:
            iter_tags = list(tags)
            matching = self._tag_index.get(iter_tags[0], set()).copy()
            for tag in iter_tags[1:]:
                matching &= self._tag_index.get(tag, set())
        else:
            matching = set()
            for tag in tags:
                matching |= self._tag_index.get(tag, set())

        for key in matching:
            entry = self._cache.get(key)
            if entry is None:
                continue
            if entry.is_expired():
                self._remove_entry(key)
                continue
            entry.access()
            result[key] = self._resolve_artifact_value(entry, None)

        return result

    def clear(self, cache_type: str | None = None) -> int:
        if cache_type is None:
            keys = list(self._cache.keys())
        else:
            keys = list(self._type_index.get(cache_type, set()))

        count = 0
        for key in keys:
            if self._remove_entry(key):
                count += 1

        if count:
            self._stats["deletes"] += count

        logger.info("Cleared %d cache entries", count)
        return count

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _current_disk_usage(self) -> dict[str, int]:
        artifact_root = self._artifact_dir or self._cache_dir
        if not artifact_root:
            return {"file_count": 0, "total_bytes": 0}

        file_count = 0
        total_bytes = 0
        seen: set[str] = set()
        for entry in self._cache.values():
            descriptor = entry.value if isinstance(entry.value, dict) else {}
            filename = descriptor.get("filename")
            if not filename or filename in seen:
                continue
            seen.add(filename)
            data_path = artifact_root / filename
            if not data_path.exists() and self._cache_dir:
                legacy_path = self._cache_dir / filename
                if legacy_path.exists():
                    data_path = legacy_path
            if data_path.exists():
                file_count += 1
                total_bytes += data_path.stat().st_size

        return {"file_count": file_count, "total_bytes": total_bytes}

    def _load_from_disk(self) -> None:
        assert self._cache_dir is not None
        self._cache.clear()
        self._type_index.clear()
        self._tag_index.clear()
        self._stats.update({"hits": 0, "misses": 0, "sets": 0, "deletes": 0})

        self._migrate_legacy_cache_layout()

        meta_files: list[Path] = []
        if self._meta_dir and self._meta_dir.exists():
            meta_files.extend(sorted(self._meta_dir.glob("*.meta.json")))
        if self._cache_dir:
            meta_files.extend(
                sorted(
                    path
                    for path in self._cache_dir.glob("*.meta.json")
                    if not self._meta_dir or path.parent != self._meta_dir
                )
            )
        for meta_path in meta_files:
            try:
                with meta_path.open(encoding="utf-8") as fh:
                    payload = json.load(fh)
            except Exception as exc:
                logger.error("Failed to load cache metadata %s: %s", meta_path, exc)
                continue

            cache_key = payload.get("cache_key")
            filename = payload.get("filename")
            if not cache_key or not filename:
                logger.warning("Skipping malformed cache metadata file: %s", meta_path)
                continue

            descriptor = {
                "filename": filename,
                "file_path": str(
                    ((self._artifact_dir or self._cache_dir) / filename).resolve()
                ),
                "serializer": payload.get("serializer"),
                "extension": payload.get("extension"),
                "original_key": payload.get("original_key", cache_key),
                "size": payload.get("size"),
                "stored_inline": False,
            }

            entry = CacheEntry(
                key=cache_key,
                value=descriptor,
                cache_type=payload.get("cache_type", "general"),
                metadata=payload.get("metadata") or {},
                ttl=payload.get("ttl"),
                tags=set(payload.get("tags", [])),
                created_at=payload.get("created_at"),
                last_accessed=payload.get("last_accessed"),
                access_count=payload.get("access_count"),
            )

            self._cache[cache_key] = entry
            self._update_indexes(entry)

        self._stats["sets"] = len(self._cache)
        logger.debug("Loaded %d cache entries from disk", len(self._cache))

    def _migrate_legacy_cache_layout(self) -> None:
        assert self._cache_dir is not None
        cache_file = self._cache_dir / "cache.pkl"
        metadata_file = self._cache_dir / "metadata.json"

        if not cache_file.exists():
            return

        try:
            with cache_file.open("rb") as fh:
                legacy_cache = pickle.load(fh)
        except Exception as exc:
            logger.error("Failed to read legacy cache.pkl: %s", exc)
            return

        for cache_key, entry in legacy_cache.items():
            if not isinstance(entry, CacheEntry):
                logger.debug("Skipping non-CacheEntry during migration: %s", cache_key)
                continue

            original_key = (
                entry.metadata.get("original_key")
                or entry.metadata.get("cache_key_original")
                or cache_key
            )

            serializer = self._select_serializer(entry.value, entry.cache_type, entry.metadata)
            descriptor, data_filename, size, effective_serializer = self._store_payload(
                original_key=str(original_key),
                value=entry.value,
                serializer=serializer,
            )

            reconstructed = CacheEntry(
                key=cache_key,
                value=descriptor,
                cache_type=entry.cache_type,
                metadata=entry.metadata,
                ttl=entry.ttl,
                tags=entry.tags,
                created_at=entry.created_at,
                last_accessed=entry.last_accessed,
                access_count=entry.access_count,
            )

            self._write_metadata_file(
                cache_key=cache_key,
                original_key=str(original_key),
                entry=reconstructed,
                serializer=effective_serializer,
                data_filename=data_filename,
                size=size,
            )

        with suppress(Exception):
            cache_file.unlink()
        with suppress(Exception):
            metadata_file.unlink()

        logger.info("Migrated legacy cache layout to per-artifact files")

    def save(self) -> None:
        if self._cache_dir:
            logger.debug("LocalCacheSystem persistence is immediate; save() is a no-op.")

    def to_easydict(self) -> EasyDict:
        return EasyDict(self.stats)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests else 0

        stats = {
            "total_entries": len(self._cache),
            "cache_types": list(self._type_index.keys()),
            "total_tags": len(self._tag_index),
            "hit_rate": hit_rate,
            "stats": self._stats.copy(),
        }

        stats["disk_usage"] = self._current_disk_usage()
        stats["memory_usage"] = {
            "current_entries": len(self._cache),
            "max_entries": self._max_memory_entries,
            "usage_percentage": (len(self._cache) / self._max_memory_entries) * 100,
        }
        return stats


__all__ = ["CacheEntry", "LocalCacheSystem"]
