"""Financial analysis plugin for AutoData."""

from __future__ import annotations

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from autodata.plugins import PluginSpec


class FinancialResearchInput(BaseModel):
    symbol: str = Field(
        ..., description="Ticker symbol, index, or financial entity to research"
    )
    focus: str | None = Field(
        default=None,
        description="Optional focus area such as fundamentals, sentiment, or macroeconomic indicators",
    )


class FinancialResearchTool(BaseTool):
    name: str = "financial_market_research_tool"
    description: str = "Compile financial datasets, regulatory filings, and market commentary for quantitative workflows."
    args_schema: type[BaseModel] = FinancialResearchInput

    def _run(self, symbol: str, focus: str | None = None) -> str:
        topic = f" for focus '{focus}'" if focus else ""
        return (
            f"Gather authoritative financial information for symbol '{symbol}'{topic}, including pricing datasets, "
            "fundamental filings (10-K/10-Q), macro indicators, and reliable API sources. Summarize licensing constraints and refresh cadence."
        )

    async def _arun(self, symbol: str, focus: str | None = None) -> str:
        return self._run(symbol, focus)


PLUGIN = PluginSpec(
    name="financial",
    prompts={
        "PlanAgent": (
            "For financial analytics tasks, ensure plans capture data sourcing from regulated providers, note currency/market hours, "
            "and address compliance requirements (e.g., SEC, ESMA)."
        ),
        "ToolAgent": (
            "Leverage `financial_market_research_tool` to identify APIs (Tiingo, AlphaVantage, FRED), historical coverage, and licensing. Provide blueprint-ready notes."
        ),
        "EngineerAgent": (
            "Handle rate limits, market calendar edge cases, and currency normalization when coding financial pipelines. Persist raw data with metadata for audit trails."
        ),
        "ValidationAgent": (
            "Verify outputs honor trading calendars, contain timestamped provenance, and respect any usage caps disclosed during research."
        ),
    },
    tool_classes=(FinancialResearchTool,),
    metadata={
        "version": "1.0.0",
        "tool_info": {
            "financial_market_research_tool": "Aggregates compliant financial data sources, regulatory filings, and macroeconomic references."
        },
    },
)


__all__ = ["PLUGIN"]
