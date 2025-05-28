from abc import ABC, abstractmethod
from typing import List, Union

from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.chunking.dataclass.main import NeoSpan


class BaseChunker(ABC):
    @abstractmethod
    def chunk_code(
        self, tree, content: bytes, max_chars, coalesce, language
    ) -> Union[List[ChunkInfo], List[NeoSpan]]:
        pass
