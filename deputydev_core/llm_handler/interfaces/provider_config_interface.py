from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ProviderConfigInterface(ABC):
    """Provider-specific configuration interface"""

    @abstractmethod
    def get_openai_config(self) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_anthropic_config(self) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_openrouter_config(self) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_aws_config(self) -> Optional[Dict[str, Any]]:
        pass
