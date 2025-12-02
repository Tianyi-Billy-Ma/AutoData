"""Report unused imports, functions, and classes inside autodata."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Sequence

from vulture.core import Vulture

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATHS = [str(REPO_ROOT / "autodata")]


@dataclass(slots=True)
class Finding:
    """Normalized representation of an unused or ignored symbol."""

    name: str
    kind: str
    path: Path
    lineno: int
    confidence: int
    reason: str

    def as_dict(self) -> dict[str, object]:
        """Convert the finding into a JSON-friendly payload."""

        return {
            "name": self.name,
            "type": self.kind,
            "path": str(self.path),
            "lineno": self.lineno,
            "confidence": self.confidence,
            "reason": self.reason,
        }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the cleanup script."""

    parser = argparse.ArgumentParser(
        description=(
            "Scan Python modules for unused imports, classes, and functions."
            " The script never modifies files; remove code manually and rerun"
            " until it exits successfully."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=DEFAULT_PATHS,
        help="Paths to scan (default: autodata directory).",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Filter out results whose path/name matches the provided pattern (can repeat).",
    )
    parser.add_argument(
        "--ignore-names",
        action="append",
        default=[],
        help="fnmatch-style patterns for names that should be ignored (e.g., register_*).",
    )
    parser.add_argument(
        "--min-confidence",
        type=int,
        default=90,
        help="Minimum confidence (0-100) reported by Vulture before flagging (default: 90).",
    )
    parser.add_argument(
        "--include",
        dest="includes",
        action="append",
        default=[],
        help="Only report items whose name/path matches this pattern (can repeat).",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Emit JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--check",
        dest="check",
        action="store_true",
        help="Exit with a non-zero status if unused entries remain (default).",
    )
    parser.add_argument(
        "--no-check",
        dest="check",
        action="store_false",
        help="Only print the report, even when unused entries are found.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose Vulture logging.",
    )
    parser.add_argument(
        "--exclude-path",
        dest="exclude_paths",
        action="append",
        default=[],
        help="Directory/file glob to skip while scanning (optional; can repeat).",
    )
    parser.set_defaults(check=True)
    return parser.parse_args(argv)


def build_vulture(min_confidence: int, verbose: bool) -> Vulture:
    """Create and configure the Vulture analyzer."""

    vulture = Vulture(verbose=verbose)
    vulture.min_confidence = min_confidence
    return vulture


def _relative_path(path: str | Path) -> Path:
    """Return a repo-relative (or absolute fallback) path for display."""

    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT)
    except ValueError:
        return resolved


def _matches_token(value: str, token: str) -> bool:
    """Case-insensitive substring/glob matcher."""

    value_lower = value.lower()
    token_lower = token.lower()
    if any(ch in token for ch in "*?[]"):
        return fnmatch(value_lower, token_lower)
    return token_lower in value_lower


def _matches_any(finding: Finding, patterns: Iterable[str]) -> bool:
    """Check whether any token matches the finding path, name, or type."""

    haystacks = (finding.name, finding.kind, str(finding.path))
    for pattern in patterns:
        for haystack in haystacks:
            if _matches_token(haystack, pattern):
                return True
    return False


def _match_ignore(name: str, patterns: Iterable[str]) -> str | None:
    """Return the ignore pattern that matches the provided name, if any."""

    for pattern in patterns:
        if _matches_token(name, pattern):
            return pattern
    return None


def collect_findings(
    paths: Sequence[str],
    *,
    include_patterns: Sequence[str],
    exclude_patterns: Sequence[str],
    ignore_name_patterns: Sequence[str],
    exclude_paths: Sequence[str],
    min_confidence: int,
    verbose: bool,
) -> tuple[list[Finding], list[Finding]]:
    """Run Vulture and bucket unused + ignored findings."""

    vulture = build_vulture(min_confidence=min_confidence, verbose=verbose)
    vulture.scavenge(paths, exclude=list(exclude_paths) or list(exclude_patterns))
    items = sorted(
        vulture.get_unused_code(),
        key=lambda item: (
            getattr(item, "filename", ""),
            getattr(item, "lineno", 0),
            getattr(item, "name", ""),
        ),
    )

    unused: list[Finding] = []
    ignored: list[Finding] = []

    for raw in items:
        finding = Finding(
            name=getattr(raw, "name", ""),
            kind=getattr(raw, "typ", ""),
            path=_relative_path(getattr(raw, "filename", "")),
            lineno=getattr(raw, "lineno", 0),
            confidence=getattr(raw, "confidence", 0),
            reason="unused",
        )

        ignore_match = _match_ignore(finding.name, ignore_name_patterns)
        if ignore_match:
            finding.reason = f"ignored-by-pattern:{ignore_match}"
            ignored.append(finding)
            continue

        if include_patterns and not _matches_any(finding, include_patterns):
            continue

        if exclude_patterns and _matches_any(finding, exclude_patterns):
            continue

        unused.append(finding)

    return unused, ignored


def print_human_report(unused: Sequence[Finding], ignored: Sequence[Finding]) -> None:
    """Print findings in a compact, readable format."""

    if not unused:
        print("✅ No unused code detected.")
    else:
        width = max(len(str(item.path)) for item in unused)
        print("Found unused definitions/imports:\n")
        for item in unused:
            print(
                f"{str(item.path):<{width}}  L{item.lineno:>4}  "
                f"{item.kind:<10}  {item.name} (conf={item.confidence})"
            )

    if ignored:
        width = max(len(str(item.path)) for item in ignored)
        print("\nIgnored entries (--ignore-names matches):\n")
        for item in ignored:
            print(
                f"{str(item.path):<{width}}  L{item.lineno:>4}  "
                f"{item.kind:<10}  {item.name} [{item.reason}]"
            )


def print_json_report(unused: Sequence[Finding], ignored: Sequence[Finding]) -> None:
    """Emit JSON payload with unused + ignored sections."""

    payload = {
        "unused": [item.as_dict() for item in unused],
        "ignored": [item.as_dict() for item in ignored],
        "summary": {"unused": len(unused), "ignored": len(ignored)},
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    args = parse_args(argv)
    unused, ignored = collect_findings(
        args.paths,
        include_patterns=args.includes,
        exclude_patterns=args.exclude,
        ignore_name_patterns=args.ignore_names,
        exclude_paths=args.exclude_paths,
        min_confidence=args.min_confidence,
        verbose=args.verbose,
    )

    if args.json_output:
        print_json_report(unused, ignored)
    else:
        print_human_report(unused, ignored)

    if args.check and unused:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
