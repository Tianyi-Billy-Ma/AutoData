"""LLM configuration dataclass."""

from dataclasses import dataclass, field


@dataclass
class LLMConfig:
    """LLM configuration for init_chat_model.

    Uses LangChain's init_chat_model for universal model initialization.
    Supports multiple providers (OpenAI, Anthropic, Google, etc.) and
    third-party providers via base_url override.

    Environment variable auto-detection:
    - OPENROUTER_API_KEY: Automatically used if api_key is None
    - OPENROUTER_BASE_URL: Automatically used if base_url is None
    - Other provider keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.) are
      handled by LangChain's init_chat_model
    """

    model: str = field(
        default="gpt-4o",
        metadata={"help": "Model name (e.g., 'gpt-4o', 'claude-3-5-sonnet-latest')"},
    )
    model_provider: str | None = field(
        default=None,
        metadata={
            "help": "Model provider (e.g., 'openai', 'anthropic', 'google_genai'). "
            "If None, will be inferred from model name."
        },
    )
    temperature: float = field(
        default=0.0,
        metadata={"help": "Temperature for sampling"},
    )
    base_url: str | None = field(
        default=None,
        metadata={
            "help": "Optional base URL for OpenAI-compatible APIs. "
            "Use this for third-party providers like OpenRouter. "
            "Auto-detects OPENROUTER_BASE_URL environment variable if None."
        },
    )
    api_key: str | None = field(
        default=None,
        metadata={
            "help": "Optional API key override. If None, uses environment variables "
            "(OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY, etc.)."
        },
    )
    configurable_fields: str | None = field(
        default=None,
        metadata={
            "help": "Fields that can be configured at runtime. "
            "Use 'any' for all fields or provide a comma-separated list of field names."
        },
    )
