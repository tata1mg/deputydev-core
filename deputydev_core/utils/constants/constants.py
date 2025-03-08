from enum import Enum

APP_VERSION = "1.0.4"
WEAVIATE_SCHEMA_VERSION = 1
LARGE_NO_OF_CHUNKS = 60
JAVASCRIPT_EXTENSIONS = {
    "js": "javascript",
    "jsx": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "es": "javascript",
    "es6": "javascript",
}
EXTENSION_TO_LANGUAGE = {
    "py": "python",
    "html": "html",
    "kt": "kotlin",
    "go": "go",
    "json": "json",
}
TSX_EXTENSIONS = {"tsx": "tsx"}
JAVA_EXTENSIONS = {"java": "java"}
TYPESCRIPT_EXTENSIONS = {
    "ts": "typescript",
    "mts": "typescript",
    "cts": "typescript",
}

ALL_EXTENSIONS = {
    **JAVASCRIPT_EXTENSIONS,
    **TYPESCRIPT_EXTENSIONS,
    **JAVA_EXTENSIONS,
    **TSX_EXTENSIONS,
    **EXTENSION_TO_LANGUAGE,
}


class ExtendedEnum(Enum):
    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class LLMModelNames(ExtendedEnum):
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    GPT_4_PREVIEW = "gpt-4-1106-preview"
    GPT_4_O = "gpt-4o"
    GPT_TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"


class AuthTokenKeys(Enum):
    CLI_AUTH_TOKEN = "cli_auth_token"
    EXTENSION_AUTH_TOKEN = "extension_auth_token"


class LocalDirectories(Enum):
    LOCAL_ROOT_DIRECTORY = ".deputydev"


class LocalFiles(Enum):
    LOCAL_AUTH_TOKENS_FILE = "264325ba-cbd0-47d5-9269-ac4bd19067c2.json"


class TimeFormat(Enum):
    SECONDS = "SECONDS"
    MINUTES = "MINUTES"
