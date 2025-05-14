from typing import Dict, List

from deputydev_core.services.chunking.chunk_info import ChunkInfo


def filter_chunks_by_denotation(chunks: List[ChunkInfo], denotations: List[str]) -> List[ChunkInfo]:
    return [chunk for chunk in chunks if chunk.denotation in denotations]


def jsonify_chunks(chunks: List[ChunkInfo]) -> List[Dict[str, dict]]:
    return [chunk.model_dump(mode="json") for chunk in chunks]
