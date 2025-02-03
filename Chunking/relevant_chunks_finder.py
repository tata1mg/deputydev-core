from chunkers.non_vector_db_chunker import NonVectorDBChunker
from chunkers.vector_db_chunker import VectorDBChunker
from managers.chunking_manager import ChunkingManger
from utils.base_local_repo import BaseLocalRepo
from repo.local_repo.factory import LocalRepoFactory
from utils.config_manager import ConfigManager
from clients.one_dev_client import OneDevClient
from concurrent.futures import ProcessPoolExecutor
from managers.one_dev_embedding_manager import OneDevEmbeddingManager
from utils.initialization_manager import InitializationManager
from utils.enums import SearchTypes
import asyncio
from datetime import datetime
from xxhash import xxh64
import argparse


def get_usage_hash(repo_path):
    usage_hash = xxh64(
        str(
            {
                "repo_path": repo_path,
                "current_day_start_time": datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            }
        )
    ).hexdigest()
    return usage_hash


def get_local_repo(repo_path) -> BaseLocalRepo:
    local_repo = LocalRepoFactory.get_local_repo(repo_path)
    return local_repo


async def run_main(args):
    repo_path = args.repo_path
    auth_token = args.auth_token
    query = args.query
    local_repo = get_local_repo(repo_path)
    one_dev_client = OneDevClient(ConfigManager.configs["HOST_AND_TIMEOUT"])
    embedding_manager = OneDevEmbeddingManager(auth_token=auth_token, one_dev_client=one_dev_client)
    query_vector = await embedding_manager.embed_text_array(texts=[query], store_embeddings=False)
    weaviate_client = await InitializationManager().initialize_vector_db()
    chunkable_files_and_hashes = await local_repo.get_chunkable_files_and_commit_hashes()
    usage_hash = get_usage_hash(args.repo_path)
    use_new_chunking = True
    with ProcessPoolExecutor(max_workers=ConfigManager.configs["NUMBER_OF_WORKERS"]) as executor:
        chunker = NonVectorDBChunker(
            local_repo=local_repo,
            process_executor=executor,
            use_new_chunking=use_new_chunking,
        )
        final_chunks, chunks_docs = await VectorDBChunker(
            local_repo=local_repo,
            weaviate_client=weaviate_client,
            embedding_manager=OneDevEmbeddingManager(auth_token=auth_token, one_dev_client=one_dev_client),
            process_executor=executor,
            usage_hash=get_usage_hash(repo_path),
            chunkable_files_and_hashes=chunkable_files_and_hashes,
        ).create_chunks_and_docs()
        relevant_chunks, _ = await ChunkingManger.get_relevant_chunks(
            query=query,
            local_repo=local_repo,
            embedding_manager=embedding_manager,
            process_executor=executor,
            focus_files=[],
            focus_chunks=[],
            weaviate_client=weaviate_client,
            chunkable_files_with_hashes=chunkable_files_and_hashes,
            chunking_handler=chunker,
            query_vector=query_vector[0][0],
            search_type=SearchTypes.VECTOR_DB_BASED,
            usage_hash=usage_hash,
        )
    return relevant_chunks


async def get_args_and_run_main():
    parser = argparse.ArgumentParser(description="Example script with arguments.")
    parser.add_argument("--repo_path", required=True, help="Repo Path")
    parser.add_argument("--auth_token", required=True, help="Repo Path")
    parser.add_argument("--query", required=True, help="Query")
    args = parser.parse_args()
    relevant_chunks = await run_main(args)
    print(f"Number of received relevant_chunks: {len(relevant_chunks)}")


# if __name__ == "__main__":
#     asyncio.run(get_args_and_run_main())
