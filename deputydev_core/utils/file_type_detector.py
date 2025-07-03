import re
from pathlib import Path
from typing import Optional

from deputydev_core.models.dto.summarization_dto import FileType
from deputydev_core.utils.constants.constants import (
    ALL_EXTENSIONS,
    BINARY_EXTENSIONS,
    CODE_EXTENSIONS,
    CONFIG_EXTENSIONS,
    IGNORED_PATHS,
    SPECIAL_FILENAME_MAP,
    TEXT_EXTENSIONS,
)


class FileTypeDetector:
    """Lightweight file type detector using centralized constants."""

    @classmethod
    def should_ignore_file(cls, file_path: str) -> bool:
        """Check if file should be ignored."""
        path = Path(file_path)
        path_parts = path.parts
        if any(ignored in path_parts for ignored in IGNORED_PATHS):
            return True
        ext = path.suffix.lower()
        return ext in BINARY_EXTENSIONS

    @classmethod
    def get_language_from_file(cls, file_path: str) -> Optional[str]:
        """Get tree-sitter language name from file extension."""
        if not file_path:
            return None

        ext = file_path.lower().split(".")[-1] if "." in file_path else ""
        filename = file_path.lower().split("/")[-1] if "/" in file_path else file_path.lower()

        # Check special filenames first
        if filename in SPECIAL_FILENAME_MAP:
            return SPECIAL_FILENAME_MAP[filename]

        return ALL_EXTENSIONS.get(ext)

    @classmethod
    def detect_file_type(cls, file_path: str, content_sample: str = "") -> FileType:
        """Detect file type from extension."""
        path = Path(file_path)
        ext = path.suffix.lower()
        filename = path.name.lower()

        if ext in CODE_EXTENSIONS or filename in ["dockerfile", "makefile"]:
            return FileType.CODE
        elif ext in TEXT_EXTENSIONS:
            return FileType.TEXT
        elif ext in CONFIG_EXTENSIONS or filename.startswith(".env"):
            return FileType.CONFIG

        # Simple content-based detection
        if content_sample:
            if re.search(r"\b(class|def|function|import)\b", content_sample):
                return FileType.CODE
            elif re.search(r"^[\w-]+\s*[:=]", content_sample, re.MULTILINE):
                return FileType.CONFIG

        return FileType.UNKNOWN
