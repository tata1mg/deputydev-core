from typing import List

from tree_sitter import Node

from deputydev_core.services.chunking.dataclass.main import Span
from deputydev_core.services.chunking.utils.chunk_utils import (
    get_line_number, non_whitespace_len)

from .base_chunker import BaseChunker


class LegacyChunker(BaseChunker):
    def chunk_code(
        self, tree, content: bytes, max_chars, coalesce, language
    ) -> List[Span]:
        """
        Chunk the AST tree based on maximum characters and coalesce size.

        Args:
            tree: The AST tree.
            source_code (bytes): The source code bytes.
            MAX_CHARS (int): Maximum characters per chunk.
            coalesce (int): Coalesce size.
            language

        Returns:
            list[Span]: List of chunks.
        """

        # 1. Recursively form chunks
        def chunk_node(node: Node) -> list[Span]:
            chunks: list[Span] = []
            current_chunk: Span = Span(node.start_byte, node.start_byte)
            node_children = node.children
            for child in node_children:
                if child.end_byte - child.start_byte > max_chars:
                    chunks.append(current_chunk)
                    current_chunk = Span(child.end_byte, child.end_byte)
                    chunks.extend(chunk_node(child))
                elif child.end_byte - child.start_byte + len(current_chunk) > max_chars:
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
            end = get_line_number(chunks[0].end, content)
            return [Span(0, end)]
        for i in range(len(chunks) - 1):
            chunks[i].end = chunks[
                i + 1
            ].start  # sets the last byte of chunk to start byte of suceessiding chunk
        chunks[
            -1
        ].end = (
            tree.root_node.end_byte
        )  # sets the last byte of chunk to start byte of suceessiding chunk for last chunk

        # 3. Combining small chunks with bigger ones
        new_chunks = []
        current_chunk = Span(0, 0)
        for chunk in chunks:
            current_chunk += chunk
            # if the current chunk starts with a closing parenthesis, bracket, or brace, we coalesce it with the previous chunk
            stripped_contents = current_chunk.extract(content.decode("utf-8")).strip()
            first_char = stripped_contents[0] if stripped_contents else ""
            if first_char in [")", "}", "]"] and new_chunks:
                new_chunks[-1] += chunk
                current_chunk = Span(chunk.end, chunk.end)
            # if the current chunk is too large, create a new chunk, otherwise, combine the chunks
            elif non_whitespace_len(
                current_chunk.extract(content.decode("utf-8"))
            ) > coalesce and "\n" in current_chunk.extract(content.decode("utf-8")):
                new_chunks.append(current_chunk)
                current_chunk = Span(chunk.end, chunk.end)
        if len(current_chunk) > 0:
            new_chunks.append(current_chunk)

        # 4. Changing line numbers
        first_chunk = new_chunks[0]
        line_chunks = [Span(0, get_line_number(first_chunk.end, content))]
        for chunk in new_chunks[1:]:
            start_line = get_line_number(chunk.start, content) + 1
            end_line = get_line_number(chunk.end, content)
            line_chunks.append(Span(start_line, max(start_line, end_line)))

        # 5. Eliminating empty chunks
        line_chunks = [chunk for chunk in line_chunks if len(chunk) > 0]

        # 6. Coalescing last chunk if it's too small
        if len(line_chunks) > 1 and len(line_chunks[-1]) < coalesce:
            line_chunks[-2] += line_chunks[-1]
            line_chunks.pop()

        return line_chunks
