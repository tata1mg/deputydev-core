"""
Mock data models for DeputyDev Core test suite.

This module contains mock implementations of data models used in tests.
"""


class MockChunkSourceDetails:
    def __init__(self, file_path, start_line, end_line, file_hash=None):
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.file_hash = file_hash


class MockChunkMetadata:
    def __init__(self):
        self.hierarchy = []
        self.all_classes = []
        self.all_functions = []


class MockChunkInfo:
    def __init__(self, content, file_path, start_line, end_line, file_hash=None, embedding=None, metadata=None):
        self.content = content
        self.source_details = MockChunkSourceDetails(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            file_hash=file_hash
        )
        self.embedding = embedding
        self.metadata = metadata or MockChunkMetadata()
        self.has_embedded_lines = False
        self.search_score = 0
    
    @property
    def content_hash(self):
        # Simple hash for testing
        return f"hash_{hash(self.content) % 10000}"
    
    @property
    def file_path(self):
        return self.source_details.file_path
    
    @property
    def start_line(self):
        return self.source_details.start_line
    
    @property
    def end_line(self):
        return self.source_details.end_line
    
    @property
    def file_hash(self):
        return self.source_details.file_hash


# Use our mock classes consistently
ChunkInfo = MockChunkInfo
ChunkSourceDetails = MockChunkSourceDetails
ChunkMetadata = MockChunkMetadata