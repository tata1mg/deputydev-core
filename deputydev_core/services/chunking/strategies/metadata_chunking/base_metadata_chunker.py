import copy
from typing import Dict, List, Optional, Tuple

from tree_sitter import Node

from deputydev_core.services.chunking.dataclass.main import (
    ChunkMetadata,
    ChunkMetadataHierachyObject,
    ChunkNodeType,
    NeoSpan,
)
from deputydev_core.services.chunking.utils.chunk_utils import get_current_chunk_length, deduplicate_hierarchy
from deputydev_core.services.chunking.utils.grammar_utils import LanguageIdentifiers

from ..base_chunker import BaseChunker


class BaseMetadataChunker(BaseChunker):

    language_identifiers = {}

    def chunk_code(self, tree, content: bytes, max_chars, coalesce, language) -> List[NeoSpan]:
        """Main implementation for new chunking"""
        all_classes: List[str] = []
        all_functions: List[str] = []
        chunks = self.chunk_node_with_meta_data(
            tree.root_node,
            max_chars=max_chars,
            source_code=content,
            all_functions=all_functions,
            all_classes=all_classes,
            language=language,
        )
        for chunk in chunks:
            if chunk.metadata.import_only_chunk:
                chunk.metadata.all_classes = list(set(all_classes))
                chunk.metadata.all_functions = list(set(all_functions))

        new_chunks = self.dechunk(chunks, coalesce=coalesce, source_code=content, max_chars=max_chars)
        return new_chunks

    def is_function_node(self, node: Node, grammar: Dict[str, str]):
        """
        Checks if a given node is function by visiting to depth
        Args:
            node (Ast node):
            grammar (Dict[str, str]): grammar for the language

        Returns:

        """
        if node.type in grammar[LanguageIdentifiers.FUNCTION_CLASS_WRAPPER.value]:
            is_function_node = False
            for child in node.children:
                is_function_node = is_function_node or (
                    child.type in grammar[LanguageIdentifiers.FUNCTION_DEFINITION.value]
                )

            return is_function_node
        return node.type in grammar[LanguageIdentifiers.FUNCTION_DEFINITION.value]

    def is_class_node(self, node: Node, grammar: Dict[str, str]):
        """
        Checks if a given node is class by visiting to depth
        Args:
            node (Ast node):
            grammar (Dict[str, str]): grammar for the language

        Returns:

        """
        if node.type in grammar[LanguageIdentifiers.FUNCTION_CLASS_WRAPPER.value]:
            is_class_node = False
            for child in node.children:
                is_class_node = is_class_node or (child.type in grammar[LanguageIdentifiers.CLASS_DEFINITION.value])
            return is_class_node

        return node.type in grammar[LanguageIdentifiers.CLASS_DEFINITION.value]

    def is_namespace_node(self, node: Node, grammar: Dict[str, str]):
        """
        Checks if a given node is namespace by visiting to depth
        Args:
            node (Ast node):
            grammar (Dict[str, str]): grammar for the language

        Returns:

        """
        return node.type in grammar[LanguageIdentifiers.NAMESPACE.value]

    def is_node_breakable(self, node: Node, grammar: Dict[str, str]) -> bool:
        if node.type in grammar[LanguageIdentifiers.FUNCTION_CLASS_WRAPPER.value]:
            breakable = False
            for child in node.children:
                breakable = breakable or (
                    child.type
                    in grammar[LanguageIdentifiers.CLASS_DEFINITION.value]
                    + grammar[LanguageIdentifiers.FUNCTION_DEFINITION.value]
                    + grammar[LanguageIdentifiers.NAMESPACE.value]
                )
            return breakable
        return node.type in (
            grammar[LanguageIdentifiers.FUNCTION_DEFINITION.value]
            + grammar[LanguageIdentifiers.CLASS_DEFINITION.value]
            + grammar[LanguageIdentifiers.NAMESPACE.value]
        )

    def extract_name(self, node: Node, grammar: Dict[str, str]) -> Optional[str]:
        """
        Recursively extract the name from a node, handling different possible structures
        """
        # Direct identifier check
        if (
            node.type
            in grammar[LanguageIdentifiers.FUNCTION_IDENTIFIER.value]
            + grammar[LanguageIdentifiers.CLASS_IDENTIFIER.value]
            + grammar[LanguageIdentifiers.NAMESPACE_IDENTIFIER.value]
        ):
            return node.text.decode("utf-8")

        # Search in direct children for an identifier
        for child in node.children:
            if (
                child.type
                in grammar[LanguageIdentifiers.FUNCTION_IDENTIFIER.value]
                + grammar[LanguageIdentifiers.CLASS_IDENTIFIER.value]
                + grammar[LanguageIdentifiers.NAMESPACE_IDENTIFIER.value]
            ):
                return child.text.decode("utf-8")

        # Recursive search for nested definitions
        for child in node.children:
            # Check for nested class or function definitions
            if (
                child.type
                in grammar[LanguageIdentifiers.CLASS_DEFINITION.value]
                + grammar[LanguageIdentifiers.FUNCTION_DEFINITION.value]
                + grammar[LanguageIdentifiers.NAMESPACE_IDENTIFIER.value]
            ):
                name = self.extract_name(child, grammar)
                if name:
                    return name

        return None

    def is_valid_chunk(self, chunk):
        """
        chunk: Neospan chunk
        Function to check if chunk is valid and can be added in chunks list.
        We are initializing the chunk initially with same start and end
        position so removing them to avoid duplicacy.
        """
        if chunk and not chunk.start == chunk.end:
            return True
        return False

    def chunk_node_with_meta_data(
        self,
        node: Node,
        max_chars: int,
        source_code: bytes,
        all_classes: List[str],
        all_functions: List[str],
        language: str,
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
        node_children = node.children
        grammar = self.language_identifiers
        prev_hierarchy_length = len(hierarchy)
        # Handle decorators for class or function definitions

        def create_chunk_with_decorators(start_point, end_point, byte_size, decorators=None, current_node=None):
            if decorators:
                # Start from the first decorator
                actual_start = decorators[0].start
                decorators.clear()
            else:
                actual_start = start_point

            chunk_hierarchy = []
            # For non-breakable nodes or regular chunks, use hierarchy
            if current_node and self.is_node_breakable(current_node, grammar) and byte_size > 0:
                chunk_hierarchy = deduplicate_hierarchy(
                    hierarchy + self.get_breakable_node_hierarchy(current_node, grammar)
                )
            else:
                chunk_hierarchy.extend(copy.deepcopy(hierarchy or []))

            return NeoSpan(
                actual_start,
                end_point,
                metadata=ChunkMetadata(
                    hierarchy=copy.deepcopy(chunk_hierarchy),
                    dechunk=not self.is_node_breakable(current_node, grammar),
                    import_only_chunk=not hierarchy and not self.is_node_breakable(current_node, grammar),
                    all_functions=[],
                    all_classes=[],
                    byte_size=byte_size,
                ),
            )

        # Determine if the current node is a class or function
        if node.type not in grammar[LanguageIdentifiers.FUNCTION_CLASS_WRAPPER.value]:
            if self.is_class_node(node, grammar):
                class_name = self.extract_name(node, grammar)
                hierarchy.append(ChunkMetadataHierachyObject(type=ChunkNodeType.CLASS.value, value=class_name))
                all_classes.append(class_name)

            elif self.is_function_node(node, grammar):
                func_name = self.extract_name(node, grammar)
                hierarchy.append(ChunkMetadataHierachyObject(type=ChunkNodeType.FUNCTION.value, value=func_name))
                all_functions.append(func_name)
            elif self.is_namespace_node(node, grammar):
                namespace_name = self.extract_name(node, grammar)
                # namespace type will not be fixed to class or functon so using node actual type
                hierarchy.append(ChunkMetadataHierachyObject(type=node.type, value=namespace_name))

        current_chunk = create_chunk_with_decorators(
            start_point=node.start_point,
            end_point=node.start_point,
            byte_size=0,
            decorators=pending_decorators,
            current_node=node,
        )

        for child in node_children:
            if self.is_class_node(child, grammar):
                class_name = self.extract_name(child, grammar)
                if class_name:
                    all_classes.append(class_name)

            elif self.is_function_node(child, grammar):
                func_name = self.extract_name(child, grammar)
                if func_name:
                    all_functions.append(func_name)

            if child.type == grammar[LanguageIdentifiers.DECORATOR.value]:
                # Store the decorator for the next class or function definition
                pending_decorators.append(NeoSpan(child.start_point, child.end_point))
                continue

            elif child.end_byte - child.start_byte > max_chars:
                # Finalize the current chunk, avoid initiaziable chunk.
                if self.is_valid_chunk(current_chunk):
                    chunks.append(current_chunk)
                current_chunk = None
                # Recursively process large nodes
                chunks.extend(
                    self.chunk_node_with_meta_data(
                        child,
                        max_chars,
                        source_code,
                        all_classes,
                        all_functions,
                        language,
                        hierarchy,
                        pending_decorators,
                    )
                )

            elif (
                child.end_byte - child.start_byte + get_current_chunk_length(current_chunk, source_code) > max_chars
            ) or self.is_node_breakable(child, grammar):
                # Split the current chunk if it exceeds the maximum size
                if self.is_valid_chunk(current_chunk):
                    chunks.append(current_chunk)

                current_chunk = create_chunk_with_decorators(
                    child.start_point,
                    child.end_point,
                    byte_size=child.end_byte - child.start_byte,
                    current_node=child,
                    decorators=pending_decorators,
                )

            else:
                # Append the current child to the chunk
                if current_chunk:
                    current_chunk += create_chunk_with_decorators(
                        child.start_point,
                        child.end_point,
                        byte_size=child.end_byte - child.start_byte,
                        current_node=child,
                    )
                else:
                    current_chunk = create_chunk_with_decorators(
                        child.start_point,
                        child.end_point,
                        byte_size=child.end_byte - child.start_byte,
                        current_node=child,
                    )

        # Finalize the last chunk
        if self.is_valid_chunk(current_chunk):
            chunks.append(current_chunk)

        # pop the last hirarchey
        if hierarchy and len(hierarchy) > 0 and len(hierarchy) > prev_hierarchy_length:
            hierarchy.pop()
        return chunks

    def dechunk(self, chunks: List[NeoSpan], coalesce: int, source_code: bytes, max_chars: int) -> list[NeoSpan]:
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

        previous_chunk = chunks[0]

        for idx, chunk in enumerate(chunks[1:]):
            # check dechunk condition: case when both chunks have same start line
            if chunk.start[0] == previous_chunk.start[0]:
                previous_chunk += chunk

            elif (
                chunk.metadata.dechunk is False
                or previous_chunk.metadata.byte_size + chunk.metadata.byte_size > max_chars
            ):
                if previous_chunk and len(previous_chunk) > 0:
                    new_chunks.append(previous_chunk)
                previous_chunk = chunk

            else:
                previous_chunk += chunk

        # Append any remaining chunk
        if previous_chunk and len(previous_chunk) > 0:
            new_chunks.append(previous_chunk)

        return new_chunks

    def get_breakable_node_hierarchy(self, node: Node, grammar: Dict[str, str]) -> List[ChunkMetadataHierachyObject]:
        """
        Recursively extract all function and class names from a node and its children
        """
        hierarchy = []

        # Check if current node is a function or class
        if self.is_function_node(node, grammar):
            name = self.extract_name(node, grammar)
            if name:
                hierarchy.append(
                    ChunkMetadataHierachyObject(
                        type=ChunkNodeType.FUNCTION.value,
                        value=name,
                        is_breakable_node=True,
                    )
                )

        elif self.is_class_node(node, grammar):
            name = self.extract_name(node, grammar)
            if name:
                hierarchy.append(
                    ChunkMetadataHierachyObject(
                        type=ChunkNodeType.CLASS.value,
                        value=name,
                        is_breakable_node=True,
                    )
                )
        elif self.is_namespace_node(node, grammar):
            name = self.extract_name(node, grammar)
            if name:
                hierarchy.append(ChunkMetadataHierachyObject(type=node.type, value=name))

        # Recursively process children
        for child in node.children:
            child_hierarchy = self.get_breakable_node_hierarchy(child, grammar)
            hierarchy.extend(child_hierarchy)

        return hierarchy
