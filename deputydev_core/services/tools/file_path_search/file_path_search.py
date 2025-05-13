import os
from typing import List, Optional

from fuzzywuzzy import fuzz


class FilePathSearch:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def list_files(
        self,
        directory: str,
        search_terms: Optional[List[str]] = None,
        threshold: int = 70,
    ) -> List[str]:
        """
        List files in a directory that match the search terms.

        Args:
            directory (str): The directory to search in.
            search_terms (List[str]): The search terms to match.
            threshold (int): The threshold for the fuzzy search.

        Returns:
            List[str]: The list of matching files. Only the first 100 files are returned.
        """
        abs_dir_path = self.repo_path
        if directory == "/" or directory == ".":
            directory = ""

        if directory.startswith("/"):
            directory = directory[1:]

        if directory:
            abs_dir_path = os.path.join(abs_dir_path, directory)

        if not os.path.isdir(abs_dir_path):
            abs_dir_path = self.repo_path

        matching_files: List[str] = []

        for root, _, files in os.walk(abs_dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                path_parts = file_path.split(os.sep)

                if search_terms:
                    if any(
                        fuzz.ratio(term.lower(), part.lower()) >= threshold
                        for term in search_terms
                        for part in path_parts
                    ):
                        matching_files.append(os.path.relpath(file_path, self.repo_path))
                else:
                    matching_files.append(os.path.relpath(file_path, self.repo_path))

        return matching_files[:100]
