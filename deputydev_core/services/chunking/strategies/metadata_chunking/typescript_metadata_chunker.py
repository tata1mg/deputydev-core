from deputydev_core.services.chunking.strategies.metadata_chunking.base_metadata_chunker import (
    BaseMetadataChunker,
)
from deputydev_core.services.chunking.utils.grammar_utils import LanguageIdentifiers


class TypescriptMetadataChunker(BaseMetadataChunker):
    language_identifiers = {
        LanguageIdentifiers.FUNCTION_DEFINITION.value: [
            "method_definition",
            "function_declaration",
            "generator_function_declaration",
            "pair"
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
