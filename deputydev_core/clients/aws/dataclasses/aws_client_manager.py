from typing import Optional

from pydantic import BaseModel


class AWSConnectionParams(BaseModel):
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    endpoint_url: Optional[str] = None


class AWSConfig(BaseModel):
    connect_timeout: Optional[int] = None
    read_timeout: Optional[int] = None
    max_pool_connections: Optional[int] = None
    signature_version: Optional[str] = None
