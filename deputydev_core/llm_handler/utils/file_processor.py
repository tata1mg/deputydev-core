import base64


def get_base64_file_content(file_data: bytes) -> str:
    """
    Convert file data to base64 string
    """
    return base64.b64encode(file_data).decode("utf-8")
