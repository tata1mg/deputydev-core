from deputydev_core.services.chunking.strategies.metadata_chunking.base_metadata_chunker import (
    BaseMetadataChunker,
)
from deputydev_core.services.chunking.utils.grammar_utils import LanguageIdentifiers


class SwiftMetadataChunker(BaseMetadataChunker):
    language_identifiers = {
        LanguageIdentifiers.FUNCTION_DEFINITION.value: [
            "function_declaration",
            "method_declaration",
            "initializer_declaration",
            "subscript_declaration",
            "operator_declaration",
            "init_declaration"
        ],
        LanguageIdentifiers.CLASS_DEFINITION.value: [
            "class_declaration",
            "struct_declaration",
            "enum_declaration",
            "protocol_declaration",
            "extension_declaration",
        ],
        LanguageIdentifiers.FUNCTION_IDENTIFIER.value: [
            "simple_identifier",
            "identifier",
        ],
        LanguageIdentifiers.CLASS_IDENTIFIER.value: [
            "simple_identifier",
            "identifier",
            "type_identifier"
        ],
        LanguageIdentifiers.DECORATOR.value: "NA",
        LanguageIdentifiers.FUNCTION_CLASS_WRAPPER.value: [],
        LanguageIdentifiers.NAMESPACE.value: [],
        LanguageIdentifiers.NAMESPACE_IDENTIFIER.value: [],
        LanguageIdentifiers.DECORATED_DEFINITION.value: [],
    }