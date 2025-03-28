from deputydev_core.services.chunking.strategies.metadata_chunking.base_metadata_chunker import (
    BaseMetadataChunker,
)
from deputydev_core.services.chunking.utils.grammar_utils import LanguageIdentifiers
from tree_sitter import Node
from typing import Dict, Optional


class JavascriptMetadataChunker(BaseMetadataChunker):
    language_identifiers = {
        LanguageIdentifiers.FUNCTION_DEFINITION.value: [
            "method_definition",
            "function_declaration",
            "generator_function_declaration",
        ],
        LanguageIdentifiers.CLASS_DEFINITION.value: [
            "class_declaration",
            "abstract_class_declaration",
        ],
        LanguageIdentifiers.FUNCTION_IDENTIFIER.value: [
            "property_identifier",
            "identifier",
        ],
        LanguageIdentifiers.CLASS_IDENTIFIER.value: ["type_identifier"],
        LanguageIdentifiers.DECORATOR.value: "NA",
        LanguageIdentifiers.FUNCTION_CLASS_WRAPPER.value: ["expression_statement"],
        LanguageIdentifiers.NAMESPACE.value: ["namespace", "internal_module"],
        LanguageIdentifiers.NAMESPACE_IDENTIFIER.value: ["identifier"],
        LanguageIdentifiers.DECORATED_DEFINITION.value: [],
    }

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
                + ["variable_declarator"]
                # For node type lexical_declaration, identifier is present inside variable_declarator node
            ):
                name = self.extract_name(child, grammar)
                if name:
                    return name

        return None

    def is_function_node(self, node: Node, grammar: Dict[str, str]):
        """
        Checks if a given node is function by visiting to depth
        Args:
            node (Ast node):
            grammar (Dict[str, str]): grammar for the language

        Returns:

        """
        if self.is_lexical_declaration(node) or self.is_pair_function(node):
            return True

        if node.type in grammar[LanguageIdentifiers.FUNCTION_CLASS_WRAPPER.value]:
            is_function_node = False
            for child in node.children:
                is_function_node = is_function_node or (
                    child.type in grammar[LanguageIdentifiers.FUNCTION_DEFINITION.value]
                )

            return is_function_node
        return node.type in grammar[LanguageIdentifiers.FUNCTION_DEFINITION.value]

    def is_lexical_declaration(self, node: Node):
        if node.type == "lexical_declaration":
            for child in node.children:
                if child.type == "variable_declarator":
                    # Check if the variable_declarator node has a child of type identifier
                    if any(grandchild.type == "identifier" for grandchild in child.children):
                        return True
        return False

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
        elif self.is_lexical_declaration(node) or self.is_pair_function(node):
            return True
        return node.type in (
            grammar[LanguageIdentifiers.FUNCTION_DEFINITION.value]
            + grammar[LanguageIdentifiers.CLASS_DEFINITION.value]
            + grammar[LanguageIdentifiers.NAMESPACE.value]
        )

    def is_pair_function(self, node: Node):
        return node.type == "pair" and any(child.type == "function_expression" for child in node.children)
