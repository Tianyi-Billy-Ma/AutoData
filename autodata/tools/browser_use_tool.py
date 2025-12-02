"""
Browser-use tools for the BrowserAgent.

This module provides Pydantic models for browser-use integration.
The cache_artifact tool enables caching of browsing artifacts (HTML snippets,
documentation pages) for downstream agents to access via the shared OHCache system.
"""

from pydantic import BaseModel, Field


class CacheArtifactInput(BaseModel):
    """Input model for cache_artifact tool with LLM guidance."""

    cache_key: str = Field(
        description=(
            "Unique descriptive cache key in the format: {source}_{page_type}_{content_type}. "
            "Must be specific to avoid collisions across different browsing sessions. "
            "Include the source/website name, page type, and content type. "
            "Use underscores to separate words, lowercase only. "
            "DO NOT include the actual URL in the cache key."
        )
    )
    content: str = Field(
        description=(
            "The HTML or text content to cache. "
            "This should be the actual page content, HTML snippets, or documentation in markdown format or plain text "
            "that downstream agents need to analyze for data collection planning."
        )
    )
    cache_type: str = Field(
        default="browser_html",
        description=(
            "Type of cached content (metadata for filtering). "
            "Options: 'browser_html' (default), 'documentation', 'general'. "
            "This helps agents filter cached artifacts by type."
        ),
    )


class FetchCacheInput(BaseModel):
    """Input model for fetch_cache tool."""

    cache_key: str = Field(
        description=(
            "The exact cache key used when storing the artifact. "
            "Must match the key from cache_artifact exactly. "
            "Use the same format: {source}_{page_type}_{content_type}."
        )
    )
