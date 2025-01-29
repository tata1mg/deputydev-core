from typing import Any, Dict, Optional

from clients.base_http_client import BaseHTTPClient
from utils.initialization_constants import (
    APP_VERSION,
    HOST,
    LIMIT,
    LIMIT_PER_HOST,
    TIMEOUT,
    TTL_DNS_CACHE,
)
from utils.exceptions import InvalidVersionException


class OneDevClient(BaseHTTPClient):
    """
    Class to handle all the inter service requests to OneDev service
    """

    def __init__(self, host_and_timeout: Optional[Dict[str, Any]] = None):
        self._host: str = host_and_timeout["HOST"] if host_and_timeout is not None else HOST
        super().__init__(
            timeout=host_and_timeout["TIMEOUT"] if host_and_timeout is not None else TIMEOUT,
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
            if parsed_response.get("meta") and parsed_response["meta"]["error_code"] == 101:
                raise InvalidVersionException(message=parsed_response["error"]["message"])
        return response

    async def generate_code(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        path = "/end_user/v1/generate-code"
        result = await self.post(self._host + path, json=payload, headers=headers)
        return (await result.json()).get("data")

    async def generate_docs(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        path = "/end_user/v1/generate-docs"
        result = await self.post(url=self._host + path, json=payload, headers=headers)
        return (await result.json()).get("data")

    async def generate_test_cases(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        path = "/end_user/v1/generate-test-cases"
        result = await self.post(url=self._host + path, json=payload, headers=headers)
        return (await result.json()).get("data")

    async def generate_code_plan(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        path = "/end_user/v1/generate-code-plan"
        result = await self.post(url=self._host + path, json=payload, headers=headers)
        return (await result.json()).get("data")

    async def generate_diff(self, payload: Optional[Dict[str, Any]], headers: Dict[str, str]) -> Dict[str, Any]:
        path = "/end_user/v1/generate-diff"
        result = await self.post(url=self._host + path, json=payload, headers=headers)
        return (await result.json()).get("data")

    async def iterative_chat(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        path = "/end_user/v1/iterative-chat"
        result = await self.post(url=self._host + path, json=payload, headers=headers)
        return (await result.json()).get("data")

    async def record_feedback(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        path = "/end_user/v1/record-feedback"
        result = await self.post(url=self._host + path, json=payload, headers=headers)
        return (await result.json()).get("data")

    async def plan_to_code(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        path = "/end_user/v1/plan-code-generation"
        result = await self.post(url=self._host + path, json=payload, headers=headers)
        return (await result.json()).get("data")

    async def get_registered_repo_details(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        path = "/end_user/v1/get-registered-repo-details"
        result = await self.get(url=self._host + path, headers=headers, params=payload)
        return (await result.json()).get("data")

    async def get_job_status(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        path = "/end_user/v1/get-job-status"
        result = await self.get(url=self._host + path, headers=headers, params=payload)
        return (await result.json()).get("data")

    async def create_embedding(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        path = "/end_user/v1/create-embedding"
        result = await self.post(url=self._host + path, json=payload, headers=headers)
        return (await result.json()).get("data")

    async def verify_auth_token(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        path = "/end_user/v1/verify-auth-token"
        result = await self.post(url=self._host + path, json=payload, headers=headers)
        return (await result.json()).get("data")

    async def get_configs(self, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        path = "/end_user/v1/get-configs"
        result = await self.get(url=self._host + path, headers=headers)
        return (await result.json()).get("data")
