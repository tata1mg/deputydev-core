from typing import Any, Dict, Union

from deputydev_core.services.auth_token_storage.cli_auth_token_storage_manager import (
    CLIAuthTokenStorageManager,
)
from deputydev_core.services.auth_token_storage.extension_auth_token_storage_manager import (
    ExtensionAuthTokenStorageManager,
)
from deputydev_core.utils.constants.enums import Clients, SharedMemoryKeys, Status
from deputydev_core.utils.shared_memory import SharedMemory


class AuthTokenService:
    """
    A service class for managing authentication tokens, including storing and loading tokens
    from different storage managers.
    """

    @classmethod
    def get_auth_token_storage_manager(
        cls, client: str
    ) -> Union[CLIAuthTokenStorageManager, ExtensionAuthTokenStorageManager]:
        """
        Retrieves the appropriate authentication token storage manager based on the provided type.

        Args:
            client (str): client (CLI, VSCODE_EXT).

        Returns:
            Union[CLIAuthTokenStorageManager, ExtensionAuthTokenStorageManager]: The corresponding storage manager instance.

        Raises:
            ValueError: If the storage manager type is invalid.
        """
        if client == Clients.CLI.value:
            return CLIAuthTokenStorageManager
        elif client == Clients.VSCODE_EXT.value:
            return ExtensionAuthTokenStorageManager
        else:
            raise ValueError("Invalid client")

    @classmethod
    async def store_token(cls, client: str) -> Dict[str, Any]:
        """
        Stores the authentication token using the specified storage manager.

        Args:
            client (str): client (CLI, VSCODE_EXT).

        Returns:
            Dict[str, Any]: A dictionary containing the result of the operation, including success or failure messages.

        Raises:
            ValueError: If the required headers are not found.
        """
        try:
            storage_manager = cls.get_auth_token_storage_manager(client)
            token = cls.get_auth_token(client)
            storage_manager.store_auth_token(token)
            return {"message": Status.SUCCESS.value}
        except (ValueError, Exception) as e:
            return {
                "message": Status.FAILED.value,
                "error": f"Failed to store auth token: {e}",
            }

    @classmethod
    async def load_token(cls, client: str) -> Dict[str, Any]:
        """
        Loads the authentication token using the specified storage manager.

        Args:
            client (str): client (CLI, VSCODE_EXT).

        Returns:
            Dict[str, Any]: A dictionary containing the loaded token and success or failure messages.

        Raises:
            ValueError: If the required headers are not found.
        """
        try:
            storage_manager = cls.get_auth_token_storage_manager(client)
            auth_token = storage_manager.load_auth_token()
            return {"message": Status.SUCCESS.value, "auth_token": auth_token}
        except (ValueError, Exception) as e:
            return {
                "message": Status.FAILED.value,
                "error": f"Failed to load auth token: {e}",
            }

    @classmethod
    def get_auth_token(cls, client: str) -> str:
        if client == Clients.CLI.value:
            return SharedMemory.read(SharedMemoryKeys.CLI_AUTH_TOKEN.value)
        elif client == Clients.VSCODE_EXT.value:
            return SharedMemory.read(SharedMemoryKeys.EXTENSION_AUTH_TOKEN.value)
        else:
            raise ValueError("Invalid Client")
