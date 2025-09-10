import re
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from pydantic import BaseModel

from deputydev_core.llm_handler.dataclasses.main import (
    MalformedToolUseRequest,
    StreamingEvent,
    StreamingEventType,
    TextBlockDelta,
    TextBlockDeltaContent,
    TextBlockEnd,
    TextBlockEvents,
    TextBlockStart,
    ToolUseRequestDelta,
    ToolUseRequestEnd,
    ToolUseRequestStart,
)
from deputydev_core.llm_handler.models.dto.message_thread_dto import MessageData
from deputydev_core.llm_handler.prompts.base_prompt import BasePrompt
from deputydev_core.llm_handler.providers.google.prompts.base_prompts.dataclass.main import (
    XMLWrappedContentPosition,
    XMLWrappedContentTagPosition,
)
from deputydev_core.llm_handler.providers.google.prompts.parsers.event_based.text_block_xml_parser import (
    BaseGoogleTextDeltaParser,
)


class BaseGeminiPromptHandler(BasePrompt):
    @classmethod
    def get_parsed_response_blocks(cls, response_block: List[MessageData]) -> List[Dict[str, Any]]:
        raise NotImplementedError("This method must be implemented in the child class")

    @classmethod
    async def parse_streaming_text_block_events(  # noqa: C901
        cls, events: AsyncIterator[StreamingEvent], parsers: List[BaseGoogleTextDeltaParser]
    ) -> AsyncIterator[Union[StreamingEvent, BaseModel]]:
        xml_tags_to_paraser_map = {parser.xml_tag: parser for parser in parsers}

        text_buffer: str = ""
        on_hold_events: List[TextBlockEvents] = []

        # stores the positions for ongoing xml tags if any
        xml_wrapped_text_position: Optional[XMLWrappedContentPosition] = None

        # iterate over events and parse text blocks, if text block doesn't contain any xml tags, yield it, otherwise
        # keep accumulating text until we find full xml tag, then parse it and yield the result

        async for event in events:
            ################################################################################################################
            # Handling non TextBlockDelta events
            ################################################################################################################
            # if event is not text block, yield it
            if (
                isinstance(event, ToolUseRequestStart)
                or isinstance(event, ToolUseRequestEnd)
                or isinstance(event, ToolUseRequestDelta)
                or isinstance(event, MalformedToolUseRequest)
            ):
                yield event
                continue

            # if event is text block start, we add to on hold events
            if event.type == StreamingEventType.TEXT_BLOCK_START:
                on_hold_events.append(event)
                continue

            # if event is text block end, we yield the text block only if there are no ongoing xml tags
            if event.type == StreamingEventType.TEXT_BLOCK_END:
                if xml_wrapped_text_position is None:
                    yield event
                continue

            ################################################################################################################
            # Handling TextBlockDelta events
            ################################################################################################################
            # accumulate text from TextBlockDelta events
            text_buffer += event.content.text.replace("```diff", "").replace("```", "")

            # if there is no ongoing tag, we try to find a new tag in the text, otherwise we keep yielding text
            # we use regex to find the tag, because partial tags are possible

            need_next_event = False
            while len(text_buffer) > 0 and not need_next_event:
                need_next_event = False
                all_parsers_checked_for_start_tag = False
                while (
                    xml_wrapped_text_position is None or (xml_wrapped_text_position.tag_name is None)
                ) and not all_parsers_checked_for_start_tag:
                    # for each parser, we try to find the start tag in the text buffer which is closest to the start of the buffer
                    for xml_tag, parser in xml_tags_to_paraser_map.items():
                        # entire start tag is present in the text buffer
                        if parser.start_tag in text_buffer and (
                            xml_wrapped_text_position is None
                            or text_buffer.index(parser.start_tag) <= xml_wrapped_text_position.start.start_pos
                        ):
                            xml_wrapped_text_position = XMLWrappedContentPosition(
                                tag_name=xml_tag,
                                start=XMLWrappedContentTagPosition(
                                    start_pos=text_buffer.index(parser.start_tag),
                                    end_pos=text_buffer.index(parser.start_tag) + len(parser.start_tag),
                                ),
                            )

                            # continue to check for other tags
                            continue

                        # partial start tag is present at the end of the text buffer
                        ends_with_start_tag = re.search(parser.ends_with_start_tag_regex, text_buffer)
                        if bool(ends_with_start_tag) and xml_wrapped_text_position is None:
                            # We only update the xml_wrapped_text_position if its None
                            # because if we have already found a tag, we don't want to override it with a partial tag
                            # We don't set the tag_name here, because we don't know if the partial tag is the correct tag
                            xml_wrapped_text_position = XMLWrappedContentPosition(
                                start=XMLWrappedContentTagPosition(
                                    start_pos=text_buffer.index(ends_with_start_tag.group(0)),
                                    end_pos=text_buffer.index(ends_with_start_tag.group(0))
                                    + len(ends_with_start_tag.group(0)),
                                ),
                            )
                            # breaking as we don't need to check for other tags, as even if the tag is some other tag, the partial value will be same
                            break
                    all_parsers_checked_for_start_tag = True

                # now, either we have an ongoing tag or we don't
                # if we haven't found a tag, we can yield the text and clear the buffer

                # Case 1: No ongoing tag
                if xml_wrapped_text_position is None:
                    # if there's a pending text block start event, we yield it
                    for on_hold_event in on_hold_events:
                        yield on_hold_event
                    on_hold_events = []
                    yield TextBlockDelta(content=TextBlockDeltaContent(text=text_buffer))
                    # we clear the buffer
                    text_buffer = ""

                # Case 2: There's a potential ongoing tag, i.e. xml_wrapped_text_position is not None, but tag_name is None
                elif xml_wrapped_text_position.tag_name is None:
                    # we will need more text to identify the tag, so we keep accumulating text by continuing for next event
                    need_next_event = True
                    continue

                # Case 3: There's an ongoing tag, and we know the tag name. i.e. xml_wrapped_text_position is not None and tag_name is not None
                # we try to find the end tag in the text buffer
                else:
                    if xml_wrapped_text_position.start.end_pos is None:
                        raise ValueError("Invalid XMLWrappedContentPosition")

                    # firstly, we can yield the text before the start index, in case there's any
                    if xml_wrapped_text_position.start.start_pos > 0:
                        for on_hold_event in on_hold_events:
                            yield on_hold_event
                        on_hold_events = []
                        yield TextBlockDelta(
                            content=TextBlockDeltaContent(text=text_buffer[: xml_wrapped_text_position.start.start_pos])
                        )
                        yield TextBlockEnd()
                        text_buffer = text_buffer[xml_wrapped_text_position.start.start_pos :]

                        # now we update the xml_wrapped_text_position positions accordingly to new text buffer
                        tag_start_len = (
                            xml_wrapped_text_position.start.end_pos - xml_wrapped_text_position.start.start_pos
                        )
                        xml_wrapped_text_position.start.start_pos = 0
                        xml_wrapped_text_position.start.end_pos = tag_start_len

                    # now, we initialize the tag parser
                    ongoing_tag_parser = xml_tags_to_paraser_map[xml_wrapped_text_position.tag_name]

                    # now, we try to find the end tag or partial end tag in the text buffer

                    # check if the current ongoing tag ends in the text
                    if ongoing_tag_parser.end_tag in text_buffer and (
                        xml_wrapped_text_position.end is None
                        or text_buffer.index(ongoing_tag_parser.end_tag) >= xml_wrapped_text_position.end.start_pos
                    ):
                        tag_end_index = text_buffer.index(ongoing_tag_parser.end_tag)
                        xml_wrapped_text_position.end = XMLWrappedContentTagPosition(
                            start_pos=tag_end_index, end_pos=tag_end_index + len(ongoing_tag_parser.end_tag)
                        )

                    # check if we have a partial end tag at the end of the text buffer
                    else:
                        ends_with_end_tag = re.search(ongoing_tag_parser.ends_with_end_tag_regex, text_buffer)
                        if bool(ends_with_end_tag):
                            # we update the start_pos of the end tag, but not the end_pos, because we don't know the exact end_pos yet
                            xml_wrapped_text_position.end = XMLWrappedContentTagPosition(
                                start_pos=text_buffer.index(ends_with_end_tag.group(0)),
                                end_pos=None,
                            )

                    # now, either we have an end tag or we don't, but we have an ongoing tag
                    # anyway, we can yield the text and clear the buffer until the start of the end tag

                    yieldable_text_start = xml_wrapped_text_position.start.end_pos
                    yieldable_text_end = (
                        xml_wrapped_text_position.end.start_pos
                        if xml_wrapped_text_position.end is not None
                        else len(text_buffer)
                    )
                    events_to_yield = await ongoing_tag_parser.parse_text_delta(
                        TextBlockDelta(
                            content=TextBlockDeltaContent(text=text_buffer[yieldable_text_start:yieldable_text_end])
                        ),
                        last_event=(
                            True
                            if xml_wrapped_text_position.end is not None
                            and xml_wrapped_text_position.end.end_pos is not None
                            else False
                        ),
                    )
                    for event in events_to_yield:
                        yield event
                    # now, we update the text buffer to the text after the end tag
                    text_buffer = text_buffer[yieldable_text_end:]
                    xml_wrapped_text_position.start.start_pos = 0
                    xml_wrapped_text_position.start.end_pos = 0
                    if xml_wrapped_text_position.end is not None:
                        xml_wrapped_text_position.end.start_pos = 0

                    if xml_wrapped_text_position.end is not None and xml_wrapped_text_position.end.end_pos is None:
                        # we need more text to complete the end tag
                        need_next_event = True

                    # now, in next iteration, we can either try to complete the end tag or find a new start tag
                    # but we need to handle a case such that incrementally, the end tag gets completed, then we need to parse and reset the xml_wrapped_text_position

                    if xml_wrapped_text_position.end is not None and xml_wrapped_text_position.end.end_pos is not None:
                        # we clear the buffer upto end pos and then insert a text block start event in on hold events if not already present
                        if xml_wrapped_text_position.end.end_pos > 0:
                            text_buffer = text_buffer.replace(ongoing_tag_parser.end_tag, "")
                            if len(on_hold_events) == 0:
                                on_hold_events.append(TextBlockStart())
                            else:
                                if on_hold_events[-1].type != StreamingEventType.TEXT_BLOCK_START:
                                    on_hold_events.append(TextBlockStart())
                        xml_wrapped_text_position = None
                        # we clear the parser buffer too
                        await ongoing_tag_parser.cleanup()
