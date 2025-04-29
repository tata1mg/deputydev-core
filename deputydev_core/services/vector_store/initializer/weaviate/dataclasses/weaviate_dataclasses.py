from typing import List
from pydantic import BaseModel

from deputydev_core.utils.constants.weaviate import WeaviateSupportedArchitecture


class WeaviateDownloadPlatformConfig(BaseModel):
    """Configuration for Weaviate download based on platform and architecture."""

    supported_archs: List[WeaviateSupportedArchitecture]
    combined_package: bool
    package_ext: str
    extracted_file_name: str
