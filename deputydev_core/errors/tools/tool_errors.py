class HandledToolError(Exception):
    """Base class for all handled tool errors."""

    error_code: str = "DDT400"


class UnhandledToolError(Exception):
    """Base class for all unhandled tool errors."""

    error_code: str = "DDT500"


class InvalidToolParamsError(HandledToolError):
    """Exception raised for invalid tool parameters."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class EmptyToolResponseError(HandledToolError):
    """Exception raised when a tool response is empty."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
