"""Mixin supplying think-and-fetch planning helpers."""

from __future__ import annotations

import json
import logging
from typing import Any, TYPE_CHECKING

from easydict import EasyDict
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableBinding
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from autodata.core.mixins.base_mixin import BaseAgentMixin
from autodata.core.ohcache.formatter import ThinkResponse
from autodata.prompts.think_prompt import THINK_PROMPT
from autodata.utils.type_utils import normalize_messages

logger = logging.getLogger("AutoData.core")

if TYPE_CHECKING:
    from autodata.agents.types import AgentState


class ThinkAgentMixin(BaseAgentMixin):
    """Mixin supplying think-and-fetch planning helpers."""

    think_instruction: str = Field(init=False, default=THINK_PROMPT)
    think_formatter: BaseModel | PydanticOutputParser = Field(
        init=False, default=ThinkResponse
    )
    think_format_instruction: str = Field(init=False, default="")
    think_parser: PydanticOutputParser | None = Field(init=False, default=None)
    think_prompt: ChatPromptTemplate | None = Field(init=False, default=None)
    think_chain: Runnable | None = Field(init=False, default=None)
    enable_think_stage: bool = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[misc]
        self._initialise_think_components()

    def _initialise_think_components(self) -> None:
        """Initialise parser and prompt for the think stage."""

        formatter = self.think_formatter
        if isinstance(formatter, FieldInfo):
            formatter = formatter.default
        if isinstance(formatter, PydanticOutputParser):
            parser = formatter
        else:
            parser = PydanticOutputParser(pydantic_object=formatter)
        self.think_parser = parser
        self.think_format_instruction = parser.get_format_instructions()
        self.think_prompt = self._create_think_prompt_template()
        self.think_chain = None

    def _create_think_prompt_template(self) -> ChatPromptTemplate:
        """Create the reusable prompt template for think stage."""

        return self._build_think_prompt()

    def _build_think_prompt(self) -> ChatPromptTemplate:
        """Construct the prompt template used for think-and-fetch."""

        return ChatPromptTemplate(
            [
                (
                    "system",
                    "{system_instruction}\n\n{format_instructions}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ],
            partial_variables={
                "system_instruction": self.think_instruction,
                "format_instructions": self.think_parser.get_format_instructions(),
            },
            input_types={
                "messages": list[BaseMessage],
                "artifact_summary": str,
            },
        )

    def _get_think_chain(self, model: BaseChatModel | RunnableBinding) -> Runnable:
        """Return a runnable for the think stage using the provided model."""

        prompt = self.think_prompt

        if model != getattr(self, "model", None):
            return prompt | model | self.think_parser

        if self.think_chain is None:
            self.think_chain = prompt | model | self.think_parser

        return self.think_chain

    def _format_cache_notices(self, notices: list[dict[str, Any]]) -> str:
        """Render cache notices into a user-friendly bullet list."""

        if not notices:
            return "(none)"

        lines: list[str] = []
        for idx, notice in enumerate(notices, start=1):
            key = notice.get("cache_key") or "<unknown>"
            cache_type = notice.get("cache_type") or "general"
            summary = notice.get("summary") or "(no summary provided)"
            source = notice.get("from_agent") or "unknown"
            lines.append(
                f"{idx}. key='{key}' (type={cache_type}, from={source})\n   summary: {summary}"
            )
        return "\n".join(lines)

    def _format_artifact_content(self, artifact: Any) -> str:
        """Convert fetched artifact content into a trimmed text block."""

        if isinstance(artifact, (dict, list)):
            try:
                text = json.dumps(artifact, indent=2, ensure_ascii=False)
            except TypeError:
                text = str(artifact)
        else:
            text = str(artifact)

        return text

    def _artifact_message_from_fetch(
        self,
        *,
        key: str,
        content: Any,
        cache_type: str | None,
        summary: str | None,
    ) -> HumanMessage:
        """Create a context message describing a fetched artifact."""

        lines = [f"[CACHE FETCH] key={key}"]
        if cache_type:
            lines.append(f"cache_type: {cache_type}")
        if summary:
            lines.append(f"summary: {summary}")
        lines.append("")
        lines.append("content:")
        lines.append(self._format_artifact_content(content))
        message_text = "\n".join(lines)
        return HumanMessage(content=message_text, name=self.agent_name)

    def _collect_cache_notices_for_think(self) -> list[dict[str, Any]]:
        """Gather cache notices if OHCache helpers are available."""

        pull_notices = getattr(self, "pull_cache_notices", None)
        notices: list[Any] = []

        if callable(pull_notices):
            notices = list(pull_notices(clear_buffers=True))
        else:
            receive_fn = getattr(self, "receive_cache_notices", None)
            if callable(receive_fn):
                notices = list(receive_fn(clear_buffers=True))

        if not notices:
            return []

        normalised_notices: list[dict[str, Any]] = []
        for notice in notices:
            if isinstance(notice, dict):
                payload = dict(notice)
            elif hasattr(notice, "model_dump"):
                try:
                    payload = notice.model_dump()
                except Exception:  # pragma: no cover - defensive
                    payload = {}
            else:
                payload = {}

            payload.setdefault("owner", getattr(notice, "owner", "unknown"))
            payload.setdefault(
                "cache_key",
                getattr(notice, "cache_key", "")
                or getattr(notice, "name", "")
                or payload.get("owner", ""),
            )
            payload.setdefault("cache_type", getattr(notice, "cache_type", ""))
            payload.setdefault(
                "summary",
                getattr(notice, "summary", None)
                or getattr(notice, "content", None)
                or str(notice),
            )
            normalised_notices.append(payload)

        return normalised_notices

    def _fetch_artifact_for_think(self, key: str, sentinel: object) -> Any:
        """Fetch artifact if OHCache helpers are available."""

        fetcher = getattr(self, "fetch_artifact", None)
        if not callable(fetcher):
            return sentinel

        return fetcher(key, default=sentinel)

    def _run_think_and_fetch(
        self,
        model: BaseChatModel | Runnable,
        state: "AgentState",
    ) -> "AgentState":
        """Execute the think stage and optionally fetch cache artifacts."""

        notices = self._collect_cache_notices_for_think()
        think_chain = self._get_think_chain(model)
        cache_notice_text = self._format_cache_notices(notices)
        context_messages = list(state.get("messages", []))
        normalized_context = normalize_messages(context_messages, sender=None)

        plan: ThinkResponse
        try:
            plan = think_chain.invoke(
                {
                    "messages": normalized_context,
                    "artifact_summary": cache_notice_text,
                }
            )
        except Exception:
            logger.exception("Think-and-fetch stage failed for %s", self.agent_name)
            plan = ThinkResponse(cache_keys=[], rationale="")

        unique_keys: list[str] = []
        for key in plan.cache_keys or []:
            if not isinstance(key, str):
                continue
            trimmed = key.strip()
            if not trimmed or trimmed in unique_keys:
                continue
            unique_keys.append(trimmed)

        sentinel = object()
        fetched_artifacts: list[dict[str, Any]] = []
        for key in unique_keys:
            artifact = self._fetch_artifact_for_think(key, sentinel)
            if artifact is sentinel:
                continue
            notice = next((n for n in notices if n.get("cache_key") == key), None)
            fetched_artifacts.append(
                {
                    "key": key,
                    "content": artifact,
                    "cache_type": notice.get("cache_type") if notice else None,
                    "summary": notice.get("summary") if notice else None,
                }
            )

        if not fetched_artifacts and not plan.rationale.strip():
            return state

        enriched_state: "AgentState" = dict(state)
        messages = list(enriched_state.get("messages", []))

        if notices:
            messages.append(
                HumanMessage(
                    content=f"[CACHE NOTICES]\n{cache_notice_text}",
                    name=self.agent_name,
                )
            )

        if plan.rationale.strip():
            messages.append(
                HumanMessage(
                    content=f"[CACHE THINK] {plan.rationale.strip()}",
                    name=self.agent_name,
                )
            )

        for artifact in fetched_artifacts:
            messages.append(self._artifact_message_from_fetch(**artifact))

        enriched_state["messages"] = normalize_messages(messages, sender=None)
        return enriched_state

    def on_forward_start(self, context: EasyDict) -> EasyDict:
        context = super().on_forward_start(context)
        model = context.get("model")
        state = context.get("state")
        if model is None or state is None:
            return context
        if not getattr(self, "enable_think_stage", True):
            return context
        context.state = self._run_think_and_fetch(model, state)
        return context


__all__ = ["ThinkAgentMixin"]
