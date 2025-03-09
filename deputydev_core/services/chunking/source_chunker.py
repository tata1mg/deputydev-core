import re
from typing import List, Optional, Set, Tuple

from deputydev_core.services.chunking.strategies.chunk_strategy_factory import \
    ChunkingStrategyFactory
from deputydev_core.services.chunking.utils.chunk_utils import (
    get_parser, supported_new_chunk_language)
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.config_manager import ConfigManager
from deputydev_core.utils.constants.constants import ALL_EXTENSIONS

from ..tiktoken import TikToken
from .chunk_info import ChunkInfo, ChunkSourceDetails


def chunk_content(
    content: str, line_count: int = 30, overlap: int = 15
) -> List[Tuple[int, int, str]]:
    """
    Default chunking of content based on line count and overlap.

    Args:
        content (str): The source content string.
        line_count (int): Number of lines per chunk.
        overlap (int): Overlap between chunks.

    Returns:
        List[str]: List of chunks.
    """
    if overlap >= line_count:
        raise ValueError("Overlap should be smaller than line_count.")
    lines = content.split("\n")
    total_lines = len(lines)
    chunks: List[Tuple[int, int, str]] = []

    start = 0
    while start < total_lines:
        end = min(start + line_count, total_lines)
        chunk = "\n".join(lines[start:end])
        chunks.append((start, end, chunk))
        start += line_count - overlap

    return chunks


def chunk_source(
    content: str,
    path: str,
    file_hash: Optional[str] = None,
    MAX_CHARS=None,
    coalesce=80,
    nl_desc=False,
    use_new_chunking=False,
) -> list[ChunkInfo]:
    """
    Chunk the given content into smaller segments.

    Args:
        content (str): The content to be chunked.
        path (str): The file path of the content.
        MAX_CHARS (int, optional): Maximum characters per chunk. Defaults to 1200.
        coalesce (int, optional): Coalesce parameter for chunking. Defaults to 80.
        use_new_chunking (bool): Use new chunking strategy

    Returns:
        List[ChunkInfo]: A list of ChunkInfo objects representing the chunks of content.
    """
    if not MAX_CHARS:
        MAX_CHARS = ConfigManager.configs["CHUNKING"]["CHARACTER_SIZE"]

    ext = path.split(".")[-1]
    if ext in ALL_EXTENSIONS:
        language = ALL_EXTENSIONS[ext]
    else:
        # Fallback to default chunking if tree_sitter fails
        line_count = 50
        overlap = 0
        get_chunks = chunk_content(content, line_count, overlap)
        chunks: List[ChunkInfo] = []
        for start, end, chunk_snippet in get_chunks:
            new_chunk_info = ChunkInfo(
                content=chunk_snippet,
                source_details=ChunkSourceDetails(
                    file_path=path,
                    # TODO: Check chunk index
                    start_line=start + 1,
                    end_line=end + 1,
                    file_hash=file_hash,
                ),
            )
            chunks.append(new_chunk_info)
        return chunks
    try:
        final_chunks: List[ChunkInfo] = []
        parser = get_parser(language)
        tree = parser.parse(content.encode("utf-8"))
        is_eligible_for_new_chunking = (
            use_new_chunking and supported_new_chunk_language(language)
        )
        strategy_chunker = ChunkingStrategyFactory.create_strategy(
            language=language, is_eligible_for_new_chunking=is_eligible_for_new_chunking
        )
        all_current_file_chunks = strategy_chunker.chunk_code(
            tree=tree,
            content=content.encode("utf-8"),
            max_chars=MAX_CHARS,
            coalesce=coalesce,
            language=language,
        )

        already_visited_chunk: Set[str] = set()
        file_contents = content.splitlines()
        for chunk in all_current_file_chunks:
            if is_eligible_for_new_chunking:
                new_chunk_info = ChunkInfo(
                    content="\n".join(file_contents[chunk.start[0] : chunk.end[0] + 1]),
                    source_details=ChunkSourceDetails(
                        file_path=path,
                        start_line=chunk.start[0] + 1,
                        end_line=chunk.end[0] + 1,
                        file_hash=file_hash,
                    ),
                    metadata=chunk.metadata,
                )
            else:
                new_chunk_info = ChunkInfo(
                    content="\n".join(file_contents[chunk.start : chunk.end + 1]),
                    source_details=ChunkSourceDetails(
                        file_path=path,
                        start_line=chunk.start + 1,
                        end_line=chunk.end + 1,
                        file_hash=file_hash,
                    ),
                    metadata=chunk.metadata,
                )
            # remove duplicate chunks
            if new_chunk_info.denotation not in already_visited_chunk:
                final_chunks.append(new_chunk_info)
                already_visited_chunk.add(new_chunk_info.denotation)

        return final_chunks
    except Exception:
        AppLogger.log_error(f"Error chunking file: {path}")
        return []


def chunk_pr_diff(
    diff_content: str, max_lines: int = 200, overlap: int = 15
) -> list[str]:
    file_pattern = re.compile(r"^a/.+ b/.+$")  # Our files start with a/b
    tiktoken_client = TikToken()

    pr_diff_token_count = tiktoken_client.count(
        diff_content, ConfigManager.configs["EMBEDDING"]["MODEL"]
    )
    embeeding_token_limit = ConfigManager.configs["EMBEDDING"]["TOKEN_LIMIT"]

    if pr_diff_token_count < embeeding_token_limit:
        return [diff_content]

    #  Only make diff chunks incase limit exceeds 8191 token
    lines = diff_content.split("\n")
    chunks = []
    current_chunk = []
    line_count = 0
    file_header = None  # Maintins file path of a chunk

    for line in lines:
        if file_pattern.match(line):
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            file_header = line
            current_chunk = [file_header]
            line_count = 1
        else:
            current_chunk.append(line)
            line_count += 1

            if line_count >= max_lines:
                chunks.append("\n".join(current_chunk))
                overlap_lines = current_chunk[-overlap:]
                current_chunk = [file_header] if file_header else []
                current_chunk.extend(overlap_lines)
                line_count = len(current_chunk)

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks
