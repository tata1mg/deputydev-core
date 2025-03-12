import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set, Tuple, Union

from pydantic import BaseModel


class ChunkNodeType(Enum):
    FUNCTION = "FUNCTION"
    CLASS = "CLASS"


class ChunkMetadataHierachyObject(BaseModel):
    type: str
    value: str
    is_breakable_node: Optional[bool] = False


class ChunkMetadata(BaseModel):
    hierarchy: List[ChunkMetadataHierachyObject]
    dechunk: Optional[bool] = False
    import_only_chunk: Optional[bool] = False
    all_functions: Optional[List[str]] = []
    all_classes: Optional[List[str]] = []
    byte_size: Optional[int] = None


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
    metadata: ChunkMetadata = field(
        default_factory=lambda: ChunkMetadata(
            hierarchy=[],
            dechunk=False,
            import_only_chunk=False,
            all_functions=[],
            all_classes=[],
        )
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
        return "\n".join(source_code.splitlines()[self.start[0] : self.end[0] + 1])

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
                item_tuple = (
                    _item.type,
                    _item.value,
                )  # Sort items to ensure consistent comparison
                if item_tuple not in seen:
                    seen.add(item_tuple)
                    deduped.append(_item)
            return deduped

        combined_hierarchy = self.metadata.hierarchy + other_meta_data.hierarchy
        return ChunkMetadata(
            hierarchy=deduplicate_hierarchy(combined_hierarchy),
            dechunk=self.metadata.dechunk and other_meta_data.dechunk,
            import_only_chunk=self.metadata.import_only_chunk
            or other_meta_data.import_only_chunk,
            all_functions=list(
                set(self.metadata.all_functions + other_meta_data.all_functions)
            ),
            all_classes=list(
                set(self.metadata.all_classes + other_meta_data.all_classes)
            ),
            byte_size=self.metadata.byte_size + other_meta_data.byte_size,
        )

    def get_chunk_first_char(self, source_code: bytes):
        stripped_contents = self.extract_lines(source_code.decode("utf-8")).strip()
        first_char = stripped_contents[0] if stripped_contents else ""
        return first_char

    def __len__(self) -> int:
        """
        Computes the length of lines in the NeoSpan
        """
        return self.end[0] - self.start[0] + 1

    def non_whitespace_len(self, source_code: bytes) -> int:
        """
        Calculates the length of a string excluding whitespace characters.

        Args:
            source_code (str): The input string.

        Returns:
            int: The length of the string excluding whitespace characters.
        """
        code = self.extract_lines(source_code.decode("utf-8"))
        return len(re.sub(r"\s", "", code))


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
    metadata: ChunkMetadata = field(
        default_factory=lambda: ChunkMetadata(
            hierarchy=[],
            dechunk=False,
            import_only_chunk=False,
            all_functions=[],
            all_classes=[],
        )
    )

    def extract(self, s: bytes) -> str:
        """
        Extracts the corresponding substring of string s.

        Args:
            s (bytes): The code bytes.

        Returns:
            str: The extracted substring.
        """
        return s[self.start : self.end]

    def extract_lines(self, s: str) -> str:
        """
        Extracts the corresponding substring of string s by lines.

        Args:
            s (str): The input string.

        Returns:
            str: The extracted substring.
        """
        return "\n".join(s.splitlines()[self.start : self.end + 1])

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
            raise NotImplementedError(
                "Unsupported type for 'other'. Must be Span or int."
            )

    def __len__(self) -> int:
        """
        Computes the length of the span.

        Returns:
            int: The length of the span.
        """
        return self.end - self.start + 1
