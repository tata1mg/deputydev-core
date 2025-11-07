from pathlib import Path
from typing import Literal, Optional, cast, get_args

from deputydev_core.database.async_db_manager import AsyncDBManager
from deputydev_core.models.dto.sqlite_file_chunk_dto import ChunkDTO, FileDTO
from deputydev_core.services.chunk_sync_service.chunker import RawChunk, TreeSitterChunker
from deputydev_core.services.chunk_sync_service.constant import SUPPORTED_LANGUAGES
from deputydev_core.services.chunk_sync_service.guess_language import guess_language
from deputydev_core.services.chunk_sync_service.repo_scan import diff_repo_and_db
from deputydev_core.utils.app_logger import AppLogger


class ChunkSyncService:
    def __init__(self, db: AsyncDBManager) -> None:
        self.db = db

    async def sync_repo_state(self, repo_path: str, file_hash_map: dict[str, str]) -> None:
        """
        Synchronize DB state with the current repo.
        - Deletes missing or changed files (and their chunks)
        - Inserts new or updated ones
        """
        db_files = await self.db.get_all_files_from_repo(repo_path)
        AppLogger.log_info(f"🔍 Comparing {len(file_hash_map)} repo files with {len(db_files)} DB files...")
        to_insert, to_update, to_delete = diff_repo_and_db(file_hash_map, db_files)

        to_insert = sorted(set(to_insert))
        to_update = sorted(set(to_update))
        to_delete = sorted(set(to_delete))
        AppLogger.log_info(
            f"Repo scan results - New: {len(to_insert)} | Updated: {len(to_update)} | Deleted: {len(to_delete)}"
        )

        # ------------------------------------------------------------------
        # Step 1. Delete old / missing files (and their chunks)
        # ------------------------------------------------------------------
        delete_targets = [f for f in db_files if f.file_path in set(to_update) | set(to_delete)]
        delete_ids = [f.id for f in delete_targets if f.id is not None]

        if delete_ids:
            await self.db.delete_files(delete_ids)
            AppLogger.log_info(f"Deleted {len(delete_ids)} files and their chunks.")

        # ------------------------------------------------------------------
        # Step 2. Prepare new + updated files for insertion
        # ------------------------------------------------------------------
        repo_path_obj = Path(repo_path).resolve()
        to_insert_paths = to_insert + to_update  # both treated as new inserts
        processed = {"inserted": 0, "chunked": 0, "unsupported": 0, "skipped_missing": 0, "errors": 0}
        for rel_path in to_insert_paths:
            abs_path = (repo_path_obj / rel_path).resolve()
            try:
                if not abs_path.exists():
                    AppLogger.log_warn(f"File {abs_path} does not exist, skipping.")
                    processed["skipped_missing"] += 1
                    continue

                file_language = guess_language(abs_path)

                file_dto = FileDTO(
                    repo_path=repo_path,
                    file_path=rel_path,
                    file_name=abs_path.name,
                    file_hash=file_hash_map[rel_path],
                    language=file_language,
                    num_lines=1000,  # Placeholder, can be updated later
                    metadata_json={
                        "abs_path": str(abs_path),
                    },
                )
                file_id = await self.db.insert_file(file_dto)
                if file_id is None:
                    AppLogger.log_warn(f"Failed to insert file {rel_path}, skipping chunking.")
                    processed["errors"] += 1
                    continue
                processed["inserted"] += 1

                res = await self.chunk_and_store_file(file_id, file_dto)
                processed["chunked"] += res["chunked"]
                processed["unsupported"] += res["unsupported"]
            except Exception:  # noqa: BLE001
                processed["errors"] += 1
        AppLogger.log_info(
            f"Processed {processed['inserted']} / {len(to_insert_paths)} | "
            f"Unsupported: {processed['unsupported']} | "
            f"Chunks generated: {processed['chunked']} | "
            f"Skipped: {processed['skipped_missing']} | "
            f"Errors: {processed['errors']}"
        )
        AppLogger.log_info("✅ Repo and DB are now synchronized.")

    async def update_repo_state(
        self, repo_path: str, file_hash_map: dict[str, str], files_to_update: list[str]
    ) -> None:
        """
        Synchronize DB state with the current repo.
        - Deletes missing or changed files (and their chunks)
        - Inserts new or updated ones
        """
        await self.db.delete_files_from_repo_filtered(repo_path, files_to_update)
        repo_path_obj = Path(repo_path).resolve()
        to_insert_paths = file_hash_map.keys()
        processed = {"inserted": 0, "chunked": 0, "unsupported": 0, "skipped_missing": 0, "errors": 0}
        for rel_path in to_insert_paths:
            abs_path = (repo_path_obj / rel_path).resolve()
            try:
                if not abs_path.exists():
                    AppLogger.log_warn(f"File {abs_path} does not exist, skipping.")
                    processed["skipped_missing"] += 1
                    continue

                file_language = guess_language(abs_path)

                file_dto = FileDTO(
                    repo_path=repo_path,
                    file_path=rel_path,
                    file_name=abs_path.name,
                    file_hash=file_hash_map[rel_path],
                    language=file_language,
                    num_lines=1000,  # Placeholder, can be updated later
                    metadata_json={
                        "abs_path": str(abs_path),
                    },
                )
                file_id = await self.db.insert_file(file_dto)
                if file_id is None:
                    AppLogger.log_warn(f"Failed to insert file {rel_path}, skipping chunking.")
                    processed["errors"] += 1
                    continue
                processed["inserted"] += 1

                await self.chunk_and_store_file(file_id, file_dto)
                processed["chunked"] += 1
            except Exception as e:  # noqa: BLE001
                AppLogger.log_error(f"❌ Error processing {rel_path}: {e}")
                processed["errors"] += 1
        AppLogger.log_info(
            f"Processed {processed['inserted']} / {len(to_insert_paths)} | "
            f"Chunked: {processed['chunked']} | "
            f"Unsupported: {processed['unsupported']} | "
            f"Skipped: {processed['skipped_missing']} | "
            f"Errors: {processed['errors']}"
        )
        AppLogger.log_info("✅ Repo and DB are now synchronized.")

    async def chunk_and_store_file(self, file_id: int, file_dto: FileDTO) -> dict[str, int]:
        result = {"chunked": 0, "unsupported": 0}
        if file_dto.language not in get_args(SUPPORTED_LANGUAGES):
            result["unsupported"] += 1
            return result
        try:
            language = cast(SUPPORTED_LANGUAGES, file_dto.language)
            chunker = TreeSitterChunker(language)
            abs_path = Path(file_dto.repo_path).joinpath(file_dto.file_path)
            chunks: list[RawChunk] = await chunker.extract_chunks(abs_path)

            if not chunks:
                return result
            inserted_chunks = 0
            for chunk in chunks:
                category = self._categorize_chunk(chunk, chunker)
                if category is None:
                    if chunk.node_type != "decorated_definition":
                        AppLogger.log_warn(
                            f"Skipping chunk {chunk.node_name} (node_type={chunk.node_type}) "
                            f"in file {file_dto.file_path}: unable to categorize."
                        )
                    continue
                chunk_dto = ChunkDTO(
                    file_id=file_id,
                    node_name=chunk.node_name,
                    node_type=chunk.node_type,
                    category=category,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    parent_name=chunk.parent_name,
                    parent_type=chunk.parent_type,
                    metadata_json=chunk.metadata_json,
                )
                await self.db.insert_chunk(chunk_dto)
                inserted_chunks += 1
            result["chunked"] = inserted_chunks
        except Exception as e:  # noqa: BLE001
            AppLogger.log_error(f"Error chunking file {file_dto.file_path}: {e}")
        return result

    def _categorize_chunk(
        self,
        chunk: RawChunk,
        chunker: TreeSitterChunker,
    ) -> Optional[Literal["function", "class", "import"]]:
        node_type = chunk.node_type or ""

        if node_type == "import_block" or node_type in chunker.import_types:
            return "import"
        if node_type in chunker.class_types:
            return "class"
        if node_type in chunker.func_types:
            return "function"
        if node_type == "decorated_definition":
            return None  # avoid duplicate entries for Python decorators

        return None
