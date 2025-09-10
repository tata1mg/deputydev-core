from typing import Optional

from aiobotocore.client import AioBaseClient  # type: ignore
from aiobotocore.config import AioConfig  # type: ignore
from aiobotocore.endpoint import MAX_POOL_CONNECTIONS  # type: ignore
from aiobotocore.session import AioSession, ClientCreatorContext, get_session  # type: ignore

from deputydev_core.clients.aws.dataclasses.aws_client_manager import AWSConfig, AWSConnectionParams
from deputydev_core.utils.app_logger import AppLogger  # type: ignore
from deputydev_core.utils.config_manager import ConfigManager  # type: ignore


class AWSClientManager:
    DEFAULT_TIMEOUT_IN_SECONDS = 10
    DEFAULT_MAX_POOL_CONNECTIONS = MAX_POOL_CONNECTIONS

    def __init__(
        self,
        aws_service_name: str,
        region_name: str,
        aws_connection_params: Optional[AWSConnectionParams] = None,
        aws_config: Optional[AWSConfig] = None,
    ) -> None:
        # set service and region
        self.aws_service_name = aws_service_name
        self.region_name = region_name

        # set AWS connection params and override with provided params if any
        self.aws_access_key_id = ConfigManager.configs["AWS"]["ACCESS_KEY_ID"]
        self.aws_secret_access_key = ConfigManager.configs["AWS"]["SECRET_ACCESS_KEY"]
        self.endpoint_url = ConfigManager.configs["AWS"]["ENDPOINT_URL"]
        if aws_connection_params:
            self.aws_access_key_id = aws_connection_params.aws_access_key_id
            self.aws_secret_access_key = aws_connection_params.aws_secret_access_key
            self.endpoint_url = aws_connection_params.endpoint_url

        # define the AWS config (use given config by default)
        aws_config_to_use: AWSConfig = aws_config if aws_config else AWSConfig()

        # determine default values for connect_timeout, read_timeout, and max_pool_connections and signature_version
        connect_timeout: int = ConfigManager.configs["AWS"].get("CONNECT_TIMEOUT", self.DEFAULT_TIMEOUT_IN_SECONDS)
        read_timeout: int = ConfigManager.configs["AWS"].get("READ_TIMEOUT", self.DEFAULT_TIMEOUT_IN_SECONDS)
        max_pool_connections: int = ConfigManager.configs["AWS"].get(
            "MAX_POOL_CONNECTIONS", self.DEFAULT_MAX_POOL_CONNECTIONS
        )
        signature_version: Optional[str] = ConfigManager.configs["AWS"].get("SIGNATURE_VERSION", None)

        # now, if these values are not set in the config, we can set them to the default values
        if aws_config_to_use.connect_timeout is None:
            aws_config_to_use.connect_timeout = connect_timeout
        if aws_config_to_use.read_timeout is None:
            aws_config_to_use.read_timeout = read_timeout
        if aws_config_to_use.max_pool_connections is None:
            aws_config_to_use.max_pool_connections = max_pool_connections
        if aws_config_to_use.signature_version is None:
            aws_config_to_use.signature_version = signature_version

        # set the config as AioConfig
        self.aws_config = AioConfig(
            **aws_config_to_use.model_dump(mode="json"),
        )

        # set the client initially to None
        self._client: Optional[AioBaseClient] = None

    async def _create_client(self) -> AioBaseClient:
        try:
            session: AioSession = get_session()
            client_creator_context: ClientCreatorContext = session.create_client(  # type: ignore
                service_name=self.aws_service_name,
                region_name=self.region_name,
                config=self.aws_config,
                endpoint_url=self.endpoint_url,
                aws_secret_access_key=self.aws_secret_access_key,
                aws_access_key_id=self.aws_access_key_id,
            )
            return await client_creator_context.__aenter__()
        except Exception as _ex:
            AppLogger.log_error(
                f"Failed to create AWS client for {self.aws_service_name} in region {self.region_name}: {_ex}"
            )
            raise _ex

    async def get_client(self) -> AioBaseClient:
        """
        Get the AWS client. If the client is not already created, create it.
        """
        if not self._client:
            self._client = await self._create_client()
        return self._client

    async def close_client(self) -> None:
        """
        Close the AWS client. This is important to avoid resource leaks.
        """
        if self._client:
            await self._client.__aexit__(None, None, None)  # type: ignore
            del self._client
        else:
            raise ValueError("Client not initialized. Please call get_client() first.")
