"""Human agent module for AutoData multi-agent system.

This module provides the HumanAgent that interacts with the user to
review plans, provide approvals, or share feedback during the workflow.
"""

from __future__ import annotations

import sys

from easydict import EasyDict
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from autodata.agents.base_agent import BaseAgent
from autodata.core.ohcache.formatter import HumanAgentResponse
from autodata.prompts import HUMAN_AGENT_INSTRUCTION
from autodata.utils.type_utils import pretty_format_object


class HumanAgent(BaseAgent):
    """Human agent that facilitates direct user interaction.

    This agent prompts the user in the console to review intermediate
    outputs (e.g., plans) and to either approve, request changes, or
    provide general comments. The resulting feedback is broadcast via
    the OHCache hypergraph so other agents can consume it as context.
    """

    description: str = (
        "interacts with the user to review steps and provide feedback/approval"
    )
    agent_name: str = "HumanAgent"
    instruction: str = Field(default=HUMAN_AGENT_INSTRUCTION)
    formatter: type[BaseModel] | PydanticOutputParser = Field(
        default=HumanAgentResponse
    )

    def _render_context_for_user(self) -> str:
        """Render the plan for user review, extracted from PlanAgent context.

        Returns:
            String summary of the plan for display in the console.
        """
        # Pull recent hypergraph messages destined for this agent
        payloads = []
        try:
            payloads = self.receive_messages(clear_buffers=False)
        except Exception:
            # If OHCache is not configured/available, continue silently
            payloads = []

        if not payloads:
            return "(No plan available for review.)"

        # Look for the most recent PlanAgent message
        plan_message = None
        for item in reversed(payloads):  # Check most recent first
            from_agent = str(item.get("from_agent", ""))
            if "plan" in from_agent.lower():
                plan_message = item.get("message")
                break

        if not plan_message:
            return "(No plan found in context.)"

        # Extract plan information
        lines: list[str] = ["📋 Plan for Review:", ""]

        # Handle different message formats
        if hasattr(plan_message, "goals"):
            # It's a PlanAgentResponse object
            if plan_message.goals:
                lines.append("🎯 Goals:")
                for i, goal in enumerate(plan_message.goals, start=1):
                    lines.append(f"  {i}. {goal}")
                lines.append("")

            if hasattr(plan_message, "steps") and plan_message.steps:
                lines.append("📝 Steps:")
                for i, step in enumerate(plan_message.steps, start=1):
                    # StepResponse has agent_name and description attributes
                    agent = getattr(step, "agent_name", "Unknown")
                    action = getattr(step, "description", "")
                    lines.append(f"  {i}. [{agent}] {action}")
                lines.append("")

            if hasattr(plan_message, "notes") and plan_message.notes:
                lines.append(f"💡 Notes: {plan_message.notes}")
                lines.append("")

        elif isinstance(plan_message, str):
            # Plain text plan
            lines.append(plan_message)
            lines.append("")

        elif hasattr(plan_message, "content"):
            # BaseMessage format
            lines.append(str(plan_message.content))
            lines.append("")

        else:
            # Fallback: pretty print the object
            lines.append(pretty_format_object(plan_message))

        return "\n".join(lines)

    def _prompt_user(self) -> tuple[str, str]:
        """Prompt the user for a decision and optional feedback via stdin.

        Returns:
            A tuple of (decision_tag, feedback_text)
        """
        if bool(getattr(self.config, "disable_human", False)):
            sys.stdout.write(
                "HumanAgent validation disabled; auto-approving current step.\n"
            )
            sys.stdout.flush()
            return "[APPROVE]", ""

        out = sys.stdout
        out.write("\nPlease review the above context. Choose an option:\n")
        out.write("  [A]pprove plan/step\n")
        out.write("  [R]equest changes\n")
        out.write("  [C]omment only\n")
        out.flush()

        try:
            decision_raw = input("Your choice (A/R/C): ").strip().lower()
        except EOFError:
            # Non-interactive environment: default to comment
            decision_raw = "c"
        if decision_raw.startswith("a"):
            decision = "[APPROVE]"
        elif decision_raw.startswith("r"):
            decision = "[REVISE]"
        else:
            decision = "[COMMENT]"

        try:
            feedback = input("Optional feedback (press Enter to skip): ").strip()
        except EOFError:
            feedback = ""
        return decision, feedback

    def forward_step(self, context: EasyDict) -> EasyDict:  # type: ignore[override]
        """Interact with the user and broadcast feedback."""

        summary = self._render_context_for_user()
        sys.stdout.write("\n===== Human Review =====\n")
        sys.stdout.write(f"{summary}\n")
        sys.stdout.write("=======================\n\n")
        sys.stdout.flush()

        decision, feedback = self._prompt_user()

        response = HumanAgentResponse(
            decision=decision,
            feedback=feedback,
        )

        send_metadata = self.send_message(
            response,
            message_type="human_feedback",
            target_agents={
                self.agent_name,
                "SupervisorAgent",
            },  # Only the supervisor agent will receive the message.
        )
        message = HumanMessage(content=response.to_message(), name=self.agent_name)
        context.result = response
        hyperedges = list(send_metadata.get("hyperedges", []))
        targets = set(send_metadata.get("target_agents", {self.agent_name})) or {
            self.agent_name
        }
        context.response = EasyDict(
            {
                "messages": [message],
                "sender": self.agent_name,
                "hyperedges": hyperedges,
                "message_type": "human_feedback",
                "target_agents": targets,
            }
        )
        context.exception = None
        return context

    async def forward_step_async(self, context: EasyDict) -> EasyDict:  # type: ignore[override]
        """Async wrapper delegating to the synchronous human interaction."""

        return self.forward_step(context)
