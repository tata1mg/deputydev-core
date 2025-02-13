import re
from collections import Counter
from typing import List


class ContentTokenizer:
    def __init__(self, content: str) -> None:
        """
        Tokenizes content into tokens, bigrams, and trigrams.

        Args:
            content (str): The content to tokenize.
        """
        self.tokens: List[str] = self.__tokenize_call(content)

    def __tokenize_call(self, content: str) -> List[str]:
        """
        Tokenizes the content into individual tokens.

        Args:
            content (str): The content to tokenize.

        Returns:
            list[str]: List of tokens extracted from the content.
        """

        def check_valid_token(token: str) -> bool:
            return token and len(token) > 1

        matches = re.finditer(r"\b\w+\b", content)
        pos = 0
        valid_tokens: List[str] = []
        variable_pattern = re.compile(r"([A-Z][a-z]+|[a-z]+|[A-Z]+(?=[A-Z]|$))")
        for match in matches:
            text = match.group()
            match.start()
            if "_" in text:  # snakecase
                offset = 0
                for part in text.split("_"):
                    if check_valid_token(part):
                        valid_tokens.append(part.lower())
                        pos += 1
                    offset += len(part) + 1
            elif parts := variable_pattern.findall(text):  # pascal and camelcase
                offset = 0
                for part in parts:
                    if check_valid_token(part):
                        valid_tokens.append(part.lower())
                        pos += 1
                    offset += len(part)
            else:  # everything else
                if check_valid_token(text):
                    valid_tokens.append(text.lower())
                    pos += 1
        return valid_tokens

    def construct_bigrams(self) -> List[str]:
        """
        Constructs bigrams from the tokens.

        Returns:
            list[str]: List of bigrams.
        """
        res: List[str] = []
        prev_token: str = None
        for token in self.tokens:
            if prev_token:
                joined_token: str = prev_token + "_" + token
                res.append(joined_token)
            prev_token = token
        return res

    def construct_trigrams(self) -> List[str]:
        """
        Constructs trigrams from the tokens.

        Returns:
            list[str]: List of trigrams.
        """
        res: List[str] = []
        prev_prev_token: str = None
        prev_token: str = None
        for token in self.tokens:
            if prev_token and prev_prev_token:
                joined_token: str = prev_prev_token + "_" + prev_token + "_" + token
                res.append(joined_token)
            prev_prev_token = prev_token
            prev_token = token
        return res

    def get_all_tokens(self, include_bigrams: bool = True, include_trigrams: bool = True) -> List[str]:
        """
        Retrieves all tokens, bigrams, and trigrams.

        Args:
            include_bigrams (bool): Whether to include bigrams or not. Default is True.
            include_trigrams (bool): Whether to include trigrams or not. Default is True.

        Returns:
            List[str]: List of all tokens, bigrams, and trigrams.
        """
        tokens = self.tokens
        if include_bigrams:
            bigrams: List[str] = self.construct_bigrams()
            tokens.extend(bigrams)
        if include_trigrams:
            trigrams: List[str] = self.construct_trigrams()
            tokens.extend(trigrams)
        return tokens


def compute_document_tokens(content: str, include_bigrams: bool = True, include_trigrams: bool = True) -> Counter:
    """
    Computes the tokens and their counts in the given document content.

    Args:
        content (str): The document content to tokenize.
        include_bigrams (bool): Whether to include bigrams or not. Default is True.
        include_trigrams (bool): Whether to include trigrams or not. Default is True.

    Returns:
        Counter: Counter object containing the count of each token.
    """
    tokenizer = ContentTokenizer(content)
    return Counter(tokenizer.get_all_tokens(include_bigrams, include_trigrams))
