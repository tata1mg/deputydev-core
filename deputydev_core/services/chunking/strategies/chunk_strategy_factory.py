from deputydev_core.services.chunking.strategies.base_chunker import \
    BaseChunker
from deputydev_core.services.chunking.strategies.legacy_chunker import \
    LegacyChunker
from deputydev_core.services.chunking.strategies.metadata_chunking.base_metadata_chunker import \
    BaseMetadataChunker
from deputydev_core.services.chunking.strategies.metadata_chunking.java_metadata_chunker import \
    JavaMetadataChunker
from deputydev_core.services.chunking.strategies.metadata_chunking.javascript_metadata_chunker import \
    JavascriptMetadataChunker
from deputydev_core.services.chunking.strategies.metadata_chunking.kotlin_metadata_chunker import \
    KotlinMetadataChunker
from deputydev_core.services.chunking.strategies.metadata_chunking.python_metadata_chunker import \
    PythonMetadataChunker
from deputydev_core.services.chunking.strategies.metadata_chunking.ruby_metadata_chunker import \
    RubyMetadataChunker
from deputydev_core.services.chunking.strategies.metadata_chunking.typescript_metadata_chunker import \
    TypescriptMetadataChunker


class ChunkingStrategyFactory:
    # We can keep a map of extension is to specific meta data chunking class that overrides base meta_data chunking methods
    _language_specific_chunkers = {
        "python": PythonMetadataChunker,
        "javascript": JavascriptMetadataChunker,
        "tsx": TypescriptMetadataChunker,
        "typescript": TypescriptMetadataChunker,
        "java": JavaMetadataChunker,
        "ruby": RubyMetadataChunker,
        "kotlin": KotlinMetadataChunker,
    }

    @classmethod
    def create_strategy(
        cls, language: str, is_eligible_for_new_chunking: bool
    ) -> BaseChunker:
        """Creates appropriate chunking strategy"""
        if (
            not is_eligible_for_new_chunking
            or language not in cls._language_specific_chunkers
        ):
            return LegacyChunker()

        return cls._language_specific_chunkers.get(language, BaseMetadataChunker)()
