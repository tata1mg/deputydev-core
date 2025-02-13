from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RefreshConfig(BaseModel):
    async_refresh: bool = False
    refresh_timestamp: Optional[datetime] = None
