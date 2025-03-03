from deputydev_core.services.auth_token_storage.base_auth_token_storage_manager import (
    AuthTokenStorageBase,
)
from deputydev_core.utils.constants import AuthTokenKeys


class CLIAuthTokenStorageManager(AuthTokenStorageBase):
    """
    A class to manage authentication tokens specifically for the command-line interface (CLI)
    using a persistent storage mechanism.

    Inherits from AuthTokenStorageBase and defines the key_name for storing
    and retrieving the authentication token.

    Attributes:
        key_name (str): The name of the key used to store the authentication token,
                        derived from the AuthTokenKeys. This key is essential
                        for ensuring that the correct token is accessed and
                        managed within the persistent storage.
    """

    key_name = AuthTokenKeys.CLI_AUTH_TOKEN.value
