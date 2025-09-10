from typing import Any, AsyncIterator, Dict, Iterable, List, Literal, Optional, Type, Union, cast

import httpx
from openai import AsyncOpenAI
from openai._streaming import AsyncStream
from openai.types.chat import ChatCompletion
from openai.types.responses import (
    Response,
    ResponseFormatTextJSONSchemaConfigParam,
    ResponseInputItemParam,
    ResponseTextConfigParam,
)
from openai.types.responses.response_create_params import ToolChoice
from openai.types.responses.response_stream_event import ResponseStreamEvent
from openai.types.shared_params.response_format_json_object import ResponseFormatJSONObject
from openai.types.shared_params.response_format_text import ResponseFormatText
from openai.types.shared_params.responses_model import ResponsesModel
from pydantic import BaseModel

from deputydev_core.utils.singleton import Singleton


class OpenAIServiceClient(metaclass=Singleton):
    def __init__(self, api_key: str, timeout: int) -> None:
        self.__client = AsyncOpenAI(
            api_key=api_key,
            timeout=timeout,
            http_client=httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(
                    max_connections=1000,
                    max_keepalive_connections=100,
                    keepalive_expiry=20,
                ),
            ),
        )

    async def get_llm_non_stream_response(
        self,
        conversation_messages: List[Dict[str, Any]],
        model: str,
        tool_choice: Literal["none", "auto", "required"] = "none",
        tools: Optional[List[Dict[str, Any]]] = None,
        response_type: Optional[Literal["text", "json_object", "json_schema"]] = "json_schema",
        response_schema: Any = None,
        response_format_name: Any = None,
        response_format_description: Any = None,
        instructions: str = None,
        max_output_tokens: str = None,
        parallel_tool_calls: bool = True,
    ) -> Response:
        response_type = self._get_response_text_config(
            response_type=response_type,
            response_schema=response_schema,
            schema_name=response_format_name,
            schema_description=response_format_description,
        )
        response = await self.__client.responses.create(
            input=conversation_messages,
            model=model,
            tool_choice=tool_choice,
            tools=tools,
            stream=False,
            text=response_type,
            parallel_tool_calls=parallel_tool_calls,
            instructions=instructions,
            max_output_tokens=max_output_tokens,
        )
        # we need both message and output token now to returning full completion message
        return response

    async def get_llm_non_stream_response_api(  # noqa: ANN201
        self,
        conversation_messages: List[Dict[str, Any]],
        model: str,
        tool_choice: Literal["none", "auto", "required"] = "auto",
        tools: Optional[List[Dict[str, Any]]] = None,
        instructions: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        parallel_tool_calls: bool = False,
        text_format: Optional[Type[BaseModel]] = None,
        reasoning: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
    ):
        # Build the request payload, filtering out any None values
        kwargs: Dict[str, Any] = {
            "model": model,
            "input": conversation_messages,
            "tool_choice": tool_choice,
            "tools": tools,
            "instructions": instructions,
            "max_output_tokens": max_output_tokens,
            "parallel_tool_calls": parallel_tool_calls,
            "reasoning": reasoning or {},
            "text_format": text_format,
            "store": False,
        }
        request_args = {k: v for k, v in kwargs.items() if v is not None}

        response = await self.__client.responses.parse(**request_args)
        return response

    async def get_llm_non_stream_response_chat_api(
        self,
        conversation_messages: List[Dict[str, Any]],
        model: str,
        tool_choice: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        response_type: Optional[Literal["text", "json_object", "json_schema"]] = "json_object",
    ) -> ChatCompletion:
        # THIS WILL BE DEPRECATED DO NOT USE THIS.
        if response_type == "text":
            response_format = ResponseFormatText(type=response_type)
        else:
            response_format = ResponseFormatJSONObject(type=response_type)
        completion = await self.__client.chat.completions.create(
            model=model,
            response_format=response_format,
            messages=conversation_messages,
        )

        # we need both message and output token now to returning full completion message
        return completion

    async def create_embedding(  # noqa : ANN201
        self,
        input: Union[str, List[str], Iterable[int], Iterable[Iterable[int]]],
        model: str,
        encoding_format: Literal["float", "base64"],
    ):
        embeddings = await self.__client.embeddings.create(
            input=input, model=model, encoding_format=encoding_format, timeout=2
        )
        return embeddings

    def _create_valid_responses_params(
        self,
        conversation_messages: List[ResponseInputItemParam],
        model: ResponsesModel,
        response_text_config: ResponseTextConfigParam,
        tool_choice: Optional[ToolChoice] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        instructions: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        parallel_tool_calls: bool = True,
    ) -> Dict[str, Any]:
        all_params: Dict[str, Any] = {
            "input": conversation_messages,
            "model": model,
            "tool_choice": tool_choice,
            "tools": tools,
            "stream": True,
            "text": response_text_config,
            "parallel_tool_calls": parallel_tool_calls,
            "instructions": instructions,
            "max_output_tokens": max_output_tokens,
            "extra_body": {"prompt_cache_key": f"{model}_X"},
        }
        return {k: v for k, v in all_params.items() if v is not None}

    def _get_response_text_config(
        self, response_type: Any, response_schema: Any = None, schema_name: Any = None, schema_description: Any = None
    ) -> ResponseTextConfigParam:
        if response_type == "json_schema":
            return ResponseTextConfigParam(
                format=ResponseFormatTextJSONSchemaConfigParam(
                    name=schema_name,
                    schema=response_schema,
                    type=response_type,
                    description=schema_description,
                )
            )
        elif response_type == "text":
            return ResponseTextConfigParam(format=ResponseFormatText(type=response_type))
        elif response_type == "json_object":
            return ResponseTextConfigParam(format=ResponseFormatJSONObject(type=response_type))
        else:
            raise ValueError("Invalid response type")

    async def get_llm_stream_response(
        self,
        conversation_messages: List[ResponseInputItemParam],
        model: ResponsesModel,
        tool_choice: Optional[ToolChoice] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        response_type: Optional[Literal["text", "json_object", "json_schema"]] = "json_object",
        response_schema: Any = None,
        response_format_name: Any = None,
        response_format_description: Any = None,
        instructions: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        parallel_tool_calls: bool = True,
    ) -> AsyncIterator[ResponseStreamEvent]:
        response_type_config = self._get_response_text_config(
            response_type=response_type,
            response_schema=response_schema,
            schema_name=response_format_name,
            schema_description=response_format_description,
        )
        response: AsyncStream[ResponseStreamEvent] = cast(
            AsyncStream[ResponseStreamEvent],
            await self.__client.responses.create(
                **self._create_valid_responses_params(
                    conversation_messages=conversation_messages,
                    model=model,
                    response_text_config=response_type_config,
                    tool_choice=tool_choice,
                    tools=tools,
                    instructions=instructions,
                    max_output_tokens=max_output_tokens,
                    parallel_tool_calls=parallel_tool_calls,
                )
            ),
        )
        return response.__stream__()
