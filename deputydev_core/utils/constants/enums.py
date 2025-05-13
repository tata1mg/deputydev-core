from enum import Enum


class ConfigConsumer(Enum):
    VSCODE_EXT = "VSCODE_EXT"
    CLI = "CLI"
    BINARY = "BINARY"
    PR_REVIEW = "PR_REVIEW"


class Clients(Enum):
    CLI = "CLI"
    BACKEND = "BACKEND"
    VSCODE_EXT = "VSCODE_EXT"
    BINARY = "BINARY"
    WEB = "WEB"
    REVIEW = "REVIEW"


class SharedMemoryKeys(Enum):
    BINARY_CONFIG = "BINARY_CONFIG"
    CLI_AUTH_TOKEN = "CLI_AUTH_TOKEN"
    EXTENSION_AUTH_TOKEN = "EXTENSION_AUTH_TOKEN"
    PR_REVIEW_TOKEN = "PR_REVIEW_TOKEN"
    WEAVIATE_CLIENT = "WEAVIATE_CLIENT"


class AuthTokenStorageManagers(Enum):
    CLI_AUTH_TOKEN_STORAGE_MANAGER = "cli"
    EXTENSION_AUTH_TOKEN_STORAGE_MANAGER = "extension"


class Status(Enum):
    SUCCESS = "success"
    FAILED = "failed"

class ContextValueKeys(Enum):
    WEAVIATE_CLIENT = "weaviate_client"
    PR_REVIEW_TOKEN = "pr_review_token"


