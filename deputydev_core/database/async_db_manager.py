import asyncio
import json
from asyncio import Lock
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Type

import aiosqlite
import orjson
from cachetools import TTLCache

from deputydev_core.models.dto.sqlite_file_chunk_dto import ChunkDTO, FileDTO
from deputydev_core.utils.app_logger import AppLogger


class AsyncDBManager:
    def __init__(self, use_memory: bool = False) -> None:
        self.database_dir = Path.home() / ".deputydev" / "sqlite"
        self.database_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.database_dir / "code_index.sqlite"
        self.use_memory = use_memory
        self._lock: Lock = Lock()  # ✅ type-safe annotation

        self.conn: aiosqlite.Connection | None = None

        self._repo_chunks_cache = TTLCache(maxsize=32, ttl=10)
        self._repo_files_cache = TTLCache(maxsize=32, ttl=10)
        self._cache_lock = asyncio.Lock()

    async def __aenter__(self) -> "AsyncDBManager":
        # Always open SQLite connection (in-memory or default file if extended later)
        self.conn = await aiosqlite.connect(":memory:" if self.use_memory else "code_index.sqlite")
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()

        # Optional load from disk — disabled by default to avoid deadlocks
        # if self.use_memory:
        #     await self._load_from_disk()  # noqa: ERA001
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        await self.close()

    def _require_conn(self) -> aiosqlite.Connection:
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized.")
        return self.conn

    # ==============================================================
    # Schema Setup
    # ==============================================================
    async def _create_tables(self) -> None:
        conn = self._require_conn()
        await conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_path TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                language TEXT,
                num_lines INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME,
                metadata_json TEXT
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER NOT NULL,
                node_name TEXT,
                node_type TEXT,
                category TEXT,
                start_line INTEGER,
                end_line INTEGER,
                parent_name TEXT,
                parent_type TEXT,
                metadata_json TEXT,
                FOREIGN KEY (file_id) REFERENCES files (id)
            );

            -- ✅ Add indexes for faster lookups & joins
            CREATE INDEX IF NOT EXISTS idx_files_repo_path ON files (repo_path);
            """
        )
        await conn.commit()

    # ==============================================================
    # Persistence
    # ==============================================================
    async def _load_from_disk(self) -> None:
        conn = self._require_conn()
        async with aiosqlite.connect(self.db_path) as disk_conn:
            await disk_conn.backup(conn)
        AppLogger.log_info("📂 Loaded database from disk")

    async def save_to_disk(self) -> None:
        if not self.use_memory:
            return
        conn = self._require_conn()
        async with aiosqlite.connect(self.db_path) as disk_conn:
            await conn.backup(disk_conn)
        AppLogger.log_info("💾 Saved in-memory DB to disk")

    # ==============================================================
    # CRUD Methods
    # ==============================================================
    async def insert_file(self, file: FileDTO) -> Optional[int]:
        data = file.model_dump(exclude_unset=True)
        metadata = orjson.dumps(data.pop("metadata_json", {})).decode()
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            INSERT INTO files (repo_path, file_path, file_name, file_hash, language, num_lines, metadata_json)
            VALUES (:repo_path, :file_path, :file_name, :file_hash, :language, :num_lines, :metadata_json)
        """,
            {**data, "metadata_json": metadata},
        )
        lastrowid = cursor.lastrowid
        await cursor.close()
        return lastrowid

    async def insert_chunk(self, chunk: ChunkDTO) -> Optional[int]:
        data = chunk.model_dump(exclude_unset=True)
        metadata = orjson.dumps(data.pop("metadata_json", {})).decode()
        conn = self._require_conn()
        cursor = await conn.execute(
            """
            INSERT INTO chunks (
                file_id, node_name, node_type, category,
                start_line, end_line, parent_name, parent_type, metadata_json
            )
            VALUES (
                :file_id, :node_name, :node_type, :category,
                :start_line, :end_line, :parent_name, :parent_type, :metadata_json
            )
        """,
            {**data, "metadata_json": metadata},
        )
        lastrowid = cursor.lastrowid
        await conn.commit()
        return lastrowid

    async def get_all_chunks_from_repo(self, repo_path: str) -> list[tuple[ChunkDTO, FileDTO]]:
        # ✅ Step 1: Check cache
        async with self._cache_lock:
            if repo_path in self._repo_chunks_cache:
                return self._repo_chunks_cache[repo_path]

        conn = self._require_conn()
        cursor = await conn.execute(
            """
            SELECT
                c.id            AS chunk_id,
                c.file_id       AS chunk_file_id,
                c.node_name     AS chunk_node_name,
                c.category      AS chunk_category,
                c.start_line    AS chunk_start_line,
                c.end_line      AS chunk_end_line,
                f.id            AS file_id,
                f.repo_path     AS file_repo_path,
                f.file_path     AS file_path,
                f.file_name     AS file_name,
                f.file_hash     AS file_hash
            FROM chunks c
            INNER JOIN files f ON c.file_id = f.id
            WHERE f.repo_path = ?
            ORDER BY f.file_path, c.start_line
            """,
            (repo_path,),
        )
        rows = await cursor.fetchall()
        await cursor.close()

        results: list[tuple[ChunkDTO, FileDTO]] = []
        for row in rows:
            data = dict(row)

            chunk_dict = {
                "id": data["chunk_id"],
                "file_id": data["chunk_file_id"],
                "node_name": data["chunk_node_name"],
                "category": data["chunk_category"],
                "start_line": data["chunk_start_line"],
                "end_line": data["chunk_end_line"],
            }
            file_dict = {
                "id": data["file_id"],
                "repo_path": data["file_repo_path"],
                "file_path": data["file_path"],
                "file_name": data["file_name"],
                "file_hash": data["file_hash"],
            }

            results.append((ChunkDTO(**chunk_dict), FileDTO(**file_dict)))
        # ✅ Step 2: Store in cache
        async with self._cache_lock:
            self._repo_chunks_cache[repo_path] = results
        return results

    async def get_chunks_for_file(self, file_id: int) -> List[ChunkDTO]:
        conn = self._require_conn()
        cursor = await conn.execute("SELECT * FROM chunks WHERE file_id = ?", (file_id,))
        rows = await cursor.fetchall()
        await cursor.close()
        return [ChunkDTO(**dict(r)) for r in rows]

    async def update_last_used(self, file_id: int) -> None:
        conn = self._require_conn()
        await conn.execute(
            "UPDATE files SET last_used = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), file_id),
        )
        await conn.commit()

    async def get_all_files(self) -> list[FileDTO]:
        conn = self._require_conn()
        cursor = await conn.execute("SELECT * FROM files")
        rows = await cursor.fetchall()
        await cursor.close()
        return [FileDTO(**self._deserialize_metadata(r)) for r in rows]

    async def get_all_files_from_repo(self, repo_path: str) -> list[FileDTO]:
        # ✅ Step 1: Check cache
        async with self._cache_lock:
            if repo_path in self._repo_files_cache:
                return self._repo_files_cache[repo_path]

        # ✅ Step 2: Query database
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT * FROM files WHERE repo_path = ?",
            (repo_path,),
        )
        rows = await cursor.fetchall()
        await cursor.close()

        result = [FileDTO(**self._deserialize_metadata(r)) for r in rows]

        # ✅ Step 3: Cache the result
        async with self._cache_lock:
            self._repo_files_cache[repo_path] = result

        return result

    async def delete_files_from_repo_filtered(self, repo_path: str, files_filter: list[str]) -> None:
        """
        Delete all files (and their associated chunks) from a repo
        whose file_path is in files_filter.
        """
        if not files_filter:
            return  # nothing to do

        conn = self._require_conn()

        # Create placeholders (?, ?, ?) dynamically
        placeholders = ",".join("?" for _ in files_filter)

        # Get file IDs for those paths (so we can delete related chunks too)
        cursor = await conn.execute(
            f"""
            SELECT id FROM files
            WHERE repo_path = ?
              AND file_path IN ({placeholders})
            """,
            (repo_path, *files_filter),
        )
        rows = await cursor.fetchall()
        await cursor.close()

        if not rows:
            AppLogger.log_info("ℹ️ No matching files found for deletion.")
            return
        file_ids = [r["id"] for r in rows]
        placeholders = ",".join("?" for _ in file_ids)
        await conn.execute(f"DELETE FROM chunks WHERE file_id IN ({placeholders})", file_ids)
        await conn.execute(f"DELETE FROM files WHERE id IN ({placeholders})", file_ids)

        await conn.commit()
        AppLogger.log_info(f"🗑️ Deleted {len(file_ids)} files (and their chunks) from repo '{repo_path}'")

    async def delete_file(self, file_id: int) -> None:
        conn = self._require_conn()
        await conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
        await conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        await conn.commit()

    async def delete_files(self, file_ids: List[int]) -> None:
        """Delete multiple files (and their chunks) by IDs."""
        if not file_ids:
            return
        placeholders = ",".join("?" for _ in file_ids)
        conn = self._require_conn()
        # Delete chunks first (to maintain FK consistency)
        await conn.execute(f"DELETE FROM chunks WHERE file_id IN ({placeholders})", file_ids)
        await conn.execute(f"DELETE FROM files WHERE id IN ({placeholders})", file_ids)
        await conn.commit()
        AppLogger.log_info(f"🗑️ Deleted {len(file_ids)} files and related chunks")

    async def delete_chunks_by_file(self, file_id: int) -> None:
        conn = self._require_conn()
        await conn.execute("DELETE FROM chunks WHERE file_id = ?", (file_id,))
        await conn.commit()

    async def update_file_hash(self, file_id: int, new_hash: str) -> None:
        conn = self._require_conn()
        await conn.execute(
            "UPDATE files SET file_hash = ?, last_used = ? WHERE id = ?",
            (new_hash, datetime.now(timezone.utc).isoformat(), file_id),
        )
        await conn.commit()

    # ==============================================================
    # Cleanup
    # ==============================================================
    async def close(self) -> None:
        if self.conn is None:
            return
        await self.conn.close()
        self.conn = None

    @staticmethod
    def _deserialize_metadata(row: aiosqlite.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        row_dict = dict(row)
        metadata = row_dict.get("metadata_json")
        if isinstance(metadata, str):
            try:
                row_dict["metadata_json"] = orjson.loads(metadata)
            except json.JSONDecodeError:
                row_dict["metadata_json"] = {}
        return row_dict
