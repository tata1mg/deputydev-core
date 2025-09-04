from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class FileUploadConfigInterface(ABC):
    """File upload specific configuration"""

    @abstractmethod
    def get_s3_config(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_file_upload_paths(self) -> Dict[str, str]:
        pass