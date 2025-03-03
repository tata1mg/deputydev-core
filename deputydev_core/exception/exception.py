class RetryException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(f"Retrying event: {self.message}")


class ParseException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(f"Parsing error: {self.message}")


class RefreshTokenFailed(Exception):
    """
    Exception raised when refreshing tokens fails.
    """

    def __init__(self, message):
        self.message = message
        super().__init__(f"Error Refreshing Tokens: {self.message}")


class InvalidIntegrationClient(Exception):
    """
    Exception raised for invalid integration client errors.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Invalid Integration Client: {self.message}")


class CredentialsError(Exception):
    """
    Exception raised for credential-related errors.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Credentials Error: {self.message}")


class TeamNotFound(Exception):
    """
    Exception raised when a team is not found.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Team Not Found: {self.message}")


class OnboardingError(Exception):
    """
    Exception raised for errors during onboarding.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Onboarding Error: {self.message}")


class SignUpError(Exception):
    """
    Exception raised for errors during sign-up.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Sign-Up Error: {self.message}")


class RateLimitError(Exception):
    """
    Exception raised for errors during vcs rate limit is reached
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Rate limit error: {self.message}")
