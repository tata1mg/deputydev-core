from deputydev_core.services.chunking.strategies.metadata_chunking.base_metadata_chunker import \
    BaseMetadataChunker
from deputydev_core.services.chunking.utils.grammar_utils import \
    LanguageIdentifiers


class PythonMetadataChunker(BaseMetadataChunker):
    language_identifiers = {
        LanguageIdentifiers.FUNCTION_DEFINITION.value: ["function_definition"],
        LanguageIdentifiers.DECORATED_DEFINITION.value: ["decorated_definition"],
        LanguageIdentifiers.CLASS_DEFINITION.value: ["class_definition"],
        LanguageIdentifiers.FUNCTION_IDENTIFIER.value: ["identifier"],
        LanguageIdentifiers.CLASS_IDENTIFIER.value: ["identifier"],
        LanguageIdentifiers.DECORATOR.value: "decorator",
        LanguageIdentifiers.FUNCTION_CLASS_WRAPPER.value: ["decorated_definition"],
        LanguageIdentifiers.NAMESPACE.value: ["NA"],
        LanguageIdentifiers.NAMESPACE_IDENTIFIER.value: [],
    }
