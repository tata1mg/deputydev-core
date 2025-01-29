import copy
import re
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple, Union

import tree_sitter_javascript
from tree_sitter import Language, Node, Parser
from tree_sitter_languages import get_parser as tree_sitter_get_parser

from utils.constants import ALL_EXTENSIONS
from models.chunk_meta_data import (
    ChunkMetadata,
    ChunkMetadataHierachyObject,
    ChunkNodeType,
)
from utils.tiktoken_operations import TikToken
from models.chunk_info import ChunkInfo, ChunkSourceDetails
from utils.config_manager import ConfigManager

CHARACTER_SIZE = ConfigManager.configs["CHUNKING"]["CHARACTER_SIZE"]


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


@dataclass
class NeoSpan:
    """
    Represents a slice of a string.

    Attributes:
        start (int): The starting index of the span.
        end (int): The ending index of the span.
    """

    start: Tuple[int, int] = (0, 0)
    end: Tuple[int, int] = (0, 0)
    metadata: ChunkMetadata = ChunkMetadata(
        hierarchy=[],
        dechunk=False,
        import_only_chunk=False,
        all_functions=[],
        all_classes=[],
    )

    # Example value for metadata

    # {
    #     "hierarchy": [{"type": "class", "value": "a"}, {"type": "function", "value": "fun1"},
    #                  {"type": "function", "value": "fun2"}],
    #     "dechunk": False,
    #     "import_only_chunk": a,
    #     "all_functions": [],  # used to get all functions if a chunk is import only chunk
    #     "all_classes": []  # used to get all classes if a chunk is import only chunk
    # }

    def extract_lines(self, source_code: str) -> str:
        """
        Extracts the corresponding substring of string source_code by lines.
        """
        return "\n".join(source_code.splitlines()[self.start[0]: self.end[0] + 1])

    def __add__(self, other: "NeoSpan") -> "NeoSpan":
        """
        Concatenates two NeoSpan
        """
        final_start = self.start if self.start else other.start
        final_end = other.end if other.end else self.end
        final_metadata = self.__combine_meta_data(other.metadata)
        return NeoSpan(
            final_start,
            final_end,
            metadata=final_metadata,
        )

    def __combine_meta_data(self, other_meta_data: ChunkMetadata) -> ChunkMetadata:
        """
        Combines metadata from two NeoSpan objects.
        Returns a new metadata dictionary instead of modifying in place.
        """

        def deduplicate_hierarchy(hierarchy_list: List[ChunkMetadataHierachyObject]):
            """Removes duplicate dictionaries from the hierarchy list while preserving order."""
            seen: Set[Tuple[str, str]] = set()
            deduped: List[ChunkMetadataHierachyObject] = []
            for _item in hierarchy_list:
                item_tuple = (_item.type.value, _item.value)  # Sort items to ensure consistent comparison
                if item_tuple not in seen:
                    seen.add(item_tuple)
                    deduped.append(_item)
            return deduped

        combined_hierarchy = self.metadata.hierarchy + other_meta_data.hierarchy
        return ChunkMetadata(
            hierarchy=deduplicate_hierarchy(combined_hierarchy),
            dechunk=self.metadata.dechunk and other_meta_data.dechunk,
            import_only_chunk=self.metadata.import_only_chunk or other_meta_data.import_only_chunk,
            all_functions=list(set(self.metadata.all_functions + other_meta_data.all_functions)),
            all_classes=list(set(self.metadata.all_classes + other_meta_data.all_classes)),
        )

    def __len__(self) -> int:
        """
        Computes the length of lines in the NeoSpan
        """
        return self.end[0] - self.start[0] + 1


@dataclass
class Span:
    """
    Represents a slice of a string.

    Attributes:
        start (int): The starting index of the span.
        end (int): The ending index of the span.
    """

    start: int = 0
    end: int = 0
    metadata: ChunkMetadata = ChunkMetadata(
        hierarchy=[],
        dechunk=False,
        import_only_chunk=False,
        all_functions=[],
        all_classes=[],
    )

    def extract(self, s: bytes) -> str:
        """
        Extracts the corresponding substring of string s.

        Args:
            s (bytes): The code bytes.

        Returns:
            str: The extracted substring.
        """
        return s[self.start: self.end]

    def extract_lines(self, s: str) -> str:
        """
        Extracts the corresponding substring of string s by lines.

        Args:
            s (str): The input string.

        Returns:
            str: The extracted substring.
        """
        return "\n".join(s.splitlines()[self.start: self.end + 1])

    def __add__(self, other: Union["Span", int]) -> "Span":
        """
        Concatenates two spans or adds an integer to the span.

        Args:
            other (Union[Span, int]): The other span to concatenate or the integer to add.

        Returns:
            Span: The concatenated span.

        Raises:
            NotImplementedError: If the type of 'other' is not supported.
        """
        if isinstance(other, int):
            return Span(self.start + other, self.end + other)
        elif isinstance(other, Span):
            return Span(self.start, other.end)
        else:
            raise NotImplementedError("Unsupported type for 'other'. Must be Span or int.")

    def __len__(self) -> int:
        """
        Computes the length of the span.

        Returns:
            int: The length of the span.
        """
        return self.end - self.start + 1


