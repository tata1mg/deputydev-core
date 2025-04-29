from enum import Enum

WEAVIATE_SCHEMA_VERSION = 12


class WeaviateSupportedPlatforms(Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MAC = "darwin"


class WeaviateSupportedArchitecture(Enum):
    ARM64 = "arm64"
    AMD64 = "amd64"
