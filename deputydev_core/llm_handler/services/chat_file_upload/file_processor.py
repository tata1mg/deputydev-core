import base64


class FileProcessor:
    """
    Class to process files into a format readable by LLMs
    """

    @classmethod
    def get_base64_file_content(cls, file_data: bytes) -> str:
        """
        Convert file data to base64 string
        """
        return base64.b64encode(file_data).decode("utf-8")