def is_node_breakable(node: Node) -> bool:
    return node.type in ("function_definition", "class_definition", "decorated_definition")


def extract_name(node) -> Optional[str]:
    """
    Recursively extract the name from a node, handling different possible structures
    """
    # Direct identifier check
    if node.type == "identifier":
        return node.text.decode("utf-8")

    # Search in direct children for an identifier
    for child in node.children:
        if child.type == "identifier":
            return child.text.decode("utf-8")

    # Recursive search for nested definitions
    for child in node.children:
        # Check for nested class or function definitions
        if child.type in ["class_definition", "function_definition"]:
            name = extract_name(child)
            if name:
                return name

    return None


def chunk_node_with_meta_data(
        node: Node,
        max_chars: int,
        source_code: bytes,
        all_classes: List[str],
        all_functions: List[str],
        hierarchy: Optional[List[ChunkMetadataHierachyObject]] = None,
        pending_decorators: Optional[List[NeoSpan]] = None,
) -> list[NeoSpan]:
    """
    Chunk node code while maintaining full parent class and function metadata.
    Properly handles decorators by associating them with their respective class/function definitions.
    """
    if hierarchy is None:
        hierarchy = []

    if pending_decorators is None:
        pending_decorators = []

    chunks: list[NeoSpan] = []
    current_chunk: Optional[NeoSpan] = None
    node_children = node.children

    # Handle decorators for class or function definitions
    def create_chunk_with_decorators(start_point, end_point, decorators=None, current_node=None):
        if decorators:
            # Start from the first decorator
            actual_start = decorators[0].start
        else:
            actual_start = start_point

        return NeoSpan(
            actual_start,
            end_point,
            metadata=ChunkMetadata(
                hierarchy=copy.deepcopy(hierarchy),
                dechunk=not is_node_breakable(current_node),
                import_only_chunk=not hierarchy and not is_node_breakable(current_node),
                all_functions=[],
                all_classes=[],
            ),
        )

    # Determine if the current node is a class or function
    if node.type == "class_definition":
        class_name_node = next((child for child in node.children if child.type == "identifier"), None)
        class_name = class_name_node.text.decode("utf-8") if class_name_node else "UnknownClass"
        hierarchy.append(ChunkMetadataHierachyObject(type=ChunkNodeType.CLASS, value=class_name))
        all_classes.append(class_name)

        # If this is a class definition and we have pending decorators, create a chunk including them
        if pending_decorators:
            current_chunk = create_chunk_with_decorators(node.start_point, node.end_point, pending_decorators, node)
            pending_decorators.clear()

    elif node.type == "function_definition":
        func_name_node = next((child for child in node.children if child.type == "identifier"), None)
        func_name = func_name_node.text.decode("utf-8") if func_name_node else "UnknownFunction"
        hierarchy.append(ChunkMetadataHierachyObject(type=ChunkNodeType.FUNCTION, value=func_name))
        all_functions.append(func_name)

        # If this is a function definition and we have pending decorators, create a chunk including them
        if pending_decorators:
            current_chunk = create_chunk_with_decorators(node.start_point, node.end_point, pending_decorators, node)
            pending_decorators.clear()

    for child in node_children:
        if child.type in ["class_definition"]:
            class_name = extract_name(child)
            if class_name:
                all_classes.append(class_name)

        if child.type in ["function_definition", "decorated_definition"]:
            func_name = extract_name(child)
            if func_name:
                all_functions.append(func_name)

        if child.type == "decorator":
            # Store the decorator for the next class or function definition
            pending_decorators.append(NeoSpan(child.start_point, child.end_point))
            continue

        elif child.end_byte - child.start_byte > max_chars:
            # Finalize the current chunk
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = None
            # Recursively process large nodes
            chunks.extend(
                chunk_node_with_meta_data(
                    child,
                    max_chars,
                    source_code,
                    all_classes,
                    all_functions,
                    hierarchy,
                    pending_decorators,
                )
            )

        elif (
                child.end_byte - child.start_byte + (len(current_chunk) if current_chunk else 0) > max_chars
        ) or is_node_breakable(child):
            # Split the current chunk if it exceeds the maximum size
            if current_chunk:
                chunks.append(current_chunk)

            current_chunk = create_chunk_with_decorators(child.start_point, child.end_point, current_node=child)

        else:
            # Append the current child to the chunk
            if current_chunk:
                current_chunk += create_chunk_with_decorators(child.start_point, child.end_point, current_node=child)
            else:
                current_chunk = create_chunk_with_decorators(child.start_point, child.end_point, current_node=child)

    # Finalize the last chunk
    if current_chunk:
        chunks.append(current_chunk)
    if is_node_breakable(node) and hierarchy and len(hierarchy) > 0:
        hierarchy.pop()
    return chunks


