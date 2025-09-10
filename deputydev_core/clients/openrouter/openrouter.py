from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Literal, Optional, TypedDict

import httpx
from openai import AsyncOpenAI
from openai._streaming import AsyncStream
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
from openai.types.responses.response_stream_event import ResponseStreamEvent

from deputydev_core.clients.exceptions import OpenrouterThrottledError
from deputydev_core.llm_handler.dataclasses.main import Reasoning
from deputydev_core.utils.singleton import Singleton


class FunctionDict(TypedDict):
    name: str


class FunctionToolChoice(TypedDict):
    type: Literal["function"]
    function: FunctionDict


ToolChoice = Literal["none"] | Literal["auto"] | FunctionToolChoice

ResponseType = Optional[Literal["text", "json_object", "json_schema"]]


class OpenRouterServiceClient(metaclass=Singleton):
    """
    Thin wrapper around OpenRouter's OpenAI‑compatible API.

    Use `chat()` for one‑shot requests and `stream_chat()` for SSE‑style
    token streaming.
    """

    def __init__(self, config) -> None:
        self._client = AsyncOpenAI(
            base_url=config.get("BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=config["API_KEY"],
            http_client=httpx.AsyncClient(
                timeout=config.get("TIMEOUT", 60),
                limits=httpx.Limits(
                    max_connections=config.get("MAX_CONN", 1000),
                    max_keepalive_connections=config.get("MAX_KEEPALIVE", 100),
                    keepalive_expiry=20,
                ),
            ),
        )

    # ---------- public helpers ------------------------------------------------
    async def get_llm_non_stream_response(
        self,
        *,
        model: str,
        session_id: int,
        models: Optional[List[str]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        conversation_messages: List[ChatCompletionMessageParam],
        tools: Optional[List[ChatCompletionToolParam]] = None,
        parallel_tool_calls: bool = False,
        tool_choice: ToolChoice = "none",
        transformation: Optional[List[str]] = None,
        reasoning: Optional[Reasoning] = None,
        provider: Optional[Dict[str, Any]] = None,
        response_format: Optional[Literal["text", "json_object", "json_schema"]] = None,
        structured_outputs: Optional[bool] = None,
    ) -> ChatCompletion:
        """
        Send a chat completion. Returns the full `ChatCompletion` object.
        Extra kwargs are forwarded verbatim to OpenAI for future-proofing.
        """
        kwargs = self._build_common_kwargs(
            model=model,
            messages=conversation_messages,
            tools=tools,
            tool_choice=tool_choice,
            parallel_tool_calls=parallel_tool_calls,
            stream=False,
            max_tokens=max_tokens,
            temperature=temperature,
            transformation=transformation,
            reasoning=reasoning,
            provider=provider,
            response_format=response_format,
            structured_outputs=structured_outputs,
            session_id=session_id,
        )

        try:
            response: ChatCompletion = await self._client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise OpenrouterThrottledError(
                    model=model,
                    retry_after=e.response.headers.get("Retry-After"),
                    detail=str(e),
                ) from e
            raise

    async def get_llm_stream_response(
        self,
        *,
        model: str,
        models: Optional[List[str]] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        messages: List[ChatCompletionMessageParam],
        tools: Optional[List[ChatCompletionToolParam]] = None,
        tool_choice: ToolChoice = "none",
        transformation: Optional[List[str]] = None,
        reasoning: Optional[Reasoning] = None,
        provider: Optional[Dict[str, Any]] = None,
        response_format: ResponseType = "text",
        structured_outputs: Optional[bool] = None,
        parallel_tool_calls: bool = False,
        session_id: int,
    ) -> AsyncIterator[ResponseStreamEvent]:
        """
        Convenience alias that always streams.
        """
        kwargs = self._build_common_kwargs(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            stream=True,
            max_tokens=max_tokens,
            temperature=temperature,
            transformation=transformation,
            reasoning=reasoning,
            provider=provider,
            response_format=response_format,
            structured_outputs=structured_outputs,
            session_id=session_id,
            parallel_tool_calls=parallel_tool_calls,
        )

        try:
            response: AsyncStream[ResponseStreamEvent] = await self._client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
            return response.__stream__()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise OpenrouterThrottledError(
                    model=model,
                    retry_after=e.response.headers.get("Retry-After"),
                    detail=str(e),
                ) from e
            raise

    @staticmethod
    def _build_extra_body(
        session_id: int, reasoning: Optional[Reasoning], provider: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        extra_body: Optional[Dict[str, Any]] = {}
        if reasoning is not None:
            extra_body["reasoning"] = {"effort": reasoning.name.lower()}
        if provider is not None:
            extra_body["provider"] = provider
        extra_body["user"] = str(session_id)
        return extra_body or None

    @staticmethod
    def _build_common_kwargs(
        model: str,
        messages: List[ChatCompletionMessageParam],
        tools: Optional[List[ChatCompletionToolParam]],
        tool_choice: ToolChoice,
        parallel_tool_calls: bool,
        stream: bool,
        session_id: int,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        transformation: Optional[List[str]] = None,
        reasoning: Optional[Reasoning] = None,
        provider: Optional[Dict[str, Any]] = None,
        response_format: Optional[str] = None,
        structured_outputs: Optional[bool] = None,
    ) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": parallel_tool_calls,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "transformation": transformation,
            "extra_body": OpenRouterServiceClient._build_extra_body(session_id, reasoning, provider),
            "response_format": {"type": response_format} if response_format and response_format != "text" else None,
            "structured_outputs": structured_outputs,
            "stream_options": {"include_usage": True},  # <-- Hardcoded usage block
            "extra_headers": {
                "HTTP-Referer": "https://deputydev.ai/",
                "X-Title": "DeputyDev: AI Powered Developer Assistant",
            },
        }

        # Remove keys with None values to slim the payload
        return {k: v for k, v in base.items() if v is not None}
