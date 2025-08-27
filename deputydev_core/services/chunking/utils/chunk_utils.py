from typing import List, Set, Tuple

from deputydev_core.services.chunking.dataclass.main import ChunkMetadataHierachyObject, NeoSpan


def get_line_number(index: int, source_code: bytes) -> int:
    """
    Gets the line number corresponding to a given character index in the source code.

    Args:
        index (int): The character index (0-based).
        source_code (bytes): The source code as bytes.

    Returns:
        int: The line number (1-indexed) where the character index is located.

    Example:
        >>> code = b"def hello():\n    print('Hello, world!')"
        >>> get_line_number(13, code)
        2
    
    Note:
        If the index is beyond the end of the source code, returns the last line number.
        If the source code is empty, returns 1.
    """
    if not source_code:
        return 1
    
    if index <= 0:
        return 1
    
    # Convert bytes to string for processing
    text = source_code.decode('utf-8')
    
    # Count newlines up to the given index
    line_number = 1
    for i, char in enumerate(text):
        if i >= index:
            break
        if char == '\n':
            line_number += 1
    
    return line_number


def non_whitespace_len(s: str) -> int:
    """
    Calculates the length of a string excluding whitespace characters.
    
    This is more efficient than using regex substitution for counting
    non-whitespace characters.

    Args:
        s (str): The input string.

    Returns:
        int: The length of the string excluding whitespace characters.
        
    Example:
        >>> non_whitespace_len("hello world\\n\\t")
        10
    """
    return sum(1 for char in s if not char.isspace())


def get_chunk_first_char(current_chunk: NeoSpan, source_code: bytes) -> str:
    stripped_contents = current_chunk.extract_lines(source_code.decode("utf-8")).strip()
    first_char = stripped_contents[0] if stripped_contents else ""
    return first_char


def get_current_chunk_length(chunk: NeoSpan, source_code: bytes) -> int:
    if not chunk:
        return 0
    return len(chunk.extract_lines(source_code.decode("utf-8")))


def supported_new_chunk_language(language: str) -> bool:
    return language in [
        "python",
        "javascript",
        "typescript",
        "tsx",
        "java",
        "ruby",
        "kotlin",
    ]


def deduplicate_hierarchy(hierarchy_list: List[ChunkMetadataHierachyObject]) -> List[ChunkMetadataHierachyObject]:
    """Removes duplicate dictionaries from the hierarchy list while preserving order."""
    seen: Set[Tuple[str, str]] = set()
    deduped: List[ChunkMetadataHierachyObject] = []
    for _item in hierarchy_list:
        item_tuple = (
            _item.type,
            _item.value,
        )  # Sort items to ensure consistent comparison
        if item_tuple not in seen:
            seen.add(item_tuple)
            deduped.append(_item)
    return deduped
