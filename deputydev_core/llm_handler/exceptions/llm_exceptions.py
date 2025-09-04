class LLMThrottledError(RuntimeError):
    """
    Raised when the upstream LLM returns a rate-limit / quota error.
    Subclassed for provider-specific throttling.
    """

    def __init__(
        self,
        provider: str,
        model: str | None = None,
        region: str | None = None,
        retry_after: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(f"{provider} throttled")
        self.provider = provider
        self.model = model
        self.region = region
        self.retry_after = retry_after
        self.detail = detail or ""


class AnthropicThrottledError(LLMThrottledError):
    """
    Throttling/rate limit error from Anthropic (Amazon Bedrock).
    """

    def __init__(
        self,
        model: str | None = None,
        region: str | None = None,
        retry_after: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(provider="anthropic", model=model, region=region, retry_after=retry_after, detail=detail)


class GeminiThrottledError(LLMThrottledError):
    """
    Throttling/rate limit error from Google Gemini.
    """

    def __init__(
        self,
        model: str | None = None,
        region: str | None = None,
        retry_after: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(provider="gemini", model=model, region=region, retry_after=retry_after, detail=detail)


class OpenAIThrottledError(LLMThrottledError):
    """
    Throttling/rate limit error from OpenAI.
    """

    def __init__(
        self,
        model: str | None = None,
        region: str | None = None,
        retry_after: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(provider="openai", model=model, region=region, retry_after=retry_after, detail=detail)
