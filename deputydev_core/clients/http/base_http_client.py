from typing import Any, Dict, Optional

from deputydev_core.clients.http.adapters.http_response_adapter import (
    AiohttpToRequestsAdapter,
)
from deputydev_core.clients.http.base_http_session_manager import SessionManager


class BaseHTTPClient:
    def __init__(
        self,
        timeout: Optional[int] = None,
        limit: Optional[int] = None,
        limit_per_host: Optional[int] = None,
        ttl_dns_cache: Optional[int] = None,
    ) -> None:
        self._session_manager = SessionManager(limit=limit, limit_per_host=limit_per_host, ttl_dns_cache=ttl_dns_cache)
        self._timeout = timeout

    # The following methods are the internal API for the client

    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> AiohttpToRequestsAdapter:
        session = await self._session_manager.get_session()
        request_parameters: Dict[str, Any] = dict(
            method=method, url=url, params=params, headers=headers, data=data, json=json
        )
        if self._timeout:
            request_parameters["timeout"] = self._timeout
        async with session.request(**request_parameters) as response:
            content = await response.read()
            return AiohttpToRequestsAdapter(response, content)

    async def auth_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
        }

    # The following methods are the public API for the client

    async def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        skip_auth_headers: bool = False,
    ) -> AiohttpToRequestsAdapter:
        headers = headers or {}
        if not skip_auth_headers:
            auth_headers = await self.auth_headers()
            headers.update(auth_headers)

        response = await self._request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            data=data,
            json=json,
        )
        return response

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        skip_auth_headers: bool = False,
    ) -> AiohttpToRequestsAdapter:
        return await self.request(
            "GET",
            url,
            params=params,
            headers=headers,
            skip_auth_headers=skip_auth_headers,
        )

    async def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        skip_auth_headers: bool = False,
    ) -> AiohttpToRequestsAdapter:
        return await self.request(
            "POST",
            url,
            params=params,
            headers=headers,
            data=data,
            json=json,
            skip_auth_headers=skip_auth_headers,
        )

    async def put(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        skip_auth_headers: bool = False,
    ) -> AiohttpToRequestsAdapter:
        return await self.request(
            "PUT",
            url,
            headers=headers,
            data=data,
            json=json,
            skip_auth_headers=skip_auth_headers,
        )

    async def patch(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        skip_auth_headers: bool = False,
    ) -> AiohttpToRequestsAdapter:
        return await self.request(
            "PATCH",
            url,
            headers=headers,
            data=data,
            json=json,
            skip_auth_headers=skip_auth_headers,
        )

    async def delete(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        skip_auth_headers: bool = False,
    ) -> AiohttpToRequestsAdapter:
        return await self.request(
            "DELETE",
            url,
            headers=headers,
            data=data,
            json=json,
            skip_auth_headers=skip_auth_headers,
        )

    async def close_session(self) -> None:
        await self._session_manager.close()
