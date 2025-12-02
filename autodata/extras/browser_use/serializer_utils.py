"""Message serialization utilities for LangChain and browser-use interoperability.

This module provides serializers to convert between browser-use and LangChain
message formats for seamless integration.

Credits:
    Original implementation from browser-use examples:
    https://github.com/browser-use/browser-use/blob/main/examples/models/langchain/serializer.py
"""

from __future__ import annotations

import json
from typing import overload

from browser_use.llm.messages import (
    AssistantMessage,
    BaseMessage,
    ContentPartImageParam,
    ContentPartRefusalParam,
    ContentPartTextParam,
    ToolCall,
    UserMessage,
)
from browser_use.llm.messages import SystemMessage as BrowserUseSystemMessage
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.messages import ToolCall as LangChainToolCall
from langchain_core.messages.base import BaseMessage as LangChainBaseMessage


class LangChainMessageSerializer:
    """Serializer for converting between browser-use and LangChain message types."""

    @staticmethod
    def _serialize_user_content(
        content: str | list[ContentPartTextParam | ContentPartImageParam],
    ) -> str | list[str | dict]:
        """Convert user message content for LangChain compatibility.

        Args:
            content: User message content from browser-use

        Returns:
            LangChain-compatible content format
        """
        if isinstance(content, str):
            return content

        serialized_parts = []
        for part in content:
            if part.type == "text":
                serialized_parts.append(
                    {
                        "type": "text",
                        "text": part.text,
                    }
                )
            elif part.type == "image_url":
                # LangChain format for images
                serialized_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": part.image_url.url,
                            "detail": part.image_url.detail,
                        },
                    }
                )

        return serialized_parts

    @staticmethod
    def _serialize_system_content(
        content: str | list[ContentPartTextParam],
    ) -> str:
        """Convert system message content to text string for LangChain compatibility.

        Args:
            content: System message content from browser-use

        Returns:
            Plain text string for LangChain
        """
        if isinstance(content, str):
            return content

        text_parts = []
        for part in content:
            if part.type == "text":
                text_parts.append(part.text)

        return "\n".join(text_parts)

    @staticmethod
    def _serialize_assistant_content(
        content: str | list[ContentPartTextParam | ContentPartRefusalParam] | None,
    ) -> str:
        """Convert assistant message content to text string for LangChain compatibility.

        Args:
            content: Assistant message content from browser-use

        Returns:
            Plain text string for LangChain
        """
        if content is None:
            return ""
        if isinstance(content, str):
            return content

        text_parts = []
        for part in content:
            if part.type == "text":
                text_parts.append(part.text)

        return "\n".join(text_parts)

    @staticmethod
    def _serialize_tool_call(tool_call: ToolCall) -> LangChainToolCall:
        """Convert browser-use ToolCall to LangChain ToolCall.

        Args:
            tool_call: Browser-use tool call

        Returns:
            LangChain tool call
        """
        # Parse the arguments string to a dict for LangChain
        try:
            args_dict = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            # If parsing fails, wrap in a dict
            args_dict = {"arguments": tool_call.function.arguments}

        return LangChainToolCall(
            name=tool_call.function.name,
            args=args_dict,
            id=tool_call.id,
        )

    @overload
    @staticmethod
    def serialize(message: UserMessage) -> HumanMessage: ...

    @overload
    @staticmethod
    def serialize(message: BrowserUseSystemMessage) -> SystemMessage: ...

    @overload
    @staticmethod
    def serialize(message: AssistantMessage) -> AIMessage: ...

    @staticmethod
    def serialize(message: BaseMessage) -> LangChainBaseMessage:
        """Serialize a browser-use message to a LangChain message.

        Args:
            message: Browser-use message to convert

        Returns:
            LangChain message

        Raises:
            ValueError: If message type is unknown
        """
        if isinstance(message, UserMessage):
            content = LangChainMessageSerializer._serialize_user_content(
                message.content
            )
            return HumanMessage(content=content, name=message.name)

        elif isinstance(message, BrowserUseSystemMessage):
            content = LangChainMessageSerializer._serialize_system_content(
                message.content
            )
            return SystemMessage(content=content, name=message.name)

        elif isinstance(message, AssistantMessage):
            # Handle content
            content = LangChainMessageSerializer._serialize_assistant_content(
                message.content
            )

            # For simplicity, we ignore tool calls in LangChain integration
            return AIMessage(
                content=content,
                name=message.name,
            )

        else:
            raise ValueError(f"Unknown message type: {type(message)}")

    @staticmethod
    def serialize_messages(messages: list[BaseMessage]) -> list[LangChainBaseMessage]:
        """Serialize a list of browser-use messages to LangChain messages.

        Args:
            messages: List of browser-use messages

        Returns:
            List of LangChain messages
        """
        return [LangChainMessageSerializer.serialize(m) for m in messages]