def dechunk(chunks: List[NeoSpan], coalesce: int, source_code: bytes) -> list[NeoSpan]:
    """
    Combine chunks intelligently, ensuring chunks with `dechunk` set to `False` are not merged
    with previous chunks, and chunks are split if their combined size exceeds `coalesce`.

    Args:
        chunks (list): List of Span objects to process.
        coalesce (int): Maximum character length of combined chunks before splitting.
        source_code (bytes): The source code bytes used for content extraction.

    Returns:
        list: List of combined and properly dechunked Span objects.
    """
    if len(chunks) == 0:
        return []
    elif len(chunks) == 1:
        return chunks

    new_chunks = []
    current_chunk = chunks[0]

    for idx, chunk in enumerate(chunks[1:]):
        # Do not combine if the chunk's metadata[0]["dechunk"] is False
        if chunk.metadata.dechunk is False:
            if current_chunk and len(current_chunk) > 0:
                new_chunks.append(current_chunk)
            current_chunk = chunk
            continue

        # Combine the current chunk
        if current_chunk:
            current_chunk += chunk
        else:
            current_chunk = chunk

        # Extract and process the combined content
        stripped_contents = current_chunk.extract_lines(source_code.decode("utf-8")).strip()
        first_char = stripped_contents[0] if stripped_contents else ""

        # Handle closing brackets and parentheses
        if first_char in [")", "}", "]"] and new_chunks:
            new_chunks[-1] += chunk
            current_chunk = None
        # Split based on size or newline condition
        elif non_whitespace_len(current_chunk.extract_lines(source_code.decode("utf-8"))) > coalesce:
            new_chunks.append(current_chunk)
            current_chunk = None

    # Append any remaining chunk
    if current_chunk and len(current_chunk) > 0:
        new_chunks.append(current_chunk)

    return new_chunks


def chunk_code_with_metadata(
        tree,
        source_code: bytes,
        MAX_CHARS=CHARACTER_SIZE,
        coalesce=100,
) -> list[NeoSpan]:
    """
    Chunk the AST tree based on maximum characters and coalesce size.

    Args:
        tree: The AST tree.
        source_code (bytes): The source code bytes.
        MAX_CHARS (int): Maximum characters per chunk.
        coalesce (int): Coalesce size.

    Returns:
        list[Span]: List of chunks.
    """
    # Create initial chunks with metadata
    all_classes: List[str] = []
    all_functions: List[str] = []
    chunks = chunk_node_with_meta_data(
        tree.root_node,
        max_chars=MAX_CHARS,
        source_code=source_code,
        all_functions=all_functions,
        all_classes=all_classes,
    )
    for chunk in chunks:
        if chunk.metadata.import_only_chunk:
            chunk.metadata.all_classes = list(set(all_classes))
            chunk.metadata.all_functions = list(set(all_functions))

    new_chunks = dechunk(chunks, coalesce=coalesce, source_code=source_code)
    return new_chunks


