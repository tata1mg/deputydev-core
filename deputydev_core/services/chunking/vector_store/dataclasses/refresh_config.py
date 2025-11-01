from datetime import datetime

from pydantic import BaseModel


class RefreshConfig(BaseModel):
    async_refresh: bool = False
    refresh_timestamp: datetime
