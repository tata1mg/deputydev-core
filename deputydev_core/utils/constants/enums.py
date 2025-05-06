from enum import Enum


class ConfigConsumer(Enum):
    VSCODE_EXT = "VSCODE_EXT"
    CLI = "CLI"
    BINARY = "BINARY"


class Clients(Enum):
    CLI = "CLI"
    BACKEND = "BACKEND"
    VSCODE_EXT = "VSCODE_EXT"
    BINARY = "BINARY"
    WEB = "WEB"


class ContextValueKeys(Enum):
    BINARY_CONFIG = "BINARY_CONFIG"
    CLI_AUTH_TOKEN = "CLI_AUTH_TOKEN"
    EXTENSION_AUTH_TOKEN = "EXTENSION_AUTH_TOKEN"


class AuthTokenStorageManagers(Enum):
    CLI_AUTH_TOKEN_STORAGE_MANAGER = "cli"
    EXTENSION_AUTH_TOKEN_STORAGE_MANAGER = "extension"


class Status(Enum):
    SUCCESS = "success"
    FAILED = "failed"
