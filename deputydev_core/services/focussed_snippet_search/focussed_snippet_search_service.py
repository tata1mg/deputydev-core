import asyncio
from typing import Dict, List, Set

from deputydev_core.models.dto.chunk_dto import ChunkDTO
from deputydev_core.models.dto.chunk_file_dto import ChunkFileDTO
from deputydev_core.services.chunking.chunk_info import ChunkInfo, ChunkSourceDetails
from deputydev_core.services.focussed_snippet_search.dataclass.main import (
    ChunkDetails,
    ChunkInfoAndHash,
    FocusChunksParams,
    FocussedSnippetSearchParams,
    FocussedSnippetSearchResponse,
    SearchTerm,
)
from deputydev_core.services.relevant_chunks.relevant_chunk_service import (
    RelevantChunksService,
)
from deputydev_core.services.repository.chunk_files_service import ChunkFilesService
from deputydev_core.services.repository.chunk_service import ChunkService
from deputydev_core.services.shared_chunks.shared_chunks_manager import (
    SharedChunksManager,
)
from deputydev_core.utils.constants.constants import CHUNKFILE_KEYWORD_PROPERTY_MAP


class FocussedSnippetSearchService:
    @classmethod
    async def search_code(cls, payload: FocussedSnippetSearchParams, weaviate_client, initialization_manager):
        """
        Search for code based on multiple search terms.
        """
        repo_path = payload.repo_path
        search_terms = payload.search_terms

        try:
            chunkable_files_and_hashes = await SharedChunksManager.initialize_chunks(repo_path)

            # initialization_manager = ExtensionInitialisationManager(repo_path=repo_path)
            weaviate_client, _new_weaviate_process, _schema_cleaned = (
                await initialization_manager.initialize_vector_db()
            )

            chunk_files_service = ChunkFilesService(weaviate_client)
            chunk_service = ChunkService(weaviate_client)

            chunk_files_results = await cls.search_chunk_files(
                search_terms, chunkable_files_and_hashes, chunk_files_service
            )

            all_chunk_hashes = cls.extract_chunk_hashes(chunk_files_results)

            chunks_by_hash = await cls.fetch_chunks_by_hashes(all_chunk_hashes, chunk_service)

            final_results = cls.map_chunks_to_results(search_terms, chunk_files_results, chunks_by_hash)

            # update final chunks in results
            updated_results = asyncio.gather(
                *[cls.update_chunks_list(result, repo_path, initialization_manager) for result in final_results]
            )
            final_results = await updated_results
            return {"response": [result.model_dump() for result in final_results]}

        finally:
            if weaviate_client:
                weaviate_client.sync_client.close()
                await weaviate_client.async_client.close()

    @classmethod
    async def update_chunks_list(
        cls, payload: FocussedSnippetSearchResponse, repo_path: str, initialization_manager
    ) -> FocussedSnippetSearchResponse:
        if payload.type not in ["class", "function"] or not payload.chunks:
            return payload

        # get focus chunks
        new_chunks = await RelevantChunksService(repo_path=repo_path).get_focus_chunks(
            FocusChunksParams(
                repo_path=repo_path,
                search_item_name=payload.keyword,
                search_item_type=payload.type,
                chunks=[
                    ChunkDetails(
                        start_line=_.source_details.start_line,
                        end_line=_.source_details.end_line,
                        chunk_hash=_.content_hash,
                        file_path=_.source_details.file_path,
                        file_hash=_.source_details.file_hash,
                    )
                    for _ in payload.chunks
                ],
            ),
            initialization_manager,
        )

        if not new_chunks:
            return payload

        # update chunks with chunk text
        all_new_chunks = [ChunkInfoAndHash(**new_chunk) for new_chunk in new_chunks]
        payload.chunks = [_.chunk_info for _ in all_new_chunks]
        return payload

    @classmethod
    async def search_chunk_files(cls, search_terms, chunkable_files_and_hashes, chunk_files_service):

        tasks = [
            cls.process_file_search(idx, chunk_files_service, term, chunkable_files_and_hashes)
            for idx, term in enumerate(search_terms)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {idx: chunks for idx, chunks in results if not isinstance(results, Exception)}

    @classmethod
    async def process_file_search(
        cls,
        idx,
        chunk_files_service: ChunkFilesService,
        term: SearchTerm,
        chunkable_files_and_hashes: Dict,
    ):
        """
        Process a single search term

        Args:
            idx: index of input for mapping
            chunk_files_service: Service for querying chunks
            term: Search term parameters
            chunkable_files_and_hashes: Dictionary of file paths and hashes

        Returns:
            List of search results for the term
        """

        property_name = CHUNKFILE_KEYWORD_PROPERTY_MAP.get(term.type)
        if not property_name:
            return idx, []

        chunks = await chunk_files_service.get_keyword_type_chunks(
            keyword=term.keyword,
            type=term.type,
            chunkable_files_and_hashes=chunkable_files_and_hashes,
            limit=5,
        )
        sorted_chunks = sorted(chunks, key=lambda x: getattr(x.metadata, "score", 0.0), reverse=True)

        return idx, sorted_chunks

    @classmethod
    def extract_chunk_hashes(cls, chunk_files_results):
        """
        Extract all unique chunk hashes from chunk files results.

        Args:
            chunk_files_results: Dictionary mapping request index to list of chunk files

        Returns:
            Set of unique chunk hashes
        """
        all_chunk_hashes = set()
        for chunks in chunk_files_results.values():
            for chunk in chunks:
                chunk_file_dto = ChunkFileDTO(**chunk.properties, id=str(chunk.uuid))
                all_chunk_hashes.add(chunk_file_dto.chunk_hash)

        return all_chunk_hashes

    @classmethod
    async def fetch_chunks_by_hashes(cls, chunk_hashes: Set[str], chunk_service):
        """
        Fetch all chunks by their hashes.

        Args:
            chunk_hashes: Set of chunk hashes

        Returns:
            Dictionary mapping chunk hash to chunk DTO
        """
        if not chunk_hashes:
            return {}

        chunks_with_vectors = await chunk_service.get_chunks_by_chunk_hashes(list(chunk_hashes))

        return {chunk.chunk_hash: chunk for chunk, _ in chunks_with_vectors}

    @classmethod
    def map_chunks_to_results(
        cls,
        search_terms: List[SearchTerm],
        chunk_files_results: Dict[int, List[ChunkFileDTO]],
        chunks_by_hash: Dict[str, ChunkDTO],
    ) -> List[FocussedSnippetSearchResponse]:
        """
        Map chunks to search results.

        Args:
            search_requests: List of search requests
            chunk_files_results: Dictionary mapping request index to list of chunk files
            chunks_by_hash: Dictionary mapping chunk hash to chunk

        Returns:
            List of code search results
        """

        final_results: List[FocussedSnippetSearchResponse] = []

        for idx, request in enumerate(search_terms):
            chunk_files = chunk_files_results.get(idx, [])

            # Skip if no results
            if not chunk_files:
                final_results.append(
                    FocussedSnippetSearchResponse(
                        keyword=request.keyword,
                        type=request.type,
                        file_path=request.file_path,
                        chunks=[],
                    )
                )
                continue

            # Map chunks
            chunk_results: List[ChunkInfo] = []
            for chunk_file in chunk_files:
                chunk_file_dto = ChunkFileDTO(**chunk_file.properties, id=str(chunk_file.uuid))
                # Get the corresponding chunk text
                chunk = chunks_by_hash.get(chunk_file_dto.chunk_hash)
                if chunk:
                    chunk_results.append(
                        ChunkInfo(
                            content=chunk.text,
                            source_details=ChunkSourceDetails(
                                file_path=chunk_file_dto.file_path,
                                start_line=chunk_file_dto.start_line,
                                end_line=chunk_file_dto.end_line,
                                file_hash=chunk_file_dto.file_hash,
                            ),
                        )
                    )

            # Create result
            final_results.append(
                FocussedSnippetSearchResponse(
                    keyword=request.keyword,
                    type=request.type,
                    file_path=request.file_path,
                    chunks=chunk_results,
                )
            )

        return final_results
