"""Sports analytics plugin for AutoData."""

from __future__ import annotations

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from autodata.plugins import PluginSpec


class SportsAnalyticsInput(BaseModel):
    league: str = Field(..., description="League or competition (e.g., NBA, EPL, NFL)")
    metric: str = Field(..., description="Statistic or outcome to analyze")


class SportsAnalyticsTool(BaseTool):
    name: str = "sports_analytics_research_tool"
    description: str = "Identify official statistics feeds, public datasets, and advanced metrics for sports analytics pipelines."
    args_schema: type[BaseModel] = SportsAnalyticsInput

    def _run(self, league: str, metric: str) -> str:
        return (
            f"Document trusted data providers for league '{league}' covering metric '{metric}'. Include API endpoints, "
            "historical depth, rate limits, and licensing terms. Highlight advanced analytics libraries or models commonly used."
        )

    async def _arun(self, league: str, metric: str) -> str:
        return self._run(league, metric)


PLUGIN = PluginSpec(
    name="sport",
    prompts={
        "PlanAgent": (
            "When sports analytics is requested, ensure plans capture season scope, historical depth, and competitive context (regular season vs playoffs)."
        ),
        "ToolAgent": (
            "Use `sports_analytics_research_tool` to locate official statistics feeds, play-by-play datasets, or tracking data. Include notes on latency and update cadence."
        ),
        "EngineerAgent": (
            "Normalize team and player identifiers across seasons, handle schedule gaps, and provide utilities for advanced metrics (PER, xG, EPA)."
        ),
        "ValidationAgent": (
            "Confirm outputs align with league calendars and validate sample calculations for spotlight metrics (e.g., win probability deltas)."
        ),
    },
    tool_classes=(SportsAnalyticsTool,),
    metadata={
        "version": "1.0.0",
        "tool_info": {
            "sports_analytics_research_tool": "Maps reliable sports statistics providers, advanced metrics references, and event-tracking resources."
        },
    },
)


__all__ = ["PLUGIN"]
