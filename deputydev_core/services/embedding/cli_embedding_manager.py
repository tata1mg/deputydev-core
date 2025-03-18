import asyncio
import time
from typing import List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from prompt_toolkit.shortcuts.progress_bar import ProgressBarCounter
from deputydev_core.services.embedding.base_one_dev_embedding_manager import BaseOneDevEmbeddingManager
from deputydev_core.services.tiktoken import TikToken
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.config_manager import ConfigManager


class CLIEmbeddingManager(BaseOneDevEmbeddingManager):
    def _update_embeddings_and_tokens_used(
        self,
        all_embeddings: List[List[float]],
        total_tokens_used: int,
        failed_batches: List[List[str]],
        current_batch_embeddings: Optional[List[List[float]]],
        current_batch_tokens_used: int,
        current_batch: List[str],
        last_checkpoint: float,
        progress_step: Optional[float],
        progress_bar_counter: Optional[ProgressBarCounter[int]] = None,
    ) -> Tuple[int, float]:
        if current_batch_embeddings is None:
            failed_batches.append(current_batch)
        else:
            all_embeddings.extend(current_batch_embeddings)
            total_tokens_used += current_batch_tokens_used

        if progress_step is not None and progress_bar_counter:
            while len(all_embeddings) - 1 > int(last_checkpoint):
                progress_bar_counter.item_completed()
                last_checkpoint += progress_step

        return total_tokens_used, last_checkpoint

    async def _process_parallel_batches(
        self,
        parallel_batches: List[List[str]],
        all_embeddings: List[List[float]],
        tokens_used: int,
        exponential_backoff: float,
        last_checkpoint: float,
        step: Optional[float],
        store_embeddings: bool = True,
        progress_bar_counter: Optional[ProgressBarCounter[int]] = None,
    ) -> Tuple[int, float, float, List[List[str]]]:
        parallel_tasks = [self._get_embeddings_for_single_batch(batch, store_embeddings) for batch in parallel_batches]
        failed_batches: List[List[str]] = []
        for single_task in asyncio.as_completed(parallel_tasks):
            _embeddings, _tokens_used, data_batch = await single_task
            tokens_used, last_checkpoint = self._update_embeddings_and_tokens_used(
                all_embeddings,
                tokens_used,
                failed_batches,
                _embeddings,
                _tokens_used,
                data_batch,
                last_checkpoint,
                step,
                progress_bar_counter,
            )
        parallel_batches = []
        if failed_batches:
            await asyncio.sleep(exponential_backoff)
            exponential_backoff *= 2
            parallel_batches += failed_batches
        else:
            exponential_backoff = 0.2

        return tokens_used, last_checkpoint, exponential_backoff, parallel_batches

    async def embed_text_array(
        self,
        texts: List[str],
        store_embeddings: bool = True,
        progress_bar_counter: Optional[ProgressBarCounter[int]] = None,
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
        last_checkpoint: float = 0
        step = (len(texts) / len_checkpoints) if len_checkpoints else None

        AppLogger.log_debug(
            f"Total batches: {len(iterable_batches)}, Total Texts: {len(texts)}, Total checkpoints: {len_checkpoints}"
        )
        for batch in iterable_batches:
            if len(parallel_batches) >= max_parallel_tasks:
                (
                    tokens_used,
                    last_checkpoint,
                    exponential_backoff,
                    parallel_batches,
                ) = await self._process_parallel_batches(
                    parallel_batches,
                    embeddings,
                    tokens_used,
                    exponential_backoff,
                    last_checkpoint,
                    step,
                    store_embeddings,
                    progress_bar_counter,
                )
            # store current batch
            parallel_batches += [batch]

        while len(parallel_batches) > 0:
            (
                tokens_used,
                last_checkpoint,
                exponential_backoff,
                parallel_batches,
            ) = await self._process_parallel_batches(
                parallel_batches,
                embeddings,
                tokens_used,
                exponential_backoff,
                last_checkpoint,
                step,
                store_embeddings,
                progress_bar_counter,
            )

        if len(embeddings) != len(texts):
            raise ValueError("Mismatch in number of embeddings and texts")

        return np.array(embeddings), tokens_used
