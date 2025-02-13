from typing import List

from deputydev_core.services.chunking.chunk_info import ChunkInfo


def render_snippet_array(chunks: List[ChunkInfo]) -> str:
    joined_chunks = "\n".join([chunk.get_xml() for chunk in chunks])

    start_chunk_tag = "<relevant_chunks_in_repo>"
    end_chunk_tag = "</relevant_chunks_in_repo>"
    if joined_chunks.strip() == "":
        return ""
    return start_chunk_tag + "\n" + joined_chunks + "\n" + end_chunk_tag
