from git import InvalidGitRepositoryError, Repo

from repo.local_repo.base_local_repo import BaseLocalRepo
from repo.local_repo.managers.git_repo import GitRepo
from repo.local_repo.managers.non_vcs_repo import NonVCSRepo


class LocalRepoFactory:
    @classmethod
    def _is_git_repo(cls, repo_path: str) -> bool:
        try:
            Repo(path=repo_path)
            return True
        except InvalidGitRepositoryError:
            return False

    @classmethod
    def get_local_repo(cls, repo_path: str) -> BaseLocalRepo:
        if cls._is_git_repo(repo_path):
            return GitRepo(repo_path)
        return NonVCSRepo(repo_path)
