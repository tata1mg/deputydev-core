from typing import Optional


class HandledToolError(Exception):
    """Base class for all handled tool errors."""

    error_code: str = "DDT400"
    error_type: str = "HANDLED_TOOL_ERROR"
    error_subtype: Optional[str] = None


class UnhandledToolError(Exception):
    """Base class for all unhandled tool errors."""

    error_code: str = "DDT500"
    error_type: str = "UNHANDLED_TOOL_ERROR"
    error_subtype: Optional[str] = None


class InvalidToolParamsError(HandledToolError):
    """Exception raised for invalid tool parameters."""

    def __init__(self, message: str) -> None:
        super().__init__(message)

    error_subtype: str = "INVALID_TOOL_PARAMS"
    error_code: str = "DDT401"


class EmptyToolResponseError(HandledToolError):
    """Exception raised when a tool response is empty."""

    def __init__(self, message: str) -> None:
        super().__init__(message)

    error_subtype: str = "EMPTY_TOOL_RESPONSE"
    error_code: str = "DDT402"
