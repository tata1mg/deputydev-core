from enum import Enum


class ConfigConsumer(Enum):
    VSCODE_EXT = "VSCODE_EXT"
    CLI = "CLI"
    BINARY = "BINARY"


class SharedMemoryKeys(Enum):
    BINARY_CONFIG = "BINARY_CONFIG"
    CLI_AUTH_TOKEN = "CLI_AUTH_TOKEN"
    EXTENSION_AUTH_TOKEN = "EXTENSION_AUTH_TOKEN"
