from typing import List

from tree_sitter import Node

from deputydev_core.services.chunking.dataclass.main import Span
from deputydev_core.services.chunking.utils.chunk_utils import (
    get_line_number,
    non_whitespace_len,
)

from .base_chunker import BaseChunker


class LegacyChunker(BaseChunker):
    """
    Original implementation of AST-based code chunking.
    
    This chunker processes Abstract Syntax Trees to create logical code chunks
    based on size constraints and semantic boundaries. It aims to preserve
    code structure while respecting maximum chunk sizes.
    """

    def chunk_code(self, tree, content: bytes, max_chars: int, coalesce: int, language: str) -> List[Span]:
        """
        Chunk source code based on AST structure and size constraints.

        Args:
            tree: The parsed AST tree from tree-sitter
            content (bytes): The source code as bytes
            max_chars (int): Maximum characters per initial chunk
            coalesce (int): Target size for coalescing small chunks
            language (str): Programming language identifier

        Returns:
            List[Span]: List of line-based spans representing code chunks
        """
        if not tree or not tree.root_node:
            return []

        # 1: Create initial byte-based chunks from AST traversal
        initial_chunks = self._create_ast_chunks(tree.root_node, max_chars)
        
        if not initial_chunks:
            return []

        # 2: Fill gaps between chunks to ensure complete coverage
        filled_chunks = self._fill_chunk_gaps(initial_chunks, tree.root_node.end_byte)
        
        # 3: Apply coalescing rules to merge small chunks
        coalesced_chunks = self._coalesce_chunks(filled_chunks, content, coalesce)
        
        # 4: Convert byte positions to line numbers
        line_chunks = self._convert_to_line_chunks(coalesced_chunks, content)
        
        # 5: Clean up empty chunks and apply final optimizations
        return self._finalize_chunks(line_chunks, coalesce)

    def _create_ast_chunks(self, root_node: Node, max_chars: int) -> List[Span]:
        """
        Create initial chunks by traversing the AST and grouping nodes.
        
        This uses a depth-first traversal to identify natural breaking points
        in the code structure based on node boundaries.
        """
        
        def traverse_node(node: Node, current_start: int) -> List[Span]:
            """Recursively traverse AST nodes to create logical chunks."""
            node_chunks = []
            chunk_start = current_start
            
            for child in node.children:
                child_size = child.end_byte - child.start_byte
                
                # If child is large, chunk it recursively
                if child_size > max_chars:
                    # Close current chunk if it has content
                    if chunk_start < child.start_byte:
                        node_chunks.append(Span(chunk_start, child.start_byte))
                    
                    # Recursively chunk the large child
                    child_chunks = traverse_node(child, child.start_byte)
                    node_chunks.extend(child_chunks)
                    chunk_start = child.end_byte
                    
                # If adding this child would exceed max_chars, start new chunk
                elif chunk_start + max_chars < child.end_byte:
                    if chunk_start < child.start_byte:
                        node_chunks.append(Span(chunk_start, child.start_byte))
                    chunk_start = child.start_byte
            
            # Add final chunk if there's remaining content
            if chunk_start < node.end_byte:
                node_chunks.append(Span(chunk_start, node.end_byte))
                
            return node_chunks
        
        return traverse_node(root_node, root_node.start_byte)

    def _fill_chunk_gaps(self, chunks: List[Span], end_byte: int) -> List[Span]:
        """
        Ensure complete coverage by filling gaps between chunks.
        
        This prevents loss of code content between chunk boundaries.
        """
        if not chunks:
            return []
        
        filled_chunks = []
        
        # Handle case with single chunk
        if len(chunks) == 1:
            return [Span(0, end_byte)]
        
        # Fill gaps between consecutive chunks
        for i in range(len(chunks) - 1):
            current_chunk = chunks[i]
            next_chunk = chunks[i + 1]
            
            # Extend current chunk to start of next chunk
            filled_chunks.append(Span(current_chunk.start, next_chunk.start))
        
        # Handle the last chunk
        last_chunk = chunks[-1]
        filled_chunks.append(Span(last_chunk.start, end_byte))
        
        return filled_chunks

    def _coalesce_chunks(self, chunks: List[Span], content: bytes, coalesce: int) -> List[Span]:
        """
        Merge small chunks and apply semantic grouping rules.
        
        This improves chunk quality by combining related code sections
        and handling structural elements like closing braces.
        """
        if not chunks:
            return []
        
        coalesced = []
        current_chunk = Span(0, 0)
        
        for chunk in chunks:
            # Try to merge with current chunk
            merged_chunk = self._merge_spans(current_chunk, chunk)
            
            # Check if merged chunk starts with closing delimiter
            if self._starts_with_closing_delimiter(merged_chunk, content) and coalesced:
                # Merge with previous chunk instead
                coalesced[-1] = self._merge_spans(coalesced[-1], chunk)
                current_chunk = Span(chunk.end, chunk.end)
                continue
            
            # Check if merged chunk exceeds coalesce threshold
            merged_content = self._extract_chunk_content(merged_chunk, content)
            if (non_whitespace_len(merged_content) > coalesce and 
                '\n' in merged_content and len(current_chunk) > 0):
                # Finalize current chunk and start new one
                coalesced.append(current_chunk)
                current_chunk = chunk
            else:
                # Continue building current chunk
                current_chunk = merged_chunk
        
        # Add final chunk if it has content
        if len(current_chunk) > 0:
            coalesced.append(current_chunk)
        
        return coalesced

    def _convert_to_line_chunks(self, byte_chunks: List[Span], content: bytes) -> List[Span]:
        """
        Convert byte-based spans to line-based spans.
        
        This provides more user-friendly chunk boundaries aligned with
        source code line structure.
        """
        if not byte_chunks:
            return []
        
        line_chunks = []
        
        for i, chunk in enumerate(byte_chunks):
            if i == 0:
                # First chunk starts at line 0
                start_line = 0
            else:
                # Subsequent chunks start at next line after previous chunk
                start_line = get_line_number(chunk.start, content) + 1
            
            end_line = get_line_number(chunk.end, content)
            
            # Ensure valid line range
            if start_line <= end_line:
                line_chunks.append(Span(start_line, end_line))
        
        return line_chunks

    def _finalize_chunks(self, chunks: List[Span], coalesce: int) -> List[Span]:
        """
        Apply final cleanup and optimization to chunks.
        
        This removes empty chunks and merges very small final chunks
        to improve overall chunk quality.
        """
        # Remove empty chunks
        non_empty_chunks = [chunk for chunk in chunks if len(chunk) > 0]
        
        if len(non_empty_chunks) <= 1:
            return non_empty_chunks
        
        # Merge small final chunk if needed
        if len(non_empty_chunks[-1]) < coalesce:
            # Merge last chunk with second-to-last
            merged_chunk = self._merge_spans(non_empty_chunks[-2], non_empty_chunks[-1])
            return non_empty_chunks[:-2] + [merged_chunk]
        
        return non_empty_chunks

    def _merge_spans(self, span1: Span, span2: Span) -> Span:
        """Merge two spans into a single continuous span."""
        if len(span1) == 0:
            return span2
        if len(span2) == 0:
            return span1
        
        return Span(min(span1.start, span2.start), max(span1.end, span2.end))

    def _starts_with_closing_delimiter(self, span: Span, content: bytes) -> bool:
        """Check if a span starts with a closing delimiter like ), }, or ]."""
        chunk_content = self._extract_chunk_content(span, content).strip()
        return chunk_content and chunk_content[0] in [')', '}', ']']

    def _extract_chunk_content(self, span: Span, content: bytes) -> str:
        """Extract the string content for a given span."""
        try:
            return content[span.start:span.end].decode('utf-8')
        except (UnicodeDecodeError, IndexError):
            return ""
