import logging
import pickle
from multiprocessing import Lock, shared_memory
from typing import Dict, List, Optional

from deputydev_core.services.repo.local_repo.local_repo_factory import LocalRepoFactory

logger = logging.getLogger(__name__)


class SharedChunksManager:
    _shm_name = "chunkable_files_shm"
    _lock = Lock()

    @classmethod
    async def initialize_chunks(cls, repo_path: str) -> Dict[str, str]:
        """Initialize or get chunks from shared memory, with fallback"""
        chunks_dict = cls.get_chunks()
        if chunks_dict is not None and repo_path in chunks_dict:
            return chunks_dict[repo_path]

        # fallback case
        # repo_path = "/Users/ankitrana/projects/merch_service"
        return await cls._fetch_and_store_chunks(repo_path)

    @classmethod
    async def update_chunks(
        cls,
        repo_path: str,
        chunks: Optional[Dict] = None,
        chunkable_files: Optional[List[str]] = None,
    ):
        """Update chunks in shared memory"""
        with cls._lock:
            chunks_dict = cls.get_chunks() or {}
            if repo_path in chunks_dict and chunkable_files:
                existing_chunks = chunks_dict[repo_path]

                # updated chunkable file hash map
                for file_path, file_hash in chunks.items():
                    existing_chunks[file_path] = file_hash

                chunks_dict[repo_path] = existing_chunks
            else:
                chunks_dict[repo_path] = chunks

            cls.store_chunks(chunks_dict)

    @classmethod
    async def _fetch_and_store_chunks(cls, repo_path: str) -> Dict[str, str]:
        """Fetch chunks from repo and store in shared memory"""
        with cls._lock:
            local_repo = LocalRepoFactory.get_local_repo(repo_path)
            chunks = await local_repo.get_chunkable_files_and_commit_hashes()
            cls.store_chunks(chunks)
            return chunks

    @classmethod
    def store_chunks(cls, data: Dict) -> None:
        """Store chunks dictionary in shared memory"""
        data_bytes = pickle.dumps(data)
        try:
            existing_shm = shared_memory.SharedMemory(name=cls._shm_name, create=False)
            existing_shm.close()
            existing_shm.unlink()

        except FileNotFoundError:
            pass

        # Create new shared memory block
        shm = shared_memory.SharedMemory(
            create=True, size=len(data_bytes), name=cls._shm_name
        )
        shm.buf[: len(data_bytes)] = data_bytes
        shm.close()

    @classmethod
    def get_chunks(cls) -> Optional[Dict[str, Dict[str, str]]]:
        """Get chunks dictionary from shared memory"""
        try:
            shm = shared_memory.SharedMemory(name=cls._shm_name, create=False)
            data = pickle.loads(bytes(shm.buf))
            shm.close()
            return data
        except FileNotFoundError:
            return None
        except Exception as e:
            return None

    @classmethod
    def cleanup_shared_memory(cls) -> None:
        """Safely free the shared memory block"""
        try:
            shm = shared_memory.SharedMemory(name=cls._shm_name, create=False)
            shm.unlink()
            shm.close()
            # Optional: log it
            logger.info(f"Shared memory '{cls._shm_name}' unlinked and closed successfully.")
        except FileNotFoundError:
            # Memory already deleted
            logger.warning(f"Shared memory '{cls._shm_name}' not found during cleanup.")
        except Exception as e:
            logger.error(f"Error during shared memory cleanup: {e}")
