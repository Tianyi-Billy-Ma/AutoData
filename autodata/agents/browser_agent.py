"""Browser agent module for AutoData multi-agent system.

This module provides a minimal Browser agent that integrates with the browser-use
package for web browsing and data extraction capabilities.
"""

from __future__ import annotations

import hashlib
import inspect
import logging
import os
import warnings
from typing import Any

from easydict import EasyDict
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from autodata.agents.base_agent import BaseAgent
from autodata.core.config import (
    BrowserUseAgentConfig,
    BrowserUseBrowserConfig,
    BrowserUseConfig,
)
from autodata.core.exceptions import AgentStateError, AutoDataModelError
from autodata.core.mixins.ohcache_mixin import OHCacheAgentMixin
from autodata.core.ohcache.formatter import BrowserAgentResponse
from autodata.extras.browser_use.chat_utils import ChatLangchain
from autodata.prompts import BROWSER_AGENT_INSTRUCTION
from autodata.tools.browser_use_tool import CacheArtifactInput, FetchCacheInput

# Suppress browser-use library warnings
warnings.filterwarnings(
    "ignore", message="invalid escape sequence", category=SyntaxWarning
)

# Disable browser-use telemetry and logging setup
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
# Use AutoData's logging configuration instead of browser-use's default
os.environ.setdefault("BROWSER_USE_SETUP_LOGGING", "false")

logger = logging.getLogger("AutoData.agents")


