from typing import List, Optional

from pydantic import BaseModel
from xxhash import xxh64

from deputydev_core.services.chunking.dataclass.main import ChunkMetadata


class ChunkSourceDetails(BaseModel):
    file_path: str
    file_hash: Optional[str] = None
    start_line: int
    end_line: int



class ChunkInfo(BaseModel):
    """
    Information about a chunk of code.

    Attributes:
        content (str): The content of the chunk.
        start (int): The starting line number of the chunk.
        end (int): The ending line number of the chunk.
        source (str): The source file of the chunk.
    """

    content: str
    embedding: Optional[List[float]] = None
    source_details: ChunkSourceDetails
    metadata: Optional[ChunkMetadata] = None
    search_score: Optional[float] = 0  # vector search score

    def __hash__(self) -> int:
        return hash(self.content_hash)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ChunkInfo):
            return False
        return self.content_hash == other.content_hash

    def get_chunk_content(self, add_ellipsis: bool = False, add_lines: bool = True):
        """
        Get a content of the chunk.

        Args:
            add_ellipsis (bool, optional): Whether to add ellipsis (...) at the beginning and end of the snippet. Defaults to True.
            add_lines (bool, optional): Whether to prepend line numbers to each line of the snippet. Defaults to True.

        Returns:
            str: The snippet of the chunk.
        """
        snippet = "\n".join(
            (f"{i + self.source_details.start_line}: {line}" if add_lines else line)
            for i, line in enumerate(self.content.splitlines())
        )

        # TODO: Check and remove
        if add_ellipsis:
            if self.source_details.start_line > 0:
                snippet = "...\n" + snippet
            if self.source_details.end_line < self.content.count("\n") + 1:
                snippet = snippet + "\n..."
        return snippet

    def get_meta_data_notes(self, add_class_function_info: bool = True) -> str:
        # prepare hierarchy
        chunk_final_meta_data = ""
        if not self.metadata:
            return chunk_final_meta_data
        if add_class_function_info and self.metadata.all_classes:
            chunk_final_meta_data += (
                f"\n Below classes may use the imports in this snippet: \n {self.metadata.all_classes}"
            )

        if add_class_function_info and self.metadata.all_functions:
            chunk_final_meta_data += (
                f"\n Below functions may use the imports in this snippet: \n {self.metadata.all_functions}"
            )

        chunk_final_meta_data += f"\n File path: {self.source_details.file_path}"
        hierarchy_data: List[str] = []
        hierarchy_seperator = "\t"

        for idx, hierarchy in enumerate(self.metadata.hierarchy):
            if hierarchy.is_breakable_node:
                break
            indent = hierarchy_seperator * idx
            hierarchy_data.append(f"{indent}{hierarchy.type}  {hierarchy.value}")
            hierarchy_data.append(f"{indent}{hierarchy_seperator}...")  # Add ellipsis at current indent level
        if hierarchy_data:
            chunk_final_meta_data += "\n Snippet hierarchy represented in pseudo code format: \n"
            chunk_final_meta_data += "\n".join(hierarchy_data)
            chunk_final_meta_data += "\n"
        return chunk_final_meta_data

    def get_chunk_content_with_meta_data(
        self,
        add_ellipsis: bool = False,
        add_lines: bool = True,
        add_class_function_info: bool = True,
    ) -> str:
        chunk_content = self.get_chunk_content(add_ellipsis=add_ellipsis, add_lines=add_lines)

        meta_data = self.get_meta_data_notes(add_class_function_info=add_class_function_info)
        if meta_data:
            return f"<meta_data>{meta_data}\n</meta_data>\n<code>\n{chunk_content}\n</code>"
        else:
            return chunk_content

    @property
    def content_hash(self) -> str:
        """
        Returns the hash of the chunk content.

        Returns:
            str: The hash of the chunk content.
        """
        return xxh64(self.content.encode()).hexdigest()

    @property
    def denotation(self) -> str:
        """
        Returns the denotation of the source chunk.

        Returns:
            str: The denotation of the source chunk in the format "{source}:{start}-{end}".
        """
        return f"{self.source_details.file_path}:{self.source_details.start_line}-{self.source_details.end_line}"

    def get_xml(self) -> str:
        return f"""<chunk source="{self.denotation}">\n{self.get_chunk_content_with_meta_data(add_class_function_info=True, add_lines=True)}\n</chunk>"""
