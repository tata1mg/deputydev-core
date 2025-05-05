from pydantic import BaseModel


class IterativeFileReaderRequestParams(BaseModel):
    """
    Request parameters for the IterativeFileReader.
    """

    file_path: str
    repo_path: str
    start_line: int
    end_line: int
