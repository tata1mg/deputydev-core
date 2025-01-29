from enum import Enum


class ExtendedEnum(Enum):
    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class LLMModelNames(ExtendedEnum):
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    GPT_4_PREVIEW = "gpt-4-1106-preview"
    GPT_4_O = "gpt-4o"
    GPT_TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"
