from typing import Any, Dict

from aiohttp import ClientResponse, ClientResponseError


class AiohttpToRequestsAdapter:
    """
    Adapts aiohttp.ClientResponse to match requests.Response interface.
    Allows seamless migration from requests to aiohttp while maintaining
    existing API contracts.
    """

    def __init__(self, aiohttp_response: ClientResponse, content: bytes):
        self._response = aiohttp_response
        self._content = content

    @property
    def status_code(self) -> int:
        """Maps aiohttp status to requests status_code"""
        return self._response.status

    async def json(self) -> Dict[str, Any]:
        """Returns JSON response data"""
        return await self._response.json()

    @property
    def content(self) -> bytes:
        """Returns raw response content"""
        return self._content

    @property
    def text(self) -> str:
        """Returns decoded response content"""
        return self._content.decode()

    @property
    def headers(self) -> Dict[str, str]:
        """Returns response headers"""
        return dict(self._response.headers)

    def raise_for_status(self):
        """Raises HTTPError for 4xx and 5xx responses"""
        if 400 <= self.status_code < 500:
            raise ClientResponseError(
                request_info=self._response.request_info,
                history=self._response.history,
                status=self.status_code,
                message=f"Client Error status code: {self.status_code} Error: {self.text}",
            )
        elif 500 <= self.status_code < 600:
            raise ClientResponseError(
                request_info=self._response.request_info,
                history=self._response.history,
                status=self.status_code,
                message=f"Server Error status code: {self.status_code} Error: {self.text}",
            )
