from typing import Any, AsyncIterator, Dict, List, Optional

from google import genai
from google.genai import errors, types
from google.oauth2 import service_account

from deputydev_core.clients.exceptions import GeminiThrottledError
from deputydev_core.utils.singleton import Singleton


class GeminiServiceClient(metaclass=Singleton):
    def __init__(self, vertex_config: Dict[str, Any]) -> None:
        credentials_dict = {
            "type": vertex_config.get("type"),
            "project_id": vertex_config.get("project_id"),
            "private_key_id": vertex_config.get("private_key_id"),
            "private_key": vertex_config.get("private_key"),
            "client_email": vertex_config.get("client_email"),
            "client_id": vertex_config.get("client_id"),
            "auth_uri": vertex_config.get("auth_uri"),
            "token_uri": vertex_config.get("token_uri"),
            "auth_provider_x509_cert_url": vertex_config.get("auth_provider_x509_cert_url"),
            "client_x509_cert_url": vertex_config.get("client_x509_cert_url"),
            "universe_domain": vertex_config.get("universe_domain"),
        }
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        self.client = genai.Client(
            http_options=types.HttpOptions(api_version="v1"),
            vertexai=True,
            credentials=credentials,
            project=credentials_dict["project_id"],
            location=vertex_config.get("location"),
        )

    async def get_llm_non_stream_response(
        self,
        model_name: str,
        contents: List[types.Content],
        system_instruction: types.Part = None,
        tools: List[types.Tool] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.5,
        tool_config: Optional[types.ToolConfig] = None,
        response_mime_type: str = "text/plain",
        max_output_tokens: int = 8192,
    ) -> types.GenerateContentResponse:
        data = await self.client.aio.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=tools,
                temperature=temperature,
                response_mime_type=response_mime_type,
                response_schema=response_schema,
                max_output_tokens=max_output_tokens,
            ),
        )
        return data

    async def get_llm_stream_response(
        self,
        model_name: str,
        contents: List[types.Content],
        temperature: float,
        thinking_budget_tokens: int,
        max_output_tokens: int,
        tool_config: Optional[types.ToolConfig] = None,
        system_instruction: types.Part = None,
        tools: List[types.Tool] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        response_mime_type: str = "text/plain",
    ) -> AsyncIterator[types.GenerateContentResponse]:
        try:
            base_stream = await self.client.aio.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=tools,
                    temperature=temperature,
                    response_mime_type=response_mime_type,
                    response_schema=response_schema,
                    thinking_config=types.ThinkingConfig(
                        include_thoughts=False, thinking_budget=thinking_budget_tokens
                    ),
                    max_output_tokens=max_output_tokens,
                ),
            )
        except errors.APIError as e:
            if e.code == 429:
                raise GeminiThrottledError(model=model_name, retry_after=None, detail=str(e)) from e
            raise

        return base_stream

    async def get_tokens(self, content: str, model_name: str) -> int:
        tokens = self.client.models.count_tokens(model=model_name, contents=content)
        return tokens.total_tokens or 0
