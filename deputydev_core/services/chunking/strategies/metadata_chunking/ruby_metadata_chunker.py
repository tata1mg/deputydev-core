from deputydev_core.services.chunking.strategies.metadata_chunking.base_metadata_chunker import BaseMetadataChunker
from deputydev_core.services.chunking.utils.grammar_utils import LanguageIdentifiers


class RubyMetadataChunker(BaseMetadataChunker):
    language_identifiers = {
        LanguageIdentifiers.FUNCTION_DEFINITION.value: [
            "method",
            "singleton_method",
            "class_method",
        ],
        LanguageIdentifiers.CLASS_DEFINITION.value: ["class", "singleton_class"],
        LanguageIdentifiers.FUNCTION_IDENTIFIER.value: ["identifier", "constant"],
        LanguageIdentifiers.CLASS_IDENTIFIER.value: ["constant"],
        LanguageIdentifiers.DECORATOR.value: "NA",
        LanguageIdentifiers.FUNCTION_CLASS_WRAPPER.value: [],
        LanguageIdentifiers.NAMESPACE.value: ["module"],
        LanguageIdentifiers.NAMESPACE_IDENTIFIER.value: ["constant"],
    }
