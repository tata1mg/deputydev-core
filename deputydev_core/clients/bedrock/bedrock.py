import json
from typing import Any, Dict, Optional, Tuple

from aiobotocore.config import AioConfig  # type: ignore
from aiobotocore.session import get_session  # type: ignore
from botocore.exceptions import ClientError
from types_aiobotocore_bedrock_runtime import BedrockRuntimeClient
from types_aiobotocore_bedrock_runtime.type_defs import (
    InvokeModelResponseTypeDef,
    InvokeModelWithResponseStreamResponseTypeDef,
)

from deputydev_core.clients.exceptions import AnthropicThrottledError


class BedrockServiceClient:
    def __init__(self, region_name: str, aws_config: dict) -> None:
        self.client: Optional[BedrockRuntimeClient] = None
        self.region_name = region_name
        self.aws_config = aws_config["AWS"]

    def _get_bedrock_client(self) -> BedrockRuntimeClient:
        session = get_session()
        config = AioConfig(read_timeout=self.aws_config["BEDROCK_READ_TIMEOUT"])  # type: ignore
        self.client = session.create_client(  # type: ignore
            service_name=self.aws_config["BEDROCK_SERVICE_NAME"],  # type: ignore
            aws_access_key_id=self.aws_config.get("ACCESS_KEY_ID"),  # type: ignore
            aws_secret_access_key=self.aws_config.get("SECRET_ACCESS_KEY"),  # type: ignore
            aws_session_token=self.aws_config.get("SESSION_TOKEN"),  # type: ignore
            region_name=self.region_name,  # type: ignore
            config=config,  # type: ignore
        )

        if not self.client:
            raise ValueError("Failed to create Bedrock client")
        return self.client

    async def get_llm_non_stream_response(self, llm_payload: Dict[str, Any], model: str) -> InvokeModelResponseTypeDef:
        bedrock_client = self._get_bedrock_client()
        async with bedrock_client as client:
            response = await client.invoke_model(modelId=model, body=json.dumps(llm_payload))
            return response

    async def get_llm_stream_response(
        self, llm_payload: Dict[str, Any], model: str
    ) -> Tuple[InvokeModelWithResponseStreamResponseTypeDef, BedrockRuntimeClient]:
        bedrock_client = await self._get_bedrock_client().__aenter__()
        try:
            response = await bedrock_client.invoke_model_with_response_stream(
                modelId=model, body=json.dumps(llm_payload)
            )
            return response, bedrock_client
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
            if code == "ThrottlingException" or status == 429:
                await bedrock_client.__aexit__(None, None, None)
                raise AnthropicThrottledError(
                    model=model, region=self.region_name, retry_after=None, detail=str(e)
                ) from e
            await bedrock_client.__aexit__(None, None, None)
            raise e
        except Exception as e:
            await bedrock_client.__aexit__(None, None, None)
            raise e
