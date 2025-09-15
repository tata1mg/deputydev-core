from typing import Optional

from pydantic import BaseModel


class XMLWrappedContentTagPosition(BaseModel):
    start_pos: int
    end_pos: Optional[int] = None  # if used in streaming, end can be None


class XMLWrappedContentPosition(BaseModel):
    tag_name: Optional[str] = None
    start: XMLWrappedContentTagPosition
    end: Optional[XMLWrappedContentTagPosition] = None  # if used in streaming, end can be None
