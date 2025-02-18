import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Tuple

import numpy as np

from deputydev_core.services.chunking.chunk import chunk_pr_diff
from deputydev_core.services.chunking.chunk_info import ChunkInfo
from deputydev_core.services.embedding.base_embedding_manager import \
    BaseEmbeddingManager


def cosine_similarity(a: np.ndarray, B: np.ndarray) -> np.ndarray:
    """
    Calculates the cosine similarity between two vectors.

    Args:
        a (np.ndarray): The first vector.
        B (np.ndarray): The second vector or matrix of vectors.

    Returns:
        np.ndarray: Array of cosine similarities.
    """
    dot_product = np.dot(B, a.T)
    norm_a = np.linalg.norm(a)
    norm_B = np.linalg.norm(B, axis=1)
    return dot_product.flatten() / (norm_a * norm_B)


async def get_query_texts_similarity(
    query: str, texts: List[str], embedding_manager: BaseEmbeddingManager
) -> (List[float], int):
    """
    Computes the cosine similarity between a query and a list of texts.

    Args:
        query (str): The query text.
        texts (list[str]): List of texts to compare against the query.

    Returns:
        list[float]: List of cosine similarity scores.
    """
    if not texts:
        return [], None
    query_chunks = chunk_pr_diff(query)
    text_embeddings, text_tokens = await embedding_manager.embed_text_array(texts)

    query_embeddings, query_tokens = await embedding_manager.embed_text_array(
        query_chunks, store_embeddings=False
    )

    similarities = []
    for query_embedding in query_embeddings:
        similarity = cosine_similarity(query_embedding, text_embeddings)
        similarities.append(similarity)

    avg_similarity = np.mean(similarities, axis=0).tolist()
    total_tokens = text_tokens + query_tokens

    return avg_similarity, total_tokens


def create_chunk_str_to_contents(chunks: List[ChunkInfo]) -> Dict[str, str]:
    """
    Creates a dictionary mapping chunk denotations to their content.

    This function iterates over a list of ChunkInfo objects and constructs a
    dictionary where the keys are the denotations of the chunks and the values
    are the content of the chunks obtained by calling the get_chunk_content method.

    Args:
        chunks (List[ChunkInfo]): A list of ChunkInfo objects.

    Returns:
        Dict[str, str]: A dictionary mapping each chunk's denotation to its content.
    """
    return {
        chunk.denotation: chunk.get_chunk_content_with_meta_data(
            add_ellipsis=False, add_lines=False, add_class_function_info=True
        )
        for chunk in chunks
    }


async def compute_vector_search_scores(
    query: str,
    chunks: List[ChunkInfo],
    embedding_manager: BaseEmbeddingManager,
    process_executor: ProcessPoolExecutor,
) -> Tuple[Dict[str, float], int]:
    """
    Computes vector search scores for a query and a list of ChunkInfo objects.

    Args:
        query (str): The query string.
        chunks (list[ChunkInfo]): List of ChunkInfo objects representing text chunks.

    Returns:
        dict: Dictionary mapping chunk denotations to similarity scores.
    """
    # Instantiate an event loop object for main thread
    loop = asyncio.get_event_loop()
    # Create a ProcessPoolExecutor
    chunk_str_to_contents = await loop.run_in_executor(
        process_executor, create_chunk_str_to_contents, chunks
    )
    chunk_contents_array = list(chunk_str_to_contents.values())
    query_snippet_similarities, input_tokens = await get_query_texts_similarity(
        query, chunk_contents_array, embedding_manager
    )
    chunk_denotations = [chunk.denotation for chunk in chunks]
    chunk_denotation_to_scores = {
        chunk_denotations[i]: score
        for i, score in enumerate(query_snippet_similarities)
    }
    return chunk_denotation_to_scores, input_tokens
