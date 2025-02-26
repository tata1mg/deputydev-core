from deputydev_core.services.chunking.strategies.metadata_chunking.base_metadata_chunker import \
    BaseMetadataChunker
from deputydev_core.services.chunking.utils.grammar_utils import \
    LanguageIdentifiers


class JavaMetadataChunker(BaseMetadataChunker):
    language_identifiers = {
        LanguageIdentifiers.FUNCTION_DEFINITION.value: [
            "method_declaration",
            "function_declaration",
            "constructor_declaration",
            "lambda_expression",
            "annotation_type_declaration",
        ],
        LanguageIdentifiers.CLASS_DEFINITION.value: [
            "class_declaration",
            "abstract_class_declaration",
            "interface_declaration",
            "enum_declaration",
        ],
        LanguageIdentifiers.FUNCTION_IDENTIFIER.value: ["identifier"],
        LanguageIdentifiers.CLASS_IDENTIFIER.value: ["identifier"],
        LanguageIdentifiers.DECORATOR.value: "NA",
        LanguageIdentifiers.FUNCTION_CLASS_WRAPPER.value: [],
        LanguageIdentifiers.NAMESPACE.value: ["NA"],
        LanguageIdentifiers.NAMESPACE_IDENTIFIER.value: [],
    }
