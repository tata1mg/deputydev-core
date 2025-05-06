from enum import Enum
from typing import List

from pydantic import BaseModel


class WeaviateSupportedPlatforms(Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MAC = "darwin"


class WeaviateSupportedArchitecture(Enum):
    ARM64 = "arm64"
    AMD64 = "amd64"


class WeaviateDownloadPlatformConfig(BaseModel):
    """Configuration for Weaviate download based on platform and architecture."""

    supported_archs: List[WeaviateSupportedArchitecture]
    combined_package: bool
    package_ext: str
    extracted_file_name: str
