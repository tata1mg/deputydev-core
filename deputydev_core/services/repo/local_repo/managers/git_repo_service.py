import asyncio
import traceback
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from git.remote import Remote
from git.repo import Repo
from git.util import Actor
from giturlparse import parse as parse_git_url  # type: ignore

from deputydev_core.services.repo.local_repo.base_local_repo_service import (
    BaseLocalRepo,
)
from deputydev_core.utils.app_logger import AppLogger


class GitRepo(BaseLocalRepo):
    def __init__(self, repo_path: str, chunkable_files: Optional[List[str]] = None) -> None:
        super().__init__(repo_path, chunkable_files=chunkable_files)
        self.repo = Repo(repo_path)

    def _find_existing_remote(self, remote_url: str) -> Optional[Remote]:
        try:
            parsed_remote_url_to_match: Dict[str, str] = parse_git_url(remote_url).data  # type: ignore
            for remote in self.repo.remotes:
                parsed_exitsting_remote_url: Dict[str, str] = parse_git_url(remote.url).data  # type: ignore
                if (
                    (
                        parsed_remote_url_to_match["host"].split("@")[-1]
                        == parsed_exitsting_remote_url["host"].split("@")[-1]
                    )
                    and (parsed_remote_url_to_match["owner"] == parsed_exitsting_remote_url["owner"])
                    and (parsed_remote_url_to_match["repo"] == parsed_exitsting_remote_url["repo"])
                ):
                    return remote
        except Exception:  # noqa: BLE001
            AppLogger.log_debug(traceback.format_exc())
        return None

    def get_origin_remote_url(self) -> str:
        for remote in self.repo.remotes:
            if remote.name == "origin":
                return remote.url
        raise ValueError("Origin remote not found")

    def get_repo_name(self) -> str:
        return Path(self.get_origin_remote_url()).stem

    def branch_list(self) -> List[str]:
        return [branch.name for branch in self.repo.branches]

    def branch_exists(self, branch_name: str) -> bool:
        return branch_name in self.branch_list()

    def get_vcs_type(self) -> str:
        remote_url = self.get_origin_remote_url()
        return "bitbucket" if "bitbucket" in remote_url else "github"

    def get_active_branch(self) -> str:
        return self.repo.active_branch.name

    def checkout_branch(self, branch_name: str) -> None:
        if branch_name not in self.branch_list():
            self.repo.git.branch(branch_name)

        current = self.get_active_branch()
        if current != branch_name:
            self.repo.git.checkout(branch_name)

    async def get_modified_or_renamed_files(self) -> List[str]:
        """Fetch list of modified/renamed files using git diff."""
        process = await asyncio.create_subprocess_exec(
            "git",
            "status",
            "--short",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.repo_path,
        )
        stdout, _ = await process.communicate()
        all_statuses = stdout.decode().splitlines()

        # short status format: <XY> <filename> or <XY> <filename> -> <filename>
        # where X is the status of the first file and Y is the status of the second file
        # we ignore XY and only consider the filenames

        modified_files: List[str] = []
        for status in all_statuses:
            # Split into [XY, rest]
            parts = status.split(None, 1)
            if len(parts) < 2:
                continue
            path_info = parts[1]
            # Check for rename or copy (contains '->')
            if "->" in path_info:
                # Only take the new file path after '->'
                new_file = path_info.split("->", 1)[1].strip()
                modified_files.append(new_file)
            else:
                modified_files.append(path_info.strip())

        return modified_files

    async def _get_all_files_and_hashes_on_last_commit(self) -> Dict[str, str]:
        """Get all files on a tracked commit."""
        process = await asyncio.create_subprocess_exec(
            "git",
            "ls-tree",
            "-r",
            "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.repo_path,
        )
        stdout, _ = await process.communicate()
        all_ls_tree_files = stdout.decode().splitlines()

        files_and_hashes: Dict[str, str] = {}
        for file in all_ls_tree_files:
            file = file.split(None, 3)  # splits by whitespace, up to 4 fields
            if len(file) == 4 and file[1] == "blob" and self._is_file_chunkable(file[3]):
                files_and_hashes[file[3]] = file[2]
        return files_and_hashes

    async def get_chunkable_files_and_commit_hashes(self) -> Dict[str, str]:
        """Get files not modified/renamed and their last commit hashes."""
        # Step 2: Get the list of modified/renamed files via 'git diff'

        tasks = [
            self.get_modified_or_renamed_files(),
            self._get_all_files_and_hashes_on_last_commit(),
        ]

        task_results = await asyncio.gather(*tasks)
        modified_files: List[str] = task_results[0]  # type: ignore
        all_files_and_hashes: Dict[str, str] = task_results[1]  # type: ignore
        # filter non required files
        if self.chunkable_files:
            all_files_and_hashes = {k: v for k, v in all_files_and_hashes.items() if k in self.chunkable_files}
            modified_files = list(set(modified_files) & set(self.chunkable_files))
        # remove all modified files from all_files_and_hashes
        for file in modified_files:
            all_files_and_hashes.pop(file, None)

            if not self._is_file_chunkable(file):
                continue
            file_path = Path(self.repo_path) / file
            if file_path.exists():
                # check if the file is on the disk, and if yes, get a content hash for it
                all_files_and_hashes[file] = self._get_file_hash(file)

        return all_files_and_hashes

    async def get_chunkable_files(self) -> List[str]:
        files_with_hashes = await self.get_chunkable_files_and_commit_hashes()
        return list(files_with_hashes.keys())

    def stage_changes(self) -> None:
        self.repo.git.add(".")

    def commit_changes(self, commit_message: str, actor: Optional[Actor] = None) -> None:  # type: ignore
        self.repo.index.commit(message=commit_message, author=actor)

    async def push_to_remote(self, branch_name: str, remote_repo_url: str) -> None:
        selected_remote = self._find_existing_remote(remote_url=remote_repo_url)
        if not selected_remote:
            selected_remote = self.repo.create_remote(name=uuid4().hex, url=remote_repo_url)

        await asyncio.to_thread(selected_remote.push, refspec=branch_name)

    async def sync_with_remote(self, branch_name: str, remote_repo_url: str) -> None:
        # get the remote
        selected_remote = self._find_existing_remote(remote_url=remote_repo_url)
        if not selected_remote:
            selected_remote = self.repo.create_remote(name=uuid4().hex, url=remote_repo_url)
        await asyncio.to_thread(self.repo.git.pull, selected_remote.name, branch_name)

    def is_branch_available_on_remote(self, branch_name: str, remote_repo_url: str) -> bool:
        selected_remote = self._find_existing_remote(remote_url=remote_repo_url)
        if not selected_remote:
            selected_remote = self.repo.create_remote(name=uuid4().hex, url=remote_repo_url)
            selected_remote.fetch()

        remote_branches = [ref.name.split("/")[-1] for ref in selected_remote.refs]
        return branch_name in remote_branches
