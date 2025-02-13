import asyncio
import time
from typing import List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from prompt_toolkit.shortcuts.progress_bar import ProgressBarCounter

from managers.base_embedding_manager import BaseEmbeddingManager
from utils.tiktoken_operations import TikToken
from clients.one_dev_client import OneDevClient


class OneDevEmbeddingManager(BaseEmbeddingManager):
    def __init__(self, auth_token: str, one_dev_client: OneDevClient):
        self.auth_token = auth_token
        self.one_dev_client = one_dev_client

    @classmethod
    def create_optimized_batches(
            cls, texts: List[str], max_tokens_per_text: int, max_tokens_per_batch: int, model: str
    ) -> List[List[str]]:
        tiktoken_client = TikToken()
        batches: List[List[str]] = []
        current_batch = []
        current_batch_token_count = 0

        for text in texts:
            text_token_count = tiktoken_client.count(text, model=model)

            if text_token_count > max_tokens_per_text:  # Single text exceeds max tokens
                batches.append([text])
                continue

            if current_batch_token_count + text_token_count > max_tokens_per_batch:
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
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.auth_token}"},
            )
            return embedding_result["embeddings"], embedding_result["tokens_used"], batch
        except Exception as e:
            return None, 0, batch

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

        iterable_batches = self.create_optimized_batches(
            texts, max_tokens_per_text=4096, max_tokens_per_batch=2048, model="text-embedding-3-small"
        )

        max_parallel_tasks = 60
        parallel_batches: List[List[str]] = []
        last_checkpoint: float = 0
        step = (len(texts) / len_checkpoints) if len_checkpoints else None
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
            tokens_used, last_checkpoint, exponential_backoff, parallel_batches = await self._process_parallel_batches(
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
