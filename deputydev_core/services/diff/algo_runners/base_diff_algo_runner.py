from abc import ABC, abstractmethod
from typing import Any

from deputydev_core.services.diff.dataclasses.main import FileDiffApplicationResponse


class BaseDiffAlgoRunner(ABC):
    """
    Base class for diff algorithm runners.
    """

    @classmethod
    @abstractmethod
    async def apply_diff(
        cls,
        file_path: str,
        repo_path: str,
        current_content: str,
        diff_data: Any,
    ) -> FileDiffApplicationResponse:
        """
        Apply the diff to the file.
        """
        raise NotImplementedError(
            "apply_diff method must be implemented in the child class"
        )
