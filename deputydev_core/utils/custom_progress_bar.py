class CustomProgressBar:
    def __init__(self):
        self.is_completed = False
        self.current_batch_percentage = 0
        self.total_files_to_process = 0
        self.total_percentage = 0

    def initialise(self, total_files_to_process):
        self.total_files_to_process = total_files_to_process

    def set_current_batch_percentage(self, current_file_batch_size):
        self.current_batch_percentage = 100*(current_file_batch_size/self.total_files_to_process)

    def update(self, current_chunks_count, total_current_chunks_count):
        self.total_percentage += (self.current_batch_percentage*current_chunks_count/total_current_chunks_count)

    def is_completed(self):
        return self.total_percentage == 100
