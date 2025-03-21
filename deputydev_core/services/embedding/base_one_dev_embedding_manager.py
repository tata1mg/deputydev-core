import time
from typing import List, Optional, Tuple

from deputydev_core.clients.http.service_clients.one_dev_client import OneDevClient
from deputydev_core.services.embedding.base_embedding_manager import (
    BaseEmbeddingManager,
)
from deputydev_core.services.tiktoken import TikToken
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.shared_memory import SharedMemory


class BaseOneDevEmbeddingManager(BaseEmbeddingManager):
    def __init__(self, auth_token_key: str, one_dev_client: OneDevClient):
        self.auth_token_key = auth_token_key
        self.one_dev_client = one_dev_client

    def create_optimized_batches(self, texts: List[str], target_tokens_per_batch: int, model: str) -> List[List[str]]:
        tiktoken_client = TikToken()
        batches: List[List[str]] = []
        current_batch = []
        current_batch_token_count = 0

        for text in texts:
            text_token_count = tiktoken_client.count(text, model=model)

            if text_token_count > target_tokens_per_batch:  # Single text exceeds max tokens
                batches.append([text])
                AppLogger.log_warn(
                    f"Text with token count {text_token_count} exceeds the max token limit of {target_tokens_per_batch}."
                )
                continue

            if current_batch_token_count + text_token_count > target_tokens_per_batch:
                batches.append(current_batch)
                current_batch = [text]
                current_batch_token_count = text_token_count
            else:
                current_batch.append(text)
                current_batch_token_count += text_token_count

        if current_batch:
            batches.append(current_batch)

        return batches

    async def _get_embeddings_for_single_batch(
        self, batch: List[str], store_embeddings: bool = True
    ) -> Tuple[Optional[List[List[float]]], int, List[str]]:
        try:
            time_start = time.perf_counter()
            embedding_result = await self.one_dev_client.create_embedding(
                payload={"texts": batch, "store_embeddings": store_embeddings},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {SharedMemory.read(self.auth_token_key)}",
                },
            )
            AppLogger.log_debug(f"Time taken for embedding batch via API: {time.perf_counter() - time_start}")
            return (
                embedding_result["embeddings"],
                embedding_result["tokens_used"],
                batch,
            )
        except Exception as e:
            AppLogger.log_error(f"Failed to get embeddings for batch: {e}")
            return None, 0, batch
