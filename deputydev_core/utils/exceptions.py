class InvalidVersionException(Exception):
    """
    Exception raised for invalid version errors.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str = "Invalid version provided"):
        self.message = message
        super().__init__(self.message)