class BrowserAgent(BaseAgent):
    """Minimal browser agent integrating browser-use for web automation.

    This agent leverages browser-use defaults with minimal configuration,
    focusing on core browsing and data extraction functionality.
    """

    description: str = "Web browsing and data extraction using browser-use"
    agent_name: str = "BrowserAgent"
    instruction: str = Field(default=BROWSER_AGENT_INSTRUCTION)
    formatter: type[BaseModel] | PydanticOutputParser = Field(
        default=BrowserAgentResponse
    )

    def _build_task_cache_key(self, task: str) -> str:
        digest = hashlib.sha256(task.encode("utf-8")).hexdigest()
        return f"browser_response::{digest}"

    checkpoint_auto_sync: bool = False

    def forward_step(self, context: EasyDict) -> EasyDict:
        """Sync hook: execute browser task by delegating to async implementation."""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.forward_step_async(context))

    async def forward_step_async(self, context: EasyDict) -> EasyDict:
        """Async hook: execute the browser task."""

        current_model = context.get("model")
        if current_model is None:
            raise AutoDataModelError("BrowserAgent requires an initialized model")
        if current_model is not self.model:
            self._update_model(current_model)

        contextual_state = context.get("state") or {}
        context.state = contextual_state

        messages = contextual_state.get("messages", [])
        if not messages:
            raise AgentStateError("BrowserAgent requires at least one input message")

        task_content = getattr(messages[-1], "content", "") or ""

        history = "\n".join(
            getattr(message, "content", "") for message in messages[:-1]
        )

        full_task = (
            f"# History:\n{history}\n\n# Your Task:\n{task_content}"
            if history
            else f"# Your Task:\n{task_content}"
        )

        try:
            result = await self._run_browser_task(full_task)
        except Exception:  # noqa: BLE001
            logger.exception("Browser agent execution failed")
            raise

        context.result = result
        return context

    def _prepare_browser_tools(self) -> Any:
        """Prepare browser-use Tools instance with cache actions.

        Returns:
            Tools instance with cache_artifact and fetch_cache actions registered.
        """
        from browser_use import ActionResult, Tools

        # Create tools with write_file excluded
        tools = Tools(exclude_actions=["write_file"])

        # Register custom cache_artifact action
        @tools.action(
            description=(
                "Cache HTML content, documentation pages, or page structure examples discovered during browsing. "
                "Use this to store reusable artifacts like HTML snippets, API documentation pages, or DOM structure "
                "examples that other agents may need when implementing data collection scripts."
            ),
            param_model=CacheArtifactInput,
        )
        def cache_artifact(input_data: CacheArtifactInput):
            """Cache content to local storage for downstream agents to access."""
            try:
                cache_key = input_data.cache_key

                # Check if OHCache system is available
                if not self.enable_ohcache:
                    return ActionResult(
                        error="Cache system not available. OHCache must be enabled to use cache_artifact.",
                    )

                # Use mixin's cache_artifact method from parent
                OHCacheAgentMixin.cache_artifact(
                    self,
                    key=cache_key,
                    value=input_data.content,
                    cache_type=input_data.cache_type,
                    summary=f"Cached {len(input_data.content)} bytes with key: {cache_key}",
                )

                # Explicitly persist to disk
                self.save_cache()

                cache_dir = self.cache_dir or "memory"

                return ActionResult(
                    extracted_content=f"Cached {len(input_data.content)} bytes with key: {cache_key}",
                    long_term_memory=f"Content cached as '{cache_key}' in {cache_dir}. You can access this via the fetch_artifact tool.",
                )
            except Exception as e:
                return ActionResult(error=f"Failed to cache content: {str(e)}")

        # Register custom fetch_artifact action
        @tools.action(
            description=(
                "Retrieve previously cached HTML content, documentation pages, or page structure examples. "
                "Use this to access artifacts that were cached during previous browsing sessions or by other agents. "
                "Useful for referencing previously examined page structures, API documentation, or HTML examples."
            ),
            param_model=FetchCacheInput,
        )
        def fetch_artifact(input_data: FetchCacheInput):
            """Fetch cached content from local storage."""
            try:
                cache_key = input_data.cache_key

                # Check if OHCache system is available
                if not self.enable_ohcache:
                    return ActionResult(
                        error="Cache system not available. OHCache must be enabled to use fetch_artifact.",
                    )

                # Retrieve using mixin's fetch_artifact method from parent
                cached_value = OHCacheAgentMixin.fetch_artifact(self, key=cache_key)

                if cached_value is None:
                    return ActionResult(
                        error=f"No cached content found for key: {cache_key}",
                    )

                # Return the cached content
                content_preview = (
                    str(cached_value)[:200] + "..."
                    if len(str(cached_value)) > 200
                    else str(cached_value)
                )

                return ActionResult(
                    extracted_content=str(cached_value),
                    long_term_memory=f"Retrieved cached content for '{cache_key}'. Preview: {content_preview}",
                    include_extracted_content_only_once=True,
                )
            except Exception as e:
                return ActionResult(error=f"Failed to fetch cached content: {str(e)}")

        return tools

    async def _run_browser_task(self, task: str) -> BrowserAgentResponse:
        """Execute browser task using browser-use Agent."""

        cache_key = self._build_task_cache_key(task)

        try:
            from browser_use import Agent as BrowserUseAgent
            from browser_use import Browser

            browser_settings, agent_settings = self._get_browser_configs()

            browser_kwargs = browser_settings.model_dump(exclude_none=True)

            # Build browser-use Browser with BrowserProfile settings
            browser = Browser(**browser_kwargs)

            # Prepare browser-use tools with cache_artifact action
            tools = self._prepare_browser_tools()

            if self.model is None:
                raise ValueError("BrowserAgent requires an initialized language model")

            browser_use_llm = ChatLangchain(chat=self.model)

            # Create and run browser-use agent
            agent_kwargs = agent_settings.model_dump(exclude_none=True)
            max_steps = agent_kwargs.pop("max_steps", agent_settings.max_steps)
            agent = BrowserUseAgent(
                task=task,
                llm=browser_use_llm,
                browser=browser,
                tools=tools,
                available_file_paths=[self.config.work_dir],
                extend_system_message=self.instruction,
                flash_mode=True,
                **agent_kwargs,
            )

            try:
                # Run the agent
                history = await agent.run(max_steps=max_steps)

                # Get page URL from browser context
                url = ""
                try:
                    # Try to get the current page from browser context
                    if hasattr(agent, "browser_context") and agent.browser_context:
                        page = await agent.browser_context.get_current_page()
                        url = str(page.url) if page else ""
                    elif hasattr(browser, "context") and browser.context:
                        page = await browser.context.get_current_page()
                        url = str(page.url) if page else ""
                except Exception as e:
                    logger.warning(f"Could not get page info: {e}")

                # Get the final result from browser-use history
                final_result = (
                    history.final_result() if hasattr(history, "final_result") else ""
                )

                # Build response - let format instruction guide the LLM to populate fields
                response = BrowserAgentResponse(
                    url=url,
                    summary=str(final_result)
                    if final_result
                    else f"Browsing session completed for {url}",
                    content=str(final_result) if final_result else "",
                    # metadata={
                    #     "task": task,
                    #     "browser_type": "chromium",
                    #     "action_count": len(history.action_names())
                    #     if hasattr(history, "action_names")
                    #     else 0,
                    #     "had_errors": bool(history.errors())
                    #     if hasattr(history, "errors")
                    #     else False,
                    #     "cache_key": cache_key,
                    #     "cache_hit": False,
                    # },
                )

                if self.enable_ohcache:
                    self.cache_artifact(
                        key=cache_key,
                        value=response.to_dict(),
                        cache_type="browser_response",
                        summary=f"BrowserAgent response cached for task hash {cache_key}",
                    )
                    self.save_cache()

                return response

            finally:
                # Always cleanup browser resources
                await self._cleanup_browser(agent, browser)

        except ImportError as e:
            logger.error(f"browser-use package not available: {e}")
            return BrowserAgentResponse(
                url="",
                summary="",
                error_message=f"browser-use not installed: {str(e)}",
            )
        except Exception as e:
            logger.exception("Browser task execution failed")
            return BrowserAgentResponse(
                url="",
                summary="",
                error_message=f"Browser execution failed: {str(e)}",
            )

    def _get_browser_configs(
        self,
    ) -> tuple[BrowserUseBrowserConfig, BrowserUseAgentConfig]:
        """Retrieve browser-use browser and agent configuration models."""

        browser_value = getattr(self.config, "browser_use_browser_config", None)
        agent_value = getattr(self.config, "browser_use_agent_config", None)

        browser_config = self._coerce_browser_use_browser_config(browser_value)
        agent_config = self._coerce_browser_use_agent_config(agent_value)

        return browser_config, agent_config

    @staticmethod
    def _coerce_browser_use_browser_config(value: Any) -> BrowserUseBrowserConfig:
        if isinstance(value, BrowserUseBrowserConfig):
            return value
        if isinstance(value, BrowserUseConfig):
            return value.browser
        if isinstance(value, dict):
            return BrowserUseBrowserConfig(**value)
        return BrowserUseBrowserConfig()

    @staticmethod
    def _coerce_browser_use_agent_config(value: Any) -> BrowserUseAgentConfig:
        if isinstance(value, BrowserUseAgentConfig):
            return value
        if isinstance(value, BrowserUseConfig):
            return value.agent
        if isinstance(value, dict):
            return BrowserUseAgentConfig(**value)
        return BrowserUseAgentConfig()


    @staticmethod
    async def _cleanup_browser(agent: Any, browser: Any = None) -> None:
        """Clean up browser resources.

        Args:
            agent: Browser-use agent instance
            browser: Browser instance (optional, will try to get from agent if not provided)
        """
        try:
            context = getattr(agent, "browser_context", None)
            if context:
                await context.close()
        except Exception as e:
            logger.warning(f"Error closing browser context: {e}")

        session = getattr(agent, "browser_session", None)
        if session is not None:
            await BrowserAgent._shutdown_browser_target(session)

        browser_to_close = browser or getattr(agent, "browser", None)
        if browser_to_close is not None and browser_to_close is not session:
            await BrowserAgent._shutdown_browser_target(browser_to_close)

    @staticmethod
    async def _shutdown_browser_target(target: Any) -> None:
        for method_name in ("kill", "stop", "close"):
            if await BrowserAgent._try_async_method(target, method_name):
                return

    @staticmethod
    async def _try_async_method(target: Any, method_name: str) -> bool:
        method = getattr(target, method_name, None)
        if method is None:
            return False

        try:
            result = method()
            if inspect.isawaitable(result):
                await result
            return True
        except Exception as e:
            logger.warning(f"Error during browser {method_name}: {e}")
            return False
