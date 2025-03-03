from typing import Any, Dict, Optional

from deputydev_core.clients.http.base_http_client import BaseHTTPClient
from deputydev_core.clients.http.service_clients.constants import (
    HOST,
    LIMIT,
    LIMIT_PER_HOST,
    TIMEOUT,
    TTL_DNS_CACHE,
)
from deputydev_core.utils.constants.constants import APP_VERSION
from deputydev_core.utils.exceptions import InvalidVersionException


class OneDevClient(BaseHTTPClient):
    """
    Class to handle all the inter service requests to OneDev service
    """

    def __init__(self, host_and_timeout: Optional[Dict[str, Any]] = None):
        self._host: str = (
            host_and_timeout["HOST"] if host_and_timeout is not None else HOST
        )
        super().__init__(
            timeout=(
                host_and_timeout["TIMEOUT"] if host_and_timeout is not None else TIMEOUT
            ),
            limit=LIMIT,
            limit_per_host=LIMIT_PER_HOST,
            ttl_dns_cache=TTL_DNS_CACHE,
        )

    def build_common_headers(self, headers):
        headers = headers or {}
        headers.update({"x-cli-app-version": APP_VERSION})
        return headers

    async def request(
            self,
            method: str,
            url: str,
            params: Optional[Dict[str, str]] = None,
            headers: Optional[Dict[str, str]] = None,
            data: Optional[Dict[str, Any]] = None,
            json: Optional[Dict[str, Any]] = None,
            skip_auth_headers: bool = False,
    ):
        headers = self.build_common_headers(headers)
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
        parsed_response = await response.json()
        if parsed_response["status_code"] == 400:
            if (
                    parsed_response.get("meta")
                    and parsed_response["meta"]["error_code"] == 101
            ):
                raise InvalidVersionException(
                    message=parsed_response["error"]["message"]
                )
        return response

    async def create_embedding(
            self, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        raise NotImplementedError()
