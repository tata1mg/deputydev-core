from abc import abstractmethod
from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray


class BaseEmbeddingManager:
    @abstractmethod
    async def embed_text_array(self, texts: List[str], store_embeddings: bool = True) -> Tuple[NDArray[np.float64], int]:
        """
        Embeds a list of texts using the embedding model.

        Args:
            texts (tuple[str]): A tuple of texts to embed.
            store_embeddings (bool): If true we will store embeddings in a cache/store if available.

        Returns:
            list[np.ndarray]: List of embeddings for each text.
        """
        raise NotImplementedError("embed_text_array method should be implemented in the child class")
