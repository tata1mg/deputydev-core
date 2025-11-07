from typing import Dict, List, Tuple

from deputydev_core.models.dto.sqlite_file_chunk_dto import FileDTO


def diff_repo_and_db(
    repo_file_hash_map: Dict[str, str],
    db_files: List[FileDTO],
) -> Tuple[List[str], List[str], List[str]]:
    """
    Compare repo files (with hashes) vs DB files and detect:
    - to_insert: files not in DB
    - to_update: files in DB but hash changed
    - to_delete: files in DB but missing from repo

    Args:
        repo_file_hash_map: {relative_path: sha256_hash}
        db_files: list of FileDTO objects currently in DB

    Returns:
        (to_insert, to_update, to_delete)
    """
    db_map = {f.file_path: f.file_hash for f in db_files}
    repo_map = repo_file_hash_map

    to_insert: List[str] = []
    to_update: List[str] = []
    to_delete: List[str] = []

    # --- Detect new and updated files ---
    for file_path, hash_value in repo_map.items():
        db_hash = db_map.get(file_path)
        if db_hash is None:
            to_insert.append(file_path)
        elif db_hash != hash_value:
            to_update.append(file_path)

    # --- Detect deleted files ---
    for file_path in db_map.keys():
        if file_path not in repo_map:
            to_delete.append(file_path)

    return to_insert, to_update, to_delete
