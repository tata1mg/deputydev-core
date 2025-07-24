from pathlib import Path


def read_file(file_name: str) -> str:
    """
    Reads the content of a file.

    Args:
        file_name (str): The path to the file to be read.

    Returns:
        str: The content of the file.

    Raises:
        SystemExit: If the file cannot be read due to a SystemExit exception.
    """
    try:
        with Path(file_name).open("r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except SystemExit:
        raise SystemExit
    return ""
