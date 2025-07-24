import logging
from typing import Dict, List, Optional

from deputydev_core.services.repo.local_repo.local_repo_factory import LocalRepoFactory

logger = logging.getLogger(__name__)


class SharedChunksManager:
    _files_commit_hashes: Dict[str, Dict[str, str]] = {}

    @classmethod
    async def initialize_chunks(cls, repo_path: str, ripgrep_path: Optional[str]) -> Dict[str, str]:
        """Initialize or get chunks from shared memory, with fallback"""
        chunks_dict = cls._files_commit_hashes
        if repo_path in chunks_dict:
            return chunks_dict[repo_path]

        return await cls._fetch_and_store_chunks(repo_path, ripgrep_path=ripgrep_path)

    @classmethod
    async def update_chunks(
        cls,
        repo_path: str,
        chunks: Optional[Dict[str, str]] = None,
        chunkable_files: Optional[List[str]] = None,
    ) -> None:
        chunks_dict = cls._files_commit_hashes or {}
        if repo_path in chunks_dict and chunkable_files:
            existing_chunks = chunks_dict[repo_path]

            # updated chunkable file hash map
            for file_path, file_hash in chunks.items():
                existing_chunks[file_path] = file_hash

            chunks_dict[repo_path] = existing_chunks
        else:
            if chunks is not None:
                chunks_dict[repo_path] = chunks

    @classmethod
    async def _fetch_and_store_chunks(cls, repo_path: str, ripgrep_path: Optional[str] = None) -> Dict[str, str]:
        """Fetch chunks from repo and store in shared memory"""
        local_repo = LocalRepoFactory.get_local_repo(repo_path, ripgrep_path=ripgrep_path)
        chunks = await local_repo.get_chunkable_files_and_commit_hashes()
        cls._files_commit_hashes[repo_path] = chunks
        return chunks
