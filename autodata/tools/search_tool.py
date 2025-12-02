from typing import Any

from easydict import EasyDict
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

try:  # pragma: no cover - optional dependency
    from langchain_perplexity import ChatPerplexity  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    # We failback to our own implementation if langchain-perplexity is not installed.
    from autodata.extras.perplexity import ChatPerplexity  # type: ignore


from autodata.core.ohcache.formatter import ToolCallResponse


class PerplexitySearchToolInput(BaseModel):
    query: str = Field(description="The query to search for.")


class PerpleixtySearchTool(BaseTool):
    config: EasyDict | dict = EasyDict()
    model: str = "llama-3.1-sonar-small-128k-online"

    def __init__(
        self,
        name: str = "PerplexitySearchTool",
        description: str = "A tool that allows you to search the web using Perplexity.",
        args_schema: type[BaseModel] = PerplexitySearchToolInput,
        config: EasyDict | dict = EasyDict(),
    ) -> None:
        final_config = config or EasyDict()
        # Try to get model from nested tools.PerplexitySearchToolModel first
        model_name = "llama-3.1-sonar-small-128k-online"
        if isinstance(final_config, dict):
            # Try nested access for tools.PerplexitySearchToolModel
            if (
                "tools" in final_config
                and "PerplexitySearchToolModel" in final_config["tools"]
            ):
                model_name = final_config["tools"]["PerplexitySearchToolModel"]
            # Fallback to direct access
            elif "PerplexitySearchToolModel" in final_config:
                model_name = final_config["PerplexitySearchToolModel"]
        elif hasattr(final_config, "tools") and hasattr(
            final_config.tools, "PerplexitySearchToolModel"
        ):
            model_name = final_config.tools.PerplexitySearchToolModel

        super().__init__(
            name=name,
            description=description,
            args_schema=args_schema,
            metadata={"config": final_config},
            config=final_config,
            model=model_name,
        )

    def forward(self, query: str) -> dict:
        """Execute the search and return results as a dict with message field."""
        if ChatPerplexity is None:
            raise RuntimeError(
                "langchain-perplexity is not installed. Install it to enable the "
                "PerplexitySearchTool."
            )
        perplexity = ChatPerplexity(
            model=self.model,
            temperature=0.0,
            timeout=30,
        )
        result = perplexity.invoke(query)
        return ToolCallResponse(
            tool_name=self.name,
            message=result.content,
            additional=result.additional_kwargs,
            error_message=None,
        )

    async def arun(self, *args: Any, **kwargs: Any) -> dict:
        return self.forward(*args, **kwargs)

    def _run(self, *args: Any, **kwargs: Any) -> dict:
        return self.forward(*args, **kwargs)
