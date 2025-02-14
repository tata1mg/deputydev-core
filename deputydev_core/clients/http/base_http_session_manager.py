import asyncio
import ssl
from typing import Optional

import aiohttp
import certifi

from deputydev_core.utils.config_manager import ConfigManager
from deputydev_core.utils.singleton import Singleton


class SessionManager(metaclass=Singleton):
    def __init__(
        self, limit: Optional[int] = None, limit_per_host: Optional[int] = None, ttl_dns_cache: Optional[int] = None
    ):
        self._session: Optional[aiohttp.ClientSession] = None
        self.limit = limit if limit is not None else ConfigManager.configs["AIOHTTP"]["LIMIT"]
        self.limit_per_host = (
            limit_per_host if limit_per_host is not None else ConfigManager.configs["AIOHTTP"]["LIMIT_PER_HOST"]
        )
        self.ttl_dns_cache = (
            ttl_dns_cache if ttl_dns_cache is not None else ConfigManager.configs["AIOHTTP"]["TTL_DNS_CACHE"]
        )

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create shared session"""
        # Make sure the session is tied to the current loop
        # In aiohttp, each session and the TCP connector is bound to exactly one event loop.
        # This limitation makes the HTTP call break with the error event loop is closed.
        # In order to make this thread safe and independent of event loop status, we check the
        # event loop the session is bound to and the current loop. This is especially useful as
        # this is a Singleton class.
        current_loop = asyncio.get_running_loop()
        if self._session and self._session._loop is not current_loop:
            # Discard the session if it's tied to an old loop
            await self._session.close()
            self._session = None

        if self._session is None or self._session.closed:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            connector = aiohttp.TCPConnector(
                limit=self.limit,
                limit_per_host=self.limit_per_host,
                ttl_dns_cache=self.ttl_dns_cache,
                ssl=ssl_context,
            )
            timeout = aiohttp.ClientTimeout(total=60)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
