"""Academic domain plugin for AutoData."""

from __future__ import annotations

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from autodata.plugins import PluginSpec


class AcademicResearchInput(BaseModel):
    query: str = Field(..., description="Academic topic or query to research")


class AcademicResearchTool(BaseTool):
    name: str = "academic_research_tool"
    description: str = "Research scholarly sources, papers, and datasets relevant to the current workflow."
    args_schema: type[BaseModel] = AcademicResearchInput

    def _run(self, query: str) -> str:
        return (
            "Summarize key academic sources, notable papers, and reputable datasets for "
            f"'{query}'. Provide citation-ready metadata (title, authors, publication year) and note open-access availability."
        )

    async def _arun(self, query: str) -> str:
        return self._run(query)


PLUGIN = PluginSpec(
    name="academic",
    prompts={
        "PlanAgent": (
            "When academic research is requested, ensure steps include literature review tasks, cite peer-reviewed sources, "
            "and flag any prerequisite domain experts or ethics approvals."
        ),
        "ToolAgent": (
            "Use `academic_research_tool` to gather references from scholarly databases (ACM, arXiv, PubMed). Prioritize peer-reviewed "
            "materials and summarize why each source is relevant."
        ),
        "EngineerAgent": (
            "When implementing data collection scripts for academic sources, plan for citation metadata, DOI handling, and output structures "
            "amenable to bibliography generation."
        ),
        "ValidationAgent": (
            "Confirm output files include citation metadata and that collected datasets align with academic licensing constraints."
        ),
    },
    tool_classes=(AcademicResearchTool,),
    metadata={
        "version": "1.0.0",
        "tool_info": {
            "academic_research_tool": "Aggregates scholarly references and dataset links relevant to the current task."
        },
    },
)


__all__ = ["PLUGIN"]
