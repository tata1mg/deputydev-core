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
    def _update_embeddings_and_tokens_used(
        self,
        all_embeddings: List[List[float]],
        total_tokens_used: int,
        failed_batches: List[List[str]],
        current_batch_embeddings: Optional[List[List[float]]],
        current_batch_tokens_used: int,
        current_batch: List[str],
    ) -> int:
        if current_batch_embeddings is None:
            failed_batches.append(current_batch)
        else:
            all_embeddings.extend(current_batch_embeddings)
            total_tokens_used += current_batch_tokens_used
        return total_tokens_used

    async def _process_parallel_batches(
        self,
        parallel_batches: List[List[str]],
        all_embeddings: List[List[float]],
        tokens_used: int,
        exponential_backoff: float,
        store_embeddings: bool = True,
        progress_bar=None,
        progress_step=0,
    ) -> Tuple[int, float, List[List[str]]]:
        parallel_tasks = [
            self._get_embeddings_for_single_batch(batch, store_embeddings)
            for batch in parallel_batches
        ]
        failed_batches: List[List[str]] = []
        for single_task in asyncio.as_completed(parallel_tasks):
            _embeddings, _tokens_used, data_batch = await single_task
            tokens_used = self._update_embeddings_and_tokens_used(
                all_embeddings,
                tokens_used,
                failed_batches,
                _embeddings,
                _tokens_used,
                data_batch,
            )
            if progress_bar:
                progress_bar.update(len(data_batch), progress_step)
        parallel_batches = []
        if failed_batches:
            await asyncio.sleep(exponential_backoff)
            exponential_backoff *= 2
            if exponential_backoff > ConfigManager.configs["EMBEDDING"]["MAX_BACKOFF"]:
                exponential_backoff = ConfigManager.configs["EMBEDDING"]["MAX_BACKOFF"]
            parallel_batches += failed_batches
        else:
            exponential_backoff = 0.2

        return tokens_used, exponential_backoff, parallel_batches

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

        # we send 2048 tokens per batch to the API to avoid having spikes of long api response times in the range of 15-20s
        iterable_batches = self.create_optimized_batches(
            texts,
            target_tokens_per_batch=2048,
            model=ConfigManager.configs["EMBEDDING"]["MODEL"],
        )

        max_parallel_tasks = ConfigManager.configs["EMBEDDING"]["MAX_PARALLEL_TASKS"]
        parallel_batches: List[List[str]] = []

        AppLogger.log_debug(
            f"Total batches: {len(iterable_batches)}, Total Texts: {len(texts)}, Total checkpoints: {len_checkpoints}"
        )
        for batch in iterable_batches:
            if len(parallel_batches) >= max_parallel_tasks:
                (
                    tokens_used,
                    exponential_backoff,
                    parallel_batches,
                ) = await self._process_parallel_batches(
                    parallel_batches,
                    embeddings,
                    tokens_used,
                    exponential_backoff,
                    store_embeddings,
                    progress_bar_counter,
                    len(texts),
                )
            # store current batch
            parallel_batches += [batch]

        while len(parallel_batches) > 0:
            (
                tokens_used,
                exponential_backoff,
                parallel_batches,
            ) = await self._process_parallel_batches(
                parallel_batches,
                embeddings,
                tokens_used,
                exponential_backoff,
                store_embeddings,
                progress_bar_counter,
                len(texts),
            )

        if len(embeddings) != len(texts):
            raise ValueError("Mismatch in number of embeddings and texts")

        return np.array(embeddings), tokens_used
