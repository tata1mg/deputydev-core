from pydantic import BaseModel


class GrepSearchRequestParams(BaseModel):
    """
    Request parameters for the GrepSearch.
    """

    directory_path: str
    repo_path: str
    search_term: str
    case_insensitive: bool = False
    use_regex: bool = False
