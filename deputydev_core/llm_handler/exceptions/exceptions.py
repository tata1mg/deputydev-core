class RetryException(Exception):  # noqa : N818
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Retrying event: {self.message}")


class ParseException(Exception):  # noqa : N818
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Parsing error: {self.message}")


class InvalidIntegrationClient(Exception):  # noqa: N818
    """
    Exception raised for invalid integration client errors.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Invalid Integration Client: {self.message}")


class RefreshTokenFailed(Exception):  # noqa: N818
    """
    Exception raised when refreshing tokens fails.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Error Refreshing Tokens: {self.message}")


class CredentialsError(Exception):
    """
    Exception raised for credential-related errors.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Credentials Error: {self.message}")


class TeamNotFound(Exception):  # noqa : N818
    """
    Exception raised when a team is not found.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Team Not Found: {self.message}")


class OnboardingError(Exception):
    """
    Exception raised for errors during onboarding.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Onboarding Error: {self.message}")


class SignUpError(Exception):
    """
    Exception raised for errors during sign-up.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Sign-Up Error: {self.message}")


class RateLimitError(Exception):
    """
    Exception raised for errors during vcs rate limit is reached
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Rate limit error: {self.message}")


class InputTokenLimitExceededError(Exception):
    """
    Raised when input tokens exceed the model's token limit.
    """

    def __init__(
        self,
        model_name: str,
        current_tokens: int,
        max_tokens: int,
        detail: str | None = None,
    ) -> None:
        super().__init__(f"Input token limit exceeded for {model_name}: {current_tokens} > {max_tokens}")
        self.model_name = model_name
        self.current_tokens = current_tokens
        self.max_tokens = max_tokens
        self.detail = detail
