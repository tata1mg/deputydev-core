import json
import os
from typing import Union

from deputydev_core.utils.constants.constants import LocalDirectories, LocalFiles


class AuthTokenStorageBase:
    """
    A base class for managing authentication tokens using persistent storage in JSON format.

    This class provides methods to store and load authentication tokens
    in a JSON file located in a hidden directory in the user's home directory.

    Attributes:
        token_dir (str): The path to the directory where the JSON file is stored.
        token_file (str): The path to the JSON file used for storing the token.

    Methods:
        ensure_token_directory(): Ensures that the directory for storing tokens exists.
        store_auth_token(token: str): Stores the provided authentication token in the JSON file.
        load_auth_token() -> Union[str, None]: Loads the authentication token from the JSON file, returning None if not found.
    """

    token_dir = os.path.join(os.path.expanduser("~"), LocalDirectories.LOCAL_ROOT_DIRECTORY.value)
    token_file = os.path.join(token_dir, LocalFiles.LOCAL_AUTH_TOKENS_FILE.value)

    @classmethod
    def ensure_token_directory(cls):
        os.makedirs(cls.token_dir, exist_ok=True)

    @classmethod
    def store_auth_token(cls, token: str):
        cls.ensure_token_directory()
        if os.path.exists(cls.token_file):
            with open(cls.token_file, "r") as f:
                data = json.load(f)
            with open(cls.token_file, "w") as f:
                data[cls.key_name] = token
                json.dump(data, f)
        else:
            with open(cls.token_file, "w") as f:
                json.dump({cls.key_name: token}, f)

    @classmethod
    def load_auth_token(cls) -> Union[str, None]:
        if os.path.exists(cls.token_file):
            with open(cls.token_file, "r") as f:
                data = json.load(f)
                return data.get(cls.key_name)
        return None

    @classmethod
    def delete_auth_token(cls):
        if os.path.exists(cls.token_file):
            with open(cls.token_file, 'r') as file:
                tokens = json.load(file)
            tokens.pop(cls.key_name, None)
            with open(cls.token_file, 'w') as file:
                json.dump(tokens, file)