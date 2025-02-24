from deputydev_core.services.chunking.strategies.metadata_chunking.base_metadata_chunker import (
    BaseMetadataChunker,
)
from deputydev_core.services.chunking.utils.grammar_utils import LanguageIdentifiers


class KotlinMetadataChunker(BaseMetadataChunker):
    language_identifiers = {
        LanguageIdentifiers.FUNCTION_DEFINITION.value: [
            "function_declaration",
            "lambda_expression",
            "anonymous_function",
            "constructor_declaration",
        ],
        LanguageIdentifiers.CLASS_DEFINITION.value: [
            "class_declaration",
            "object_declaration",
            "interface_declaration",
        ],
        LanguageIdentifiers.FUNCTION_IDENTIFIER.value: ["simple_identifier"],
        LanguageIdentifiers.CLASS_IDENTIFIER.value: ["type_identifier"],
        LanguageIdentifiers.DECORATOR.value: "NA",
        LanguageIdentifiers.FUNCTION_CLASS_WRAPPER.value: [],
        LanguageIdentifiers.NAMESPACE.value: [],
        LanguageIdentifiers.NAMESPACE_IDENTIFIER.value: [],
    }
