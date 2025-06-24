import os
import re
from deputydev_core.models.dto.summarization_dto import FileType
from deputydev_core.utils.constants.constants import CODE_EXTENSIONS, TEXT_EXTENSIONS, CONFIG_EXTENSIONS, BINARY_EXTENSIONS, IGNORED_PATHS


class FileTypeDetector:
    """Lightweight file type detector using centralized constants."""
    
    @classmethod
    def should_ignore_file(cls, file_path: str) -> bool:
        """Check if file should be ignored."""
        path_parts = file_path.split(os.sep)
        if any(ignored in path_parts for ignored in IGNORED_PATHS):
            return True
        ext = os.path.splitext(file_path)[1].lower()
        return ext in BINARY_EXTENSIONS
    
    @classmethod
    def detect_file_type(cls, file_path: str, content_sample: str = "") -> FileType:
        """Detect file type from extension."""
        ext = os.path.splitext(file_path)[1].lower()
        filename = os.path.basename(file_path).lower()
        
        if ext in CODE_EXTENSIONS or filename in ['dockerfile', 'makefile']:
            return FileType.CODE
        elif ext in TEXT_EXTENSIONS:
            return FileType.TEXT
        elif ext in CONFIG_EXTENSIONS or filename.startswith('.env'):
            return FileType.CONFIG
        
        # Simple content-based detection
        if content_sample:
            if re.search(r'\b(class|def|function|import)\b', content_sample):
                return FileType.CODE
            elif re.search(r'^[\w-]+\s*[:=]', content_sample, re.MULTILINE):
                return FileType.CONFIG
                
        return FileType.UNKNOWN