import re
from abc import ABC, abstractmethod
from typing import Any, List

from pydantic import BaseModel

from deputydev_core.llm_handler.dataclasses.main import TextBlockDelta


class BaseAnthropicTextDeltaParser(ABC):
    def __init__(
        self,
        xml_tag: str,
    ) -> None:
        # we use regex to find the tag, because partial tags are possible
        # we create regex patterns for partial tags
        self.xml_tag = xml_tag

        self.start_tag = f"<{xml_tag}>"
        self.end_tag = f"</{xml_tag}>"
        start_tag_partial_patterns = [re.escape(self.start_tag[:i]) for i in range(1, len(self.start_tag) + 1)]
        end_tag_partial_patterns = [re.escape(self.end_tag[:i]) for i in range(1, len(self.end_tag) + 1)]

        # we create regex patterns for tags that start and end with the tag
        self.ends_with_start_tag_regex = rf"({'|'.join(start_tag_partial_patterns)})$"
        self.starts_with_start_tag_regex = rf"^{xml_tag}({'|'.join(start_tag_partial_patterns)})"
        self.ends_with_end_tag_regex = rf"({'|'.join(end_tag_partial_patterns)})$"
        self.starts_with_end_tag_regex = rf"^{xml_tag}({'|'.join(end_tag_partial_patterns)})"

        self.text_buffer = ""
        self.event_buffer: List[Any] = []
        self.start_event_completed = False

    @abstractmethod
    async def parse_text_delta(self, event: TextBlockDelta, last_event: bool = False) -> List[BaseModel]:
        raise NotImplementedError("This method must be implemented in the child class")

    async def cleanup(self) -> None:
        self.text_buffer = ""
        self.event_buffer = []
        self.start_event_completed = False
