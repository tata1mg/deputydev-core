from abc import ABC, abstractmethod
from typing import Any, Dict


class LLMConfigInterface(ABC):
    """Base configuration interface for LLM operations"""

    @abstractmethod
    def get_llm_max_retry(self) -> int:
        pass

    @abstractmethod
    def get_llm_models_config(self) -> Dict[str, Any]:
        pass
