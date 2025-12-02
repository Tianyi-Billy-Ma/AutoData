"""Engineer agent module for AutoData multi-agent system.

This module provides the Engineer agent that writes complete, executable Python
scripts based on blueprints and requirements.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from easydict import EasyDict
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from autodata.agents.base_agent import BaseAgent
from autodata.core.ohcache.formatter import (
    EngineerAgentOutput,
    EngineerAgentResponse,
)
from autodata.prompts import ENGINEER_AGENT_INSTRUCTION

logger = logging.getLogger("AutoData.agents")


class EngineerAgent(BaseAgent):
    """Engineer agent that generates complete, executable Python scripts.

    This agent is responsible for writing production-ready, standalone Python
    scripts with explicit dependency lists. The generated code is designed to
    be executed by the ValidationAgent in a Docker container environment.

    The agent outputs:
    - Complete Python scripts with main execution blocks
    - List of pip-installable dependencies
    - Test cases and documentation
    """

    description: str = "writes complete, executable Python scripts with dependencies"
    agent_name: str = "EngineerAgent"
    instruction: str = Field(default=ENGINEER_AGENT_INSTRUCTION)
    formatter: type[BaseModel] | PydanticOutputParser = Field(
        default=EngineerAgentResponse
    )

    def on_forward_end(self, context: EasyDict) -> EasyDict:
        """Persist engineer output to disk, cache, and trim returned payload."""

        if context.get("exception") is None:
            response = context.get("result")
            if isinstance(response, EngineerAgentResponse):
                try:
                    context.result = self._prepare_engineer_output(response)
                except Exception:  # noqa: BLE001 - ensure downstream flow continues
                    logger.exception("Failed to persist engineer response")
        return super().on_forward_end(context)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prepare_engineer_output(
        self, response: EngineerAgentResponse
    ) -> EngineerAgentOutput:
        work_dir = Path(self.config.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        title = self._normalize_title(response.title)
        script_path = self._resolve_unique_path(work_dir, title)
        script_path.write_text(response.code)

        docker_path = f"/workspace/{script_path.name}"

        cache_key = self._cache_script_artifact(
            response=response,
            title=script_path.stem,
            script_path=script_path,
            docker_path=docker_path,
        )

        message = (
            f"Script saved to {script_path} (Docker: {docker_path}). "
            f"Cached artifact key: {cache_key}."
        )

        output = EngineerAgentOutput(
            message=message,
            description=response.description,
            dependencies=response.dependencies,
            error_message=response.error_message,
        )

        # Surface cache key in harness metadata without exposing in message payload.
        try:
            object.__setattr__(output, "ohcache_artifacts", [cache_key])
        except Exception:
            logger.debug("Unable to annotate engineer output with cache metadata")

        return output

    def _normalize_title(self, title: str | None) -> str:
        base = (title or "engineer_script").strip().lower()
        base = re.sub(r"[^a-z0-9_]+", "_", base)
        base = re.sub(r"_+", "_", base).strip("_") or "engineer_script"
        return base[:48]

    def _resolve_unique_path(self, work_dir: Path, base_title: str) -> Path:
        candidate = work_dir / f"{base_title}.py"
        counter = 2
        while candidate.exists():
            candidate = work_dir / f"{base_title}_{counter}.py"
            counter += 1
        return candidate

    def _cache_script_artifact(
        self,
        *,
        response: EngineerAgentResponse,
        title: str,
        script_path: Path,
        docker_path: str,
    ) -> str:
        code_digest = hashlib.md5(response.code.encode("utf-8")).hexdigest()[:8]
        cache_key = f"engineer_code::{title}::{code_digest}"

        summary = response.summary or response.description
        summary = summary.strip()
        if summary:
            summary = self._shorten_summary(summary)

        artifact: dict[str, Any] = {
            "title": title,
            "description": response.description,
            "summary": summary,
            "dependencies": response.dependencies,
            "path": str(script_path),
            "docker_path": docker_path,
            "code": response.code,
        }

        self.cache_artifact(
            key=cache_key,
            value=artifact,
            cache_type="engineer_code",
            summary=summary or f"Code artifact '{title}'",
            tags={title},
        )
        return cache_key

    @staticmethod
    def _shorten_summary(summary: str, *, limit: int = 200) -> str:
        if len(summary) <= limit:
            return summary
        return summary[: limit - 1].rstrip() + "…"
