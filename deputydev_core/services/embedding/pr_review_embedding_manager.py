from typing import List, Optional, Tuple

from deputydev_core.services.embedding.extension_embedding_manager import (
    ExtensionEmbeddingManager,
)
from deputydev_core.utils.app_logger import AppLogger


class PRReviewEmbeddingManager(ExtensionEmbeddingManager):

    async def _get_embeddings_for_single_batch(
            self, batch: List[str], store_embeddings: bool = True
    ) -> Tuple[Optional[List[List[float]]], int, List[str]]:
        try:
            embedding_result = await self.one_dev_client.create_embedding(
                payload={"texts": batch, "store_embeddings": store_embeddings},
                headers={
                    "Content-Type": "application/json",
                },
            )
            return (
                embedding_result["embeddings"],
                embedding_result["tokens_used"],
                batch,
            )
        except Exception as e:
            AppLogger.log_error(f"Failed to get embeddings for batch: {e}")
            return None, 0, batch