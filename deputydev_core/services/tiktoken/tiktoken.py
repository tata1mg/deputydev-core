import tiktoken

from deputydev_core.utils.config_manager import ConfigManager
from deputydev_core.utils.constants import LLMModelNames


class TikToken:
    """
    Wrapper class for managing text encoding using TikToken library.
    """

    def __init__(self):
        """
        Initialize TikToken class with supported language models.
        """
        llm_models = LLMModelNames.list()
        self.llm_models = {model: tiktoken.encoding_for_model(model) for model in llm_models}

    def count(self, text: str, model: str = LLMModelNames.GPT_4_O.value) -> int:
        """
        Count the number of tokens in the input text using the specified language model.

        Args:
            text (str): The input text to be tokenized.
            model (str): The name of the language model to use for tokenization.

        Returns:
            int: The number of tokens in the input text.
        """
        return len(self.llm_models[model].encode(text, disallowed_special=()))

    def truncate_string(self, text: str, model: str = "gpt-4", max_tokens: int = None) -> str:
        """
        Truncate the input text to a specified maximum number of tokens using the specified language model.

        Args:
            text (str): The input text to be truncated.
            model (str): The name of the language model to use for tokenization.
            max_tokens (int): The maximum number of tokens to retain in the truncated text.

        Returns:
            str: The truncated text.
        """
        if not max_tokens:
            max_tokens = ConfigManager.configs["EMBEDDING"]["TOKEN_LIMIT"]
        tokens = self.llm_models[model].encode(text)[:max_tokens]
        return self.llm_models[model].decode(tokens)

    def split_text_by_tokens(self, text: str, model: str = "gpt-4", max_tokens: int = None) -> list:
        """
        Split the input text into a list of strings, each adhering to the specified maximum number of tokens using the specified language model.

        Args:
            text (str): The input text to be split.
            model (str): The name of the language model to use for tokenization.
            max_tokens (int): The maximum number of tokens per segment.

        Returns:
            list: A list of strings, each within the token limit.
        """
        if not max_tokens:
            max_tokens = ConfigManager.configs["EMBEDDING"]["TOKEN_LIMIT"]
        tokens = self.llm_models[model].encode(text)
        split_texts = []

        for i in range(0, len(tokens), max_tokens):
            segment_tokens = tokens[i : i + max_tokens]
            split_texts.append(self.llm_models[model].decode(segment_tokens))
        return split_texts
