from typing import Dict, List

from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.chunking.reranker.base_chunk_reranker import (
    BaseChunkReranker,
)


class HeuristicBasedChunkReranker(BaseChunkReranker):
    async def rerank(
        self,
        focus_chunks: List[ChunkInfo],
        related_codebase_chunks: List[ChunkInfo],
        query: str,
    ) -> List[ChunkInfo]:
        ranked_snippets_list = focus_chunks + related_codebase_chunks
        chunks_in_order: List[ChunkInfo] = []
        source_to_chunks: Dict[str, List[ChunkInfo]] = {}
        for chunk in ranked_snippets_list:
            if chunk.source_details.file_path not in source_to_chunks:
                source_to_chunks[chunk.source_details.file_path] = []
            source_to_chunks[chunk.source_details.file_path].append(chunk)

        for _source, chunks in source_to_chunks.items():
            chunks = sorted(chunks, key=lambda x: x.source_details.start_line)

            # remove chunks which are completely inside another chunk
            chunks = [
                chunk
                for i, chunk in enumerate(chunks)
                if not any(
                    chunk.source_details.start_line >= c.source_details.start_line
                    and chunk.source_details.end_line <= c.source_details.end_line
                    for c in chunks[:i] + chunks[i + 1 :]
                )
            ]
            chunks_in_order.extend(chunks)

        return chunks_in_order
