"""Routing log mixin for agent execution hooks."""

from __future__ import annotations

from easydict import EasyDict

from autodata.core.mixins.base_mixin import BaseAgentMixin
from autodata.utils.routing_utils import log_routing_decision


class LogMixin(BaseAgentMixin):
    """Mixin that records routing decisions after forward execution."""

    def on_forward_end(self, context: EasyDict) -> EasyDict:
        context = super().on_forward_end(context)
        response = context.get("response")
        if response:
            log_routing_decision(self, response)
        return context

    async def on_forward_end_async(self, context: EasyDict) -> EasyDict:
        context = await super().on_forward_end_async(context)
        response = context.get("response")
        if response:
            log_routing_decision(self, response)
        return context


__all__ = ["LogMixin"]
