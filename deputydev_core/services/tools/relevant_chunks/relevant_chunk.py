import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from deputydev_core.services.chunking.chunk_info import ChunkInfo, ChunkSourceDetails
from deputydev_core.services.initialization.initialization_service import InitializationManager
from deputydev_core.services.repo.local_repo.local_repo_factory import LocalRepoFactory
from deputydev_core.services.repository.chunk_files_service import ChunkFilesService
from deputydev_core.services.repository.chunk_service import ChunkService
from deputydev_core.services.tools.focussed_snippet_search.dataclass.main import (
    AutoCompleteSearchParams,
    ChunkDetails,
    ChunkInfoAndHash,
    CodeSnippetDetails,
    DirectoryStructureParams,
    FocusChunksParams,
)
from deputydev_core.services.tools.iterative_file_reader.iterative_file_reader import IterativeFileReader
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.weaviate import (
    get_weaviate_client,
)


class RelevantChunks:
    def __init__(self, repo_path: str, ripgrep_path: Optional[str]) -> None:
        self.repo_path = Path(repo_path)
        self.ripgrep_path = ripgrep_path

    def get_file_chunk(self, file_path: str, start_line: int, end_line: int) -> str:
        abs_file_path = Path(self.repo_path) / file_path
        with abs_file_path.open("r", encoding="utf-8", errors="ignore") as file:
            lines = file.readlines()
            return "".join(lines[start_line - 1 : end_line])

    def _refilter_chunk_info_list(
        self,
        chunk_info_list: List[ChunkInfoAndHash],
        payload: FocusChunksParams,
    ) -> List[ChunkInfoAndHash]:
        """
        Refine the chunk info list based on the focus chunks and directories.
        """
        search_type = payload.search_item_type
        if search_type == "file" and payload.search_item_path:
            # Filter by file path
            chunk_info_list = [
                chunk_info_and_hash
                for chunk_info_and_hash in chunk_info_list
                if chunk_info_and_hash.chunk_info.source_details.file_path == payload.search_item_path
            ]
        # TODO: uncomment this kachra
        """
        elif search_type == "class":
            # Filter by class name
            chunk_info_list = [
                chunk_info_and_hash
                for chunk_info_and_hash in chunk_info_list
                if payload.search_item_name
                in chunk_info_and_hash.chunk_info.metadata.all_classes
            ]
        elif search_type == "function":
            # Filter by function name
            chunk_info_list = [
                chunk_info_and_hash
                for chunk_info_and_hash in chunk_info_list
                if payload.search_item_name
                in chunk_info_and_hash.chunk_info.metadata.all_functions
            ]
        """
        return chunk_info_list

    async def get_focus_chunks(
        self, payload: FocusChunksParams, initialization_manager: InitializationManager
    ) -> List[Dict[str, Any]]:
        repo_path = payload.repo_path
        local_repo = LocalRepoFactory.get_local_repo(repo_path, ripgrep_path=self.ripgrep_path)
        chunkable_files_and_hashes = await local_repo.get_chunkable_files_and_commit_hashes()

        weaviate_client = await get_weaviate_client(initialization_manager)
        if (
            payload.search_item_type != "directory"
            and isinstance(payload.chunks[0], ChunkDetails)
            and payload.search_item_name
            and payload.search_item_type
        ):
            revised_relevant_chunks = await ChunkFilesService(
                weaviate_client=weaviate_client
            ).get_chunk_files_matching_exact_search_key(
                search_key=(
                    payload.search_item_name
                    if payload.search_item_type != "file"
                    else payload.search_item_path or payload.search_item_name
                ),
                search_type=payload.search_item_type,
                file_path_to_hash_map={
                    k: v
                    for k, v in chunkable_files_and_hashes.items()
                    if ((k == payload.search_item_path) or (not payload.search_item_path))
                },
            )

            payload.chunks = [
                ChunkDetails(
                    start_line=chunk_file_obj.start_line,
                    end_line=chunk_file_obj.end_line,
                    chunk_hash=chunk_file_obj.chunk_hash,
                    file_path=chunk_file_obj.file_path,
                    file_hash=chunk_file_obj.file_hash,
                    meta_info=chunk_file_obj.meta_info,
                )
                for chunk_file_obj in revised_relevant_chunks
            ]

        chunks = await ChunkService(weaviate_client=weaviate_client).get_chunks_by_chunk_hashes(
            chunk_hashes=[chunk.chunk_hash for chunk in payload.chunks if isinstance(chunk, ChunkDetails)]
        )

        chunk_info_list: List[ChunkInfoAndHash] = []
        for chunk_dto, _vector in chunks:
            for chunk_file in payload.chunks:
                if chunk_file.chunk_hash == chunk_dto.chunk_hash:
                    chunk_info_list.append(
                        ChunkInfoAndHash(
                            chunk_info=ChunkInfo(
                                content=chunk_dto.text,
                                source_details=ChunkSourceDetails(
                                    file_path=chunk_file.file_path,
                                    file_hash=chunk_file.file_hash,
                                    start_line=chunk_file.start_line,
                                    end_line=chunk_file.end_line,
                                ),
                                embedding=None,
                                metadata=chunk_file.meta_info,
                            ),
                            chunk_hash=chunk_file.chunk_hash,
                        )
                    )
                    break

        # handle code snippets
        code_snippets = [chunk for chunk in payload.chunks if isinstance(chunk, CodeSnippetDetails)]

        for code_snippet in code_snippets:
            file_content = ""
            try:
                file_content = self.get_file_chunk(
                    file_path=code_snippet.file_path,
                    start_line=code_snippet.start_line,
                    end_line=code_snippet.end_line,
                )
                chunk_info_list.append(
                    ChunkInfoAndHash(
                        chunk_info=ChunkInfo(
                            content=file_content,
                            source_details=ChunkSourceDetails(
                                file_path=code_snippet.file_path,
                                file_hash=None,
                                start_line=code_snippet.start_line,
                                end_line=code_snippet.end_line,
                            ),
                            embedding=None,
                            metadata=None,
                        ),
                        chunk_hash=code_snippet.chunk_hash,
                    )
                )
            except Exception as ex:  # noqa: BLE001
                AppLogger.log_error(f"Error occurred while fetching code snippet: {ex}")

        new_file_path_to_hash_map_for_import_only = {
            chunk_info_and_hash.chunk_info.source_details.file_path: chunk_info_and_hash.chunk_info.source_details.file_hash
            for chunk_info_and_hash in chunk_info_list
            if chunk_info_and_hash.chunk_info.source_details.file_hash
        }

        import_only_chunk_files = await ChunkFilesService(weaviate_client).get_only_import_chunk_files_by_commit_hashes(
            file_to_commit_hashes=new_file_path_to_hash_map_for_import_only
        )
        import_only_chunk_hashes = [chunk_file.chunk_hash for chunk_file in import_only_chunk_files]

        import_only_chunk_dtos = await ChunkService(weaviate_client).get_chunks_by_chunk_hashes(
            chunk_hashes=import_only_chunk_hashes,
        )

        chunk_info_set = set(chunk_info_list)

        for chunk_dto, _vector in import_only_chunk_dtos:
            for chunk_file in import_only_chunk_files:
                if chunk_file.chunk_hash == chunk_dto.chunk_hash:
                    chunk_info_set.add(
                        ChunkInfoAndHash(
                            chunk_info=ChunkInfo(
                                content=chunk_dto.text,
                                source_details=ChunkSourceDetails(
                                    file_path=chunk_file.file_path,
                                    file_hash=chunk_file.file_hash,
                                    start_line=chunk_file.start_line,
                                    end_line=chunk_file.end_line,
                                ),
                                embedding=None,
                                metadata=chunk_file.meta_info,
                            ),
                            chunk_hash=chunk_file.chunk_hash,
                        )
                    )
                    break

        updated_chunk_info_list = list(chunk_info_set)

        # sort updated_chunk_info_list based on start_line
        updated_chunk_info_list.sort(
            key=lambda x: (
                x.chunk_info.source_details.file_path,
                x.chunk_info.source_details.start_line,
            )
        )

        # refilter the chunk_info_list to remove extra junk
        updated_chunk_info_list = self._refilter_chunk_info_list(
            chunk_info_list=updated_chunk_info_list, payload=payload
        )

        return [chunk_info.model_dump(mode="json") for chunk_info in updated_chunk_info_list]

    async def get_autocomplete_search_chunks(self, payload: AutoCompleteSearchParams) -> ChunkInfo:
        file_reader = IterativeFileReader(
            file_path=payload.search_item_path,
            repo_path=payload.repo_path,
        )
        if payload.search_item_type == "file" or payload.chunk is None:
            file_content = await file_reader.read_lines()

            chunk = ChunkInfo(
                content=file_content.chunk.content,
                source_details=ChunkSourceDetails(
                    file_path=payload.search_item_path,
                    start_line=file_content.chunk.source_details.start_line,
                    end_line=file_content.chunk.source_details.end_line,
                ),
                has_embedded_lines=file_content.was_summary,
            )
            return chunk

        else:
            file_content = await file_reader.read_lines(
                start_line=payload.chunk.start_line, end_line=payload.chunk.end_line
            )

            chunk = ChunkInfo(
                content=file_content.chunk.content,
                source_details=ChunkSourceDetails(
                    file_path=payload.chunk.file_path,
                    start_line=file_content.chunk.source_details.start_line,
                    end_line=file_content.chunk.source_details.end_line,
                ),
                has_embedded_lines=file_content.was_summary,
            )
            return chunk

    async def get_directory_structure(self, payload: DirectoryStructureParams) -> List[Dict[str, str]]:
        base_path = self.repo_path / (payload.directory_path or "")
        result: List[Dict[str, str]] = []

        try:
            with os.scandir(base_path) as entries:
                for entry in entries:
                    entry_type = "directory" if entry.is_dir() else "file"
                    result.append({"name": entry.name, "type": entry_type})
        except Exception as e:
            AppLogger.log_error(f"Error scanning directory {base_path}: {e}")
            raise

        return result
