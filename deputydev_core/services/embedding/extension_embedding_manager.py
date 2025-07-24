import asyncio
from typing import List, Optional, Tuple

import numpy as np
from numpy._typing import NDArray

from deputydev_core.services.embedding.base_one_dev_embedding_manager import (
    BaseOneDevEmbeddingManager,
)
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.config_manager import ConfigManager
from deputydev_core.utils.custom_progress_bar import CustomProgressBar


class ExtensionEmbeddingManager(BaseOneDevEmbeddingManager):
    async def _get_embeddings_with_semaphore(
        self, batch: List[str], store_embeddings: bool, sem: asyncio.Semaphore
    ) -> Tuple[Optional[List[List[float]]], int, List[str]]:
        async with sem:
            return await self._get_embeddings_for_single_batch(batch, store_embeddings)

    async def embed_text_array(
        self,
        texts: List[str],
        store_embeddings: bool = True,
        progress_bar_counter: Optional[CustomProgressBar] = None,
        len_checkpoints: Optional[int] = None,
    ) -> Tuple[NDArray[np.float64], int]:
        embeddings: List[List[float]] = []
        tokens_used: int = 0
        exponential_backoff = 0.2

        iterable_batches = self.create_optimized_batches(
            texts,
            target_tokens_per_batch=2048,
            model=ConfigManager.configs["EMBEDDING"]["MODEL"],
        )

        max_parallel_tasks = ConfigManager.configs["EMBEDDING"]["MAX_PARALLEL_TASKS"]
        sem = asyncio.Semaphore(max_parallel_tasks)

        AppLogger.log_debug(
            f"Total batches: {len(iterable_batches)}, Total Texts: {len(texts)}, Total checkpoints: {len_checkpoints}"
        )

        failed_batches: List[List[str]] = []
        tasks = [self._get_embeddings_with_semaphore(batch, store_embeddings, sem) for batch in iterable_batches]
        # As results complete, update progress, handle failed batches, and update tokens_used
        for coro in asyncio.as_completed(tasks):
            _embeddings, _tokens_used, batch = await coro
            if _embeddings is None:
                failed_batches.append(batch)
            else:
                embeddings.extend(_embeddings)
                tokens_used += _tokens_used
            if progress_bar_counter:
                progress_bar_counter.update(len(batch), len(texts))

        # Retry failed batches with exponential backoff
        while failed_batches:
            await asyncio.sleep(exponential_backoff)
            exponential_backoff = min(
                exponential_backoff * 2,
                ConfigManager.configs["EMBEDDING"]["MAX_BACKOFF"],
            )
            AppLogger.log_debug(
                f"Retrying {len(failed_batches)} failed batches with backoff {exponential_backoff:.2f}s"
            )
            retry_batches = failed_batches
            failed_batches = []
            retry_tasks = [self._get_embeddings_with_semaphore(batch, store_embeddings, sem) for batch in retry_batches]
            for coro in asyncio.as_completed(retry_tasks):
                _embeddings, _tokens_used, batch = await coro
                if _embeddings is None:
                    failed_batches.append(batch)
                else:
                    embeddings.extend(_embeddings)
                    tokens_used += _tokens_used
                if progress_bar_counter:
                    progress_bar_counter.update(len(batch), len(texts))
            # Continue the loop if any batches still failed

        if len(embeddings) != len(texts):
            raise ValueError(f"Mismatch in number of embeddings ({len(embeddings)}) and texts ({len(texts)})")

        return np.array(embeddings), tokens_used
