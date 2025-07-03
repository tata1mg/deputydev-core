from pathlib import Path

from deputydev_core.models.dto.summarization_dto import FileSummaryResponse
from deputydev_core.utils.constants.constants import DEFAULT_MAX_SUMMARY_LINES, LARGE_FILE_THRESHOLD, MAX_FILE_SIZE
from deputydev_core.utils.file_type_detector import FileTypeDetector

from .file_summarizer import FileSummarizer


class FileSummarizationService:
    """Lightweight file summarization service."""

    @classmethod
    async def summarize_file(
        cls,
        file_path: str,
        repo_path: str = "",
        max_lines: int = DEFAULT_MAX_SUMMARY_LINES,
        include_line_numbers: bool = True,
    ) -> FileSummaryResponse:
        """Summarize a file with minimal overhead."""
        full_path = Path(repo_path) / file_path if repo_path else Path(file_path)

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {full_path}")

        if FileTypeDetector.should_ignore_file(file_path):
            raise ValueError(f"File type not supported: {file_path}")

        if full_path.stat().st_size > MAX_FILE_SIZE:
            raise ValueError("File too large for summarization")

        # Read file with encoding fallback
        content = cls._read_file_content(full_path)

        # Detect type and summarize
        file_type = FileTypeDetector.detect_file_type(file_path, content[:1000])
        summarizer = FileSummarizer(max_lines, include_line_numbers)

        return summarizer.summarize(file_path, content, file_type)

    @classmethod
    def should_summarize(cls, total_lines: int) -> bool:
        """Check if file should be summarized based on size and request."""
        return total_lines > LARGE_FILE_THRESHOLD

    @classmethod
    def _read_file_content(cls, file_path: Path) -> str:
        """Read file content with encoding fallback."""
        try:
            with file_path.open("r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            with file_path.open("r", encoding="latin-1") as f:
                return f.read()