def chunk_code(
        tree,
        source_code: bytes,
        MAX_CHARS=CHARACTER_SIZE,
        coalesce=100,
) -> List[Span]:
    """
    Chunk the AST tree based on maximum characters and coalesce size.

    Args:
        tree: The AST tree.
        source_code (bytes): The source code bytes.
        MAX_CHARS (int): Maximum characters per chunk.
        coalesce (int): Coalesce size.

    Returns:
        list[Span]: List of chunks.
    """

    # 1. Recursively form chunks
    def chunk_node(node: Node) -> list[Span]:
        chunks: list[Span] = []
        current_chunk: Span = Span(node.start_byte, node.start_byte)
        node_children = node.children
        for child in node_children:
            if child.end_byte - child.start_byte > MAX_CHARS:
                chunks.append(current_chunk)
                current_chunk = Span(child.end_byte, child.end_byte)
                chunks.extend(chunk_node(child))
            elif child.end_byte - child.start_byte + len(current_chunk) > MAX_CHARS:
                chunks.append(current_chunk)
                current_chunk = Span(child.start_byte, child.end_byte)
            else:
                current_chunk += Span(child.start_byte, child.end_byte)
        chunks.append(current_chunk)
        return chunks

    chunks = chunk_node(tree.root_node)

    # 2. Filling in the gaps
    if len(chunks) == 0:
        return []
    if len(chunks) < 2:
        end = get_line_number(chunks[0].end, source_code)
        return [Span(0, end)]
    for i in range(len(chunks) - 1):
        chunks[i].end = chunks[i + 1].start  # sets the last byte of chunk to start byte of suceessiding chunk
    chunks[
        -1
    ].end = tree.root_node.end_byte  # sets the last byte of chunk to start byte of suceessiding chunk for last chunk

    # 3. Combining small chunks with bigger ones
    new_chunks = []
    current_chunk = Span(0, 0)
    for chunk in chunks:
        current_chunk += chunk
        # if the current chunk starts with a closing parenthesis, bracket, or brace, we coalesce it with the previous chunk
        stripped_contents = current_chunk.extract(source_code.decode("utf-8")).strip()
        first_char = stripped_contents[0] if stripped_contents else ""
        if first_char in [")", "}", "]"] and new_chunks:
            new_chunks[-1] += chunk
            current_chunk = Span(chunk.end, chunk.end)
        # if the current chunk is too large, create a new chunk, otherwise, combine the chunks
        elif non_whitespace_len(
                current_chunk.extract(source_code.decode("utf-8"))
        ) > coalesce and "\n" in current_chunk.extract(source_code.decode("utf-8")):
            new_chunks.append(current_chunk)
            current_chunk = Span(chunk.end, chunk.end)
    if len(current_chunk) > 0:
        new_chunks.append(current_chunk)

    # 4. Changing line numbers
    first_chunk = new_chunks[0]
    line_chunks = [Span(0, get_line_number(first_chunk.end, source_code))]
    for chunk in new_chunks[1:]:
        start_line = get_line_number(chunk.start, source_code) + 1
        end_line = get_line_number(chunk.end, source_code)
        line_chunks.append(Span(start_line, max(start_line, end_line)))

    # 5. Eliminating empty chunks
    line_chunks = [chunk for chunk in line_chunks if len(chunk) > 0]

    # 6. Coalescing last chunk if it's too small
    if len(line_chunks) > 1 and len(line_chunks[-1]) < coalesce:
        line_chunks[-2] += line_chunks[-1]
        line_chunks.pop()

    return line_chunks


def chunk_content(content: str, line_count: int = 30, overlap: int = 15) -> List[Tuple[int, int, str]]:
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


def supported_new_chunk_language(language):
    return language in ["python"]


def chunk_source(
        content: str,
        path: str,
        file_hash: Optional[str] = None,
        MAX_CHARS=CHARACTER_SIZE,
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
        is_eligible_for_new_chunking = use_new_chunking and supported_new_chunk_language(language)
        if is_eligible_for_new_chunking:
            all_current_file_chunks = chunk_code_with_metadata(
                tree, content.encode("utf-8"), MAX_CHARS=MAX_CHARS, coalesce=coalesce
            )
        else:
            all_current_file_chunks = chunk_code(tree, content.encode("utf-8"), MAX_CHARS=MAX_CHARS)
        already_visited_chunk: Set[str] = set()
        file_contents = content.splitlines()
        for chunk in all_current_file_chunks:
            if is_eligible_for_new_chunking:
                new_chunk_info = ChunkInfo(
                    content="\n".join(file_contents[chunk.start[0]: chunk.end[0] + 1]),
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
                    content="\n".join(file_contents[chunk.start: chunk.end + 1]),
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
    except Exception as e:
        print(f"Error chunking file: {path} with error {str(e)}")
        return []


def chunk_pr_diff(diff_content: str, max_lines: int = 200, overlap: int = 15) -> list[str]:
    file_pattern = re.compile(r"^a/.+ b/.+$")  # Our files start with a/b
    tiktoken_client = TikToken()

    pr_diff_token_count = tiktoken_client.count(diff_content, ConfigManager.configs["EMBEDDING"]["MODEL"])
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
