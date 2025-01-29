import asyncio
import os
from typing import Dict, List, Optional
from uuid import uuid4

import git

from utils.base_local_repo import BaseLocalRepo


class GitRepo(BaseLocalRepo):
    def __init__(self, repo_path: str):
        super().__init__(repo_path)
        self.repo = git.Repo(repo_path)

    def get_origin_remote_url(self) -> str:
        for remote in self.repo.remotes:
            if remote.name == "origin":
                return remote.url
        raise ValueError("Origin remote not found")

    def get_repo_name(self):
        return os.path.splitext(os.path.basename(self.get_origin_remote_url()))[0]

    def branch_list(self) -> List[str]:
        return [branch.name for branch in self.repo.branches]

    def branch_exists(self, branch_name: str) -> bool:
        return branch_name in self.branch_list()

    def get_vcs_type(self):
        remote_url = self.get_origin_remote_url()
        return "bitbucket" if "bitbucket" in remote_url else "github"

    def get_active_branch(self) -> str:
        return self.repo.active_branch.name

    def checkout_branch(self, branch_name: str):
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
            status_without_xy = status[3:]
            if "->" in status:
                first_file = status_without_xy.split("->")[0].strip()
                second_file = status_without_xy.split("->")[1].strip()
                modified_files.extend([first_file, second_file])
            else:
                modified_files.append(status_without_xy)

        return modified_files

    async def _get_all_files_and_hashes_on_last_commit(self) -> Dict[str, str]:
        """Get all files on a tracked commit."""
        process = await asyncio.create_subprocess_exec(
            "git",
            "ls-tree",
            "-r",
            "--format=%(objecttype) %(objectname) %(path)",
            "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.repo_path,
        )
        stdout, _ = await process.communicate()
        all_ls_tree_files = stdout.decode().splitlines()

        files_and_hashes: Dict[str, str] = {}
        for file in all_ls_tree_files:
            file = file.split(" ")
            if file[0] == "blob" and self._is_file_chunkable(file[2]):
                files_and_hashes[file[2]] = file[1]
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

        # remove all modified files from all_files_and_hashes
        for file in modified_files:
            all_files_and_hashes.pop(file, None)

            if not self._is_file_chunkable(file):
                continue

            # check if the file is on the disk, and if yes, get a content hash for it
            if os.path.exists(os.path.join(self.repo_path, file)):
                all_files_and_hashes[file] = self._get_file_hash(file)

        return all_files_and_hashes

    async def get_chunkable_files(self) -> List[str]:
        files_with_hashes = await self.get_chunkable_files_and_commit_hashes()
        return list(files_with_hashes.keys())

    def stage_changes(self):
        self.repo.git.add(".")

    def commit_changes(self, commit_message: str, actor: Optional[git.Actor] = None):  # type: ignore
        self.repo.index.commit(message=commit_message, author=actor)

    async def push_to_remote(self, branch_name: str, remote_repo_url: str):
        selected_remote = next((remote for remote in self.repo.remotes if remote.url == remote_repo_url), None)
        if not selected_remote:
            selected_remote = self.repo.create_remote(name=uuid4().hex, url=remote_repo_url)

        await asyncio.to_thread(selected_remote.push, refspec=branch_name)

    async def sync_with_remote(self, branch_name: str, remote_repo_url: str):
        # get the remote
        selected_remote = next((remote for remote in self.repo.remotes if remote.url == remote_repo_url), None)
        if not selected_remote:
            selected_remote = self.repo.create_remote(name=uuid4().hex, url=remote_repo_url)
        await asyncio.to_thread(self.repo.git.pull, selected_remote.name, branch_name)

    def is_branch_available_on_remote(self, branch_name: str, remote_repo_url: str) -> bool:
        selected_remote = next((remote for remote in self.repo.remotes if remote.url == remote_repo_url), None)
        if not selected_remote:
            selected_remote = self.repo.create_remote(name=uuid4().hex, url=remote_repo_url)

        remote_branches = [ref.name.split("/")[-1] for ref in selected_remote.refs]
        return branch_name in remote_branches
