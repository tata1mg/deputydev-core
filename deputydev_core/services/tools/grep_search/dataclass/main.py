from typing import List

from pydantic import BaseModel


class GrepSearchRequestParams(BaseModel):
    """
    Request parameters for the GrepSearch.
    """

    directory_path: str
    repo_path: str
    search_terms: List[str] = []
