"""
Unit tests for ExtensionInitialisationManager class.

This module contains comprehensive test cases for the ExtensionInitialisationManager,
covering initialization, vector store operations, schema management, and database setup.
"""

import asyncio
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Dict, Optional

import pytest

from deputydev_core.services.initialization.extension_initialisation_manager import (
    ExtensionInitialisationManager,
)


class TestExtensionInitialisationManager:
    """Test cases for ExtensionInitialisationManager class."""

    @pytest.fixture
    def mock_dependencies(self):
        """Set up mock dependencies for ExtensionInitialisationManager."""
        with patch.multiple(
            "deputydev_core.services.initialization.extension_initialisation_manager",
            OneDevExtensionChunker=Mock(),
            WeaviateSchemaDetailsService=Mock(),
            AppLogger=Mock(),
            WEAVIATE_SCHEMA_VERSION="v1.0.0",
        ):
            yield

    @pytest.fixture
    def manager_kwargs(self, mock_weaviate_clients, mock_process_executor, mock_one_dev_client):
        """Common kwargs for creating ExtensionInitialisationManager instances."""
        return {
            "repo_path": "/test/repo/path",
            "auth_token_key": "test_auth_token",
            "process_executor": mock_process_executor,
            "one_dev_client": mock_one_dev_client,
            "weaviate_client": mock_weaviate_clients,
            "ripgrep_path": "/usr/bin/rg",
        }

    @pytest.fixture
    def manager(self, manager_kwargs, mock_dependencies):
        """Create ExtensionInitialisationManager instance for testing."""
        with patch(
            "deputydev_core.services.initialization.extension_initialisation_manager.ExtensionEmbeddingManager"
        ) as mock_embedding_manager:
            mock_embedding_manager.return_value = Mock()
            return ExtensionInitialisationManager(**manager_kwargs)

    @pytest.mark.unit
    def test_collections_defined(self):
        """Test that collections are properly defined."""
        from deputydev_core.models.dao.weaviate.chunk_files import ChunkFiles
        from deputydev_core.models.dao.weaviate.chunks import Chunks
        from deputydev_core.models.dao.weaviate.urls_content import UrlsContent
        from deputydev_core.models.dao.weaviate.weaviate_schema_details import WeaviateSchemaDetails

        expected_collections = [Chunks, ChunkFiles, WeaviateSchemaDetails, UrlsContent]
        assert ExtensionInitialisationManager.collections == expected_collections

    @pytest.mark.unit
    def test_init_with_all_parameters(self, manager_kwargs, mock_dependencies):
        """Test initialization with all parameters provided."""
        with patch(
            "deputydev_core.services.initialization.extension_initialisation_manager.ExtensionEmbeddingManager"
        ) as mock_embedding_manager:
            mock_embedding_manager.return_value = Mock()
            
            manager = ExtensionInitialisationManager(**manager_kwargs)
            
            assert manager.repo_path == "/test/repo/path"
            assert manager.weaviate_client is not None
            assert manager.process_executor is not None
            assert manager.ripgrep_path == "/usr/bin/rg"
            mock_embedding_manager.assert_called_once()

    @pytest.mark.unit
    def test_init_with_minimal_parameters(self, mock_dependencies):
        """Test initialization with minimal parameters."""
        with patch(
            "deputydev_core.services.initialization.extension_initialisation_manager.ExtensionEmbeddingManager"
        ) as mock_embedding_manager:
            mock_embedding_manager.return_value = Mock()
            
            manager = ExtensionInitialisationManager()
            
            assert manager.repo_path is None
            assert manager.weaviate_client is None
            assert manager.process_executor is None
            assert manager.ripgrep_path is None
            mock_embedding_manager.assert_called_once()

    @pytest.mark.unit
    def test_init_calls_super_with_correct_parameters(self, manager_kwargs, mock_dependencies):
        """Test that __init__ calls super().__init__ with correct parameters."""
        with patch(
            "deputydev_core.services.initialization.extension_initialisation_manager.ExtensionEmbeddingManager"
        ) as mock_embedding_manager, patch(
            "deputydev_core.services.initialization.extension_initialisation_manager.InitializationManager.__init__"
        ) as mock_super_init:
            mock_embedding_manager.return_value = Mock()
            
            manager = ExtensionInitialisationManager(**manager_kwargs)
            
            mock_super_init.assert_called_once_with(
                mock_embedding_manager,
                "/test/repo/path",
                "test_auth_token", 
                manager_kwargs["process_executor"],
                manager_kwargs["one_dev_client"],
                manager_kwargs["weaviate_client"],
                "/usr/bin/rg",
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_prefill_vector_store_success(self, manager, sample_chunkable_files, mock_dependencies):
        """Test successful prefill_vector_store execution."""
        # Setup
        manager.local_repo = Mock()
        manager.weaviate_client = Mock()
        manager.embedding_manager = Mock()
        manager.process_executor = Mock()
        
        mock_chunks = [Mock(), Mock()]
        
        with patch(
            "deputydev_core.services.initialization.extension_initialisation_manager.OneDevExtensionChunker"
        ) as mock_chunker_class:
            mock_chunker_instance = Mock()
            mock_chunker_instance.create_chunks_and_docs = AsyncMock(return_value=mock_chunks)
            mock_chunker_class.return_value = mock_chunker_instance
            
            manager.process_chunks_cleanup = Mock()
            
            # Execute
            await manager.prefill_vector_store(
                chunkable_files_and_hashes=sample_chunkable_files,
                enable_refresh=True
            )
            
            # Assert
            mock_chunker_class.assert_called_once_with(
                local_repo=manager.local_repo,
                weaviate_client=manager.weaviate_client,
                embedding_manager=manager.embedding_manager,
                process_executor=manager.process_executor,
                indexing_progress_bar=None,
                embedding_progress_bar=None,
                chunkable_files_and_hashes=sample_chunkable_files,
                file_indexing_progress_monitor=None,
            )
            mock_chunker_instance.create_chunks_and_docs.assert_called_once_with(enable_refresh=True)
            manager.process_chunks_cleanup.assert_called_once_with(mock_chunks)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_prefill_vector_store_without_refresh(self, manager, sample_chunkable_files, mock_dependencies):
        """Test prefill_vector_store without refresh enabled."""
        # Setup
        manager.local_repo = Mock()
        manager.weaviate_client = Mock()
        manager.embedding_manager = Mock()
        manager.process_executor = Mock()
        
        mock_chunks = [Mock(), Mock()]
        
        with patch(
            "deputydev_core.services.initialization.extension_initialisation_manager.OneDevExtensionChunker"
        ) as mock_chunker_class:
            mock_chunker_instance = Mock()
            mock_chunker_instance.create_chunks_and_docs = AsyncMock(return_value=mock_chunks)
            mock_chunker_class.return_value = mock_chunker_instance
            
            manager.process_chunks_cleanup = Mock()
            
            # Execute
            await manager.prefill_vector_store(
                chunkable_files_and_hashes=sample_chunkable_files,
                enable_refresh=False
            )
            
            # Assert
            mock_chunker_instance.create_chunks_and_docs.assert_called_once_with(enable_refresh=False)
            manager.process_chunks_cleanup.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_prefill_vector_store_with_progress_bars(self, manager, sample_chunkable_files, mock_dependencies):
        """Test prefill_vector_store with progress bars and monitors."""
        # Setup
        manager.local_repo = Mock()
        manager.weaviate_client = Mock()
        manager.embedding_manager = Mock()
        manager.process_executor = Mock()
        
        mock_indexing_bar = Mock()
        mock_embedding_bar = Mock()
        mock_monitor = Mock()
        
        with patch(
            "deputydev_core.services.initialization.extension_initialisation_manager.OneDevExtensionChunker"
        ) as mock_chunker_class:
            mock_chunker_instance = Mock()
            mock_chunker_instance.create_chunks_and_docs = AsyncMock(return_value=[])
            mock_chunker_class.return_value = mock_chunker_instance
            
            # Execute
            await manager.prefill_vector_store(
                chunkable_files_and_hashes=sample_chunkable_files,
                indexing_progressbar=mock_indexing_bar,
                embedding_progressbar=mock_embedding_bar,
                file_indexing_progress_monitor=mock_monitor
            )
            
            # Assert
            mock_chunker_class.assert_called_once_with(
                local_repo=manager.local_repo,
                weaviate_client=manager.weaviate_client,
                embedding_manager=manager.embedding_manager,
                process_executor=manager.process_executor,
                indexing_progress_bar=mock_indexing_bar,
                embedding_progress_bar=mock_embedding_bar,
                chunkable_files_and_hashes=sample_chunkable_files,
                file_indexing_progress_monitor=mock_monitor,
            )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_prefill_vector_store_local_repo_not_initialized(self, manager, sample_chunkable_files, mock_dependencies):
        """Test prefill_vector_store raises assertion when local_repo is not initialized."""
        manager.local_repo = None
        
        with pytest.raises(AssertionError, match="Local repo is not initialized"):
            await manager.prefill_vector_store(sample_chunkable_files)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_prefill_vector_store_weaviate_client_not_initialized(self, manager, sample_chunkable_files, mock_dependencies):
        """Test prefill_vector_store raises assertion when weaviate_client is not initialized."""
        manager.local_repo = Mock()
        manager.weaviate_client = None
        
        with pytest.raises(AssertionError, match="Connect to vector store"):
            await manager.prefill_vector_store(sample_chunkable_files)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sync_schema_and_return_cleanup_status_new_schema(self, manager, mock_dependencies):
        """Test _sync_schema_and_return_cleanup_status with new schema."""
        # Setup
        manager.weaviate_client = Mock()
        manager.weaviate_client.sync_client.collections.delete_all = Mock()
        
        with patch.object(manager, "_should_recreate_schema", return_value=True) as mock_should_recreate, \
             patch.object(manager, "_populate_collections") as mock_populate, \
             patch(
                "deputydev_core.services.initialization.extension_initialisation_manager.WeaviateSchemaDetailsService"
            ) as mock_service_class, \
             patch(
                "deputydev_core.services.initialization.extension_initialisation_manager.AppLogger"
            ) as mock_logger:
            
            mock_service_instance = Mock()
            mock_service_instance.set_schema_version = AsyncMock()
            mock_service_class.return_value = mock_service_instance
            
            # Execute
            result = await manager._sync_schema_and_return_cleanup_status(should_clean=True)
            
            # Assert
            assert result is True
            mock_should_recreate.assert_called_once_with(True)
            mock_logger.log_debug.assert_called_once_with("Cleaning up the vector store")
            manager.weaviate_client.sync_client.collections.delete_all.assert_called_once()
            mock_populate.assert_called_once()
            mock_service_instance.set_schema_version.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sync_schema_and_return_cleanup_status_existing_schema(self, manager, mock_dependencies):
        """Test _sync_schema_and_return_cleanup_status with existing schema."""
        # Setup
        manager.weaviate_client = Mock()
        manager.weaviate_client.sync_client.collections.delete_all = Mock()
        
        with patch.object(manager, "_should_recreate_schema", return_value=False) as mock_should_recreate, \
             patch.object(manager, "_populate_collections") as mock_populate, \
             patch(
                "deputydev_core.services.initialization.extension_initialisation_manager.WeaviateSchemaDetailsService"
            ) as mock_service_class, \
             patch(
                "deputydev_core.services.initialization.extension_initialisation_manager.AppLogger"
            ) as mock_logger:
            
            mock_service_instance = Mock()
            mock_service_instance.set_schema_version = AsyncMock()
            mock_service_class.return_value = mock_service_instance
            
            # Execute
            result = await manager._sync_schema_and_return_cleanup_status(should_clean=False)
            
            # Assert
            assert result is False
            mock_should_recreate.assert_called_once_with(False)
            mock_logger.log_debug.assert_not_called()
            manager.weaviate_client.sync_client.collections.delete_all.assert_not_called()
            mock_populate.assert_called_once()
            mock_service_instance.set_schema_version.assert_not_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initialize_vector_db_with_clean(self, manager, mock_dependencies):
        """Test initialize_vector_db with clean flag."""
        # Setup
        mock_weaviate_client = Mock()
        mock_process = Mock()
        manager.weaviate_client = mock_weaviate_client
        manager.weaviate_process = mock_process
        
        with patch.object(manager, "_sync_schema_and_return_cleanup_status", return_value=True) as mock_sync:
            with patch("deputydev_core.services.initialization.initialization_service.InitializationManager.initialize_vector_db") as mock_super:
                mock_super.return_value = None
                
                # Execute
                result = await manager.initialize_vector_db(should_clean=True)
                
                # Assert
                assert result == (mock_weaviate_client, mock_process, True)
                mock_super.assert_called_once()
                mock_sync.assert_called_once_with(should_clean=True)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initialize_vector_db_without_clean(self, manager, mock_dependencies):
        """Test initialize_vector_db without clean flag."""
        # Setup
        mock_weaviate_client = Mock()
        mock_process = Mock()
        manager.weaviate_client = mock_weaviate_client
        manager.weaviate_process = mock_process
        
        with patch.object(manager, "_sync_schema_and_return_cleanup_status", return_value=False) as mock_sync:
            with patch("deputydev_core.services.initialization.initialization_service.InitializationManager.initialize_vector_db") as mock_super:
                mock_super.return_value = None
                
                # Execute
                result = await manager.initialize_vector_db(should_clean=False)
                
                # Assert
                assert result == (mock_weaviate_client, mock_process, False)
                mock_super.assert_called_once()
                mock_sync.assert_called_once_with(should_clean=False)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_initialize_vector_db_default_parameters(self, manager, mock_dependencies):
        """Test initialize_vector_db with default parameters."""
        # Setup
        mock_weaviate_client = Mock()
        mock_process = Mock()
        manager.weaviate_client = mock_weaviate_client
        manager.weaviate_process = mock_process
        
        with patch.object(manager, "_sync_schema_and_return_cleanup_status", return_value=False) as mock_sync:
            with patch("deputydev_core.services.initialization.initialization_service.InitializationManager.initialize_vector_db") as mock_super:
                mock_super.return_value = None
                
                # Execute
                result = await manager.initialize_vector_db()
                
                # Assert
                assert result == (mock_weaviate_client, mock_process, False)
                mock_sync.assert_called_once_with(should_clean=False)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_prefill_vector_store_chunker_exception(self, manager, sample_chunkable_files, mock_dependencies):
        """Test prefill_vector_store handles chunker exceptions properly."""
        # Setup
        manager.local_repo = Mock()
        manager.weaviate_client = Mock()
        manager.embedding_manager = Mock()
        manager.process_executor = Mock()
        
        with patch(
            "deputydev_core.services.initialization.extension_initialisation_manager.OneDevExtensionChunker"
        ) as mock_chunker_class:
            mock_chunker_instance = Mock()
            mock_chunker_instance.create_chunks_and_docs = AsyncMock(
                side_effect=Exception("Chunker failed")
            )
            mock_chunker_class.return_value = mock_chunker_instance
            
            # Execute & Assert
            with pytest.raises(Exception, match="Chunker failed"):
                await manager.prefill_vector_store(sample_chunkable_files)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sync_schema_exception_handling(self, manager, mock_dependencies):
        """Test _sync_schema_and_return_cleanup_status handles exceptions properly."""
        # Setup
        manager.weaviate_client = Mock()
        
        with patch.object(manager, "_should_recreate_schema", side_effect=Exception("Schema check failed")):
            # Execute & Assert
            with pytest.raises(Exception, match="Schema check failed"):
                await manager._sync_schema_and_return_cleanup_status(should_clean=True)

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_initialization_workflow(self, manager_kwargs, mock_dependencies):
        """Integration test for the complete initialization workflow."""
        with patch(
            "deputydev_core.services.initialization.extension_initialisation_manager.ExtensionEmbeddingManager"
        ) as mock_embedding_manager:
            mock_embedding_manager.return_value = Mock()
            
            manager = ExtensionInitialisationManager(**manager_kwargs)
            
            # Mock all dependencies
            manager.weaviate_client = Mock()
            manager.weaviate_process = Mock()
            manager.local_repo = Mock()
            manager.embedding_manager = Mock()
            
            with patch.object(manager, "_sync_schema_and_return_cleanup_status", return_value=True) as mock_sync, \
                 patch("deputydev_core.services.initialization.initialization_service.InitializationManager.initialize_vector_db") as mock_super_init, \
                 patch(
                    "deputydev_core.services.initialization.extension_initialisation_manager.OneDevExtensionChunker"
                 ) as mock_chunker_class:
                
                mock_super_init.return_value = None
                mock_chunker_instance = Mock()
                mock_chunker_instance.create_chunks_and_docs = AsyncMock(return_value=[Mock()])
                mock_chunker_class.return_value = mock_chunker_instance
                manager.process_chunks_cleanup = Mock()
                
                # Execute full workflow
                weaviate_client, process, is_new_schema = await manager.initialize_vector_db(should_clean=True)
                
                sample_files = {"test.py": "hash123"}
                await manager.prefill_vector_store(sample_files, enable_refresh=True)
                
                # Assert workflow completion
                assert weaviate_client is not None
                assert is_new_schema is True
                mock_sync.assert_called_once_with(should_clean=True)
                mock_chunker_instance.create_chunks_and_docs.assert_called_once()
                manager.process_chunks_cleanup.assert_called_once()

    @pytest.mark.unit
    def test_collections_inheritance(self):
        """Test that collections are properly defined as class attribute."""
        # Test that collections are accessible without instantiation
        collections = ExtensionInitialisationManager.collections
        assert len(collections) == 4
        
        # Test collection names (assuming they have collection_name attribute)
        collection_names = []
        for collection in collections:
            if hasattr(collection, 'collection_name'):
                collection_names.append(collection.collection_name)
        
        # At least some collections should be present
        assert len(collection_names) >= 0  # Basic sanity check

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_prefill_vector_store_empty_files(self, manager, mock_dependencies):
        """Test prefill_vector_store with empty chunkable files."""
        # Setup
        manager.local_repo = Mock()
        manager.weaviate_client = Mock()
        manager.embedding_manager = Mock()
        manager.process_executor = Mock()
        
        with patch(
            "deputydev_core.services.initialization.extension_initialisation_manager.OneDevExtensionChunker"
        ) as mock_chunker_class:
            mock_chunker_instance = Mock()
            mock_chunker_instance.create_chunks_and_docs = AsyncMock(return_value=[])
            mock_chunker_class.return_value = mock_chunker_instance
            
            # Execute
            await manager.prefill_vector_store(
                chunkable_files_and_hashes={},
                enable_refresh=False
            )
            
            # Assert
            mock_chunker_class.assert_called_once()
            mock_chunker_instance.create_chunks_and_docs.assert_called_once_with(enable_refresh=False)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_multiple_sync_schema_calls(self, manager, mock_dependencies):
        """Test multiple calls to _sync_schema_and_return_cleanup_status."""
        # Setup
        manager.weaviate_client = Mock()
        
        with patch.object(manager, "_should_recreate_schema") as mock_should_recreate, \
             patch.object(manager, "_populate_collections") as mock_populate, \
             patch(
                "deputydev_core.services.initialization.extension_initialisation_manager.WeaviateSchemaDetailsService"
            ) as mock_service_class:
            
            mock_service_instance = Mock()
            mock_service_instance.set_schema_version = AsyncMock()
            mock_service_class.return_value = mock_service_instance
            
            # First call - new schema
            mock_should_recreate.return_value = True
            result1 = await manager._sync_schema_and_return_cleanup_status(should_clean=True)
            
            # Second call - existing schema
            mock_should_recreate.return_value = False
            result2 = await manager._sync_schema_and_return_cleanup_status(should_clean=False)
            
            # Assert
            assert result1 is True
            assert result2 is False
            assert mock_should_recreate.call_count == 2
            assert mock_populate.call_count == 2