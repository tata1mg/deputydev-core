import re
from typing import Tuple, List, Set

import tree_sitter_javascript
from tree_sitter import Language, Parser
from tree_sitter_languages import get_parser as tree_sitter_get_parser

from deputydev_core.services.chunking.dataclass.main import NeoSpan, ChunkMetadataHierachyObject


def get_parser(language: str) -> Parser:
    """
    Returns a parser for the specified language.

    Args:
        language (str): The name of the language.

    Returns:
        Parser: A parser object for the specified language.
    """
    parser = Parser()
    if language == "javascript":
        lang = Language(tree_sitter_javascript.language(), "javascript")
    else:
        return tree_sitter_get_parser(language)

    parser.set_language(lang)
    return parser


def get_line_number(index: int, source_code: bytes) -> int:
    """
    Gets the line number corresponding to a given character index in the source code.

    Args:
        index (int): The character index.
        source_code (str): The source code string.

    Returns:
        int: The line number (1-indexed) where the character index is located.

    Example:
        >>> code = "def hello():\n    print('Hello, world!')"
        >>> get_line_number(13, code)
        2
    """
    total_chars = 0
    line_number = 0
    for line_number, line in enumerate(source_code.splitlines(keepends=True), start=1):
        total_chars += len(line)
        if total_chars > index:
            return line_number - 1
    return line_number


def non_whitespace_len(s: str) -> int:
    """
    Calculates the length of a string excluding whitespace characters.

    Args:
        s (str): The input string.

    Returns:
        int: The length of the string excluding whitespace characters.
    """
    return len(re.sub(r"\s", "", s))


def get_chunk_first_char(current_chunk: NeoSpan, source_code: bytes):
    stripped_contents = current_chunk.extract_lines(source_code.decode("utf-8")).strip()
    first_char = stripped_contents[0] if stripped_contents else ""
    return first_char


def get_current_chunk_length(chunk: NeoSpan, source_code: bytes):
    if not chunk:
        return 0
    return len(chunk.extract_lines(source_code.decode("utf-8")))


def supported_new_chunk_language(language):
    return language in [
        "python",
        "javascript",
        "typescript",
        "tsx",
        "java",
        "ruby",
        "kotlin",
    ]


def deduplicate_hierarchy(hierarchy_list: List[ChunkMetadataHierachyObject]):
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
