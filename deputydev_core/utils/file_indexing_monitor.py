class FileIndexingMonitor:
    def __init__(self, files_with_indexing_status={}):
        self.files_with_indexing_status = files_with_indexing_status

    def update_status(self, files_status):
        self.files_with_indexing_status.update(files_status)
