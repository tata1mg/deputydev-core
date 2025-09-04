# llm_handler_lib/interfaces/config_interface.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ConfigInterface(ABC):
    """
    Unified configuration interface that surfaces:
      - LLM-related config (retry, model map)
      - Provider-specific config (openai/anthropic/gemini/openrouter/aws)
      - File upload config (s3, paths)
    """

    # --- LLM-level config ---
    @abstractmethod
    def get_llm_max_retry(self) -> int:
        """Maximum retry count for LLM calls."""
        pass

    @abstractmethod
    def get_llm_models_config(self) -> Dict[str, Any]:
        """Arbitrary LLM models configuration map."""
        pass

    # --- Provider-specific config (Optional dictionaries) ---
    @abstractmethod
    def get_openai_config(self) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_anthropic_config(self) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_gemini_config(self) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_openrouter_config(self) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_aws_config(self) -> Optional[Dict[str, Any]]:
        pass

    # --- File upload / S3 config ---
    @abstractmethod
    def get_s3_config(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_file_upload_paths(self) -> Dict[str, str]:
        pass
