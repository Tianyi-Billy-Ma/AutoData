"""Base hook mixin for agent execution pipeline."""

from __future__ import annotations

from typing import Any

from easydict import EasyDict


class BaseAgentMixin:
    """Default hook implementations for agent execution."""

    def on_forward_start(self, context: EasyDict) -> EasyDict:
        """Prepare execution context or pass through unchanged."""

        return context

    async def on_forward_start_async(self, context: EasyDict) -> EasyDict:
        """Async variant that defers to the sync implementation."""

        return self.on_forward_start(context)

    def forward_step(self, context: EasyDict) -> EasyDict:
        """Invoke the LLM chain with retry semantics."""

        chain = context.get("chain")
        state = context.get("state")
        if chain is None or state is None:
            raise ValueError("Chain and state must be available before forward_step.")
        context.result = self._invoke_chain_with_retry(chain, state)
        context.exception = None
        return context

    async def forward_step_async(self, context: EasyDict) -> EasyDict:
        """Async forward step with retry semantics."""

        chain = context.get("chain")
        state = context.get("state")
        if chain is None or state is None:
            raise ValueError("Chain and state must be available before forward_step.")
        context.result = await self._invoke_chain_with_retry_async(chain, state)
        context.exception = None
        return context

    def on_forward_end(self, context: EasyDict) -> EasyDict:
        """Finalize the response payload."""

        if context.get("exception") is None:
            if context.get("response") is not None:
                return context
            if "result" in context:
                context.response = self._finalize_forward_response(
                    context.result,
                    next_agent=context.get("next_agent", "Supervisor"),
                    message_type=context.get("message_type", "routing"),
                    target_agents=context.get("target_agents"),
                )
        return context

    async def on_forward_end_async(self, context: EasyDict) -> EasyDict:
        """Async finalization path."""

        return self.on_forward_end(context)


__all__ = ["BaseAgentMixin"]
