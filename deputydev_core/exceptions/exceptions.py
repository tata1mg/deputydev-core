class RetryException(Exception):  # noqa : N818
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(f"Retrying event: {self.message}")


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
