import shutil
from typing import List, Optional

from git import InvalidGitRepositoryError, Repo

from deputydev_core.services.repo.local_repo.base_local_repo_service import (
    BaseLocalRepo,
)
from deputydev_core.services.repo.local_repo.managers.git_repo_service import GitRepo
from deputydev_core.services.repo.local_repo.managers.non_vcs_repo_service import (
    NonVCSRepo,
)


class LocalRepoFactory:
    @classmethod
    def is_git_installed(cls) -> bool:
        return shutil.which("git") is not None

    @classmethod
    def is_git_repo(cls, repo_path: str) -> bool:
        if not cls.is_git_installed():
            return False
        try:
            Repo(path=repo_path)
            return True

        except InvalidGitRepositoryError:
            return False

    @classmethod
    def get_local_repo(
        cls, repo_path: str, chunkable_files: Optional[List[str]] = None, ripgrep_path: Optional[str] = None
    ) -> BaseLocalRepo:
        if ripgrep_path:
            return NonVCSRepo(repo_path, chunkable_files=chunkable_files, ripgrep_path=ripgrep_path)

        if cls.is_git_repo(repo_path):
            return GitRepo(repo_path, chunkable_files=chunkable_files)

        return NonVCSRepo(repo_path, chunkable_files=chunkable_files, ripgrep_path=ripgrep_path)
