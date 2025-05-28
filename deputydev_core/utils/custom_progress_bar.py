class CustomProgressBar:
    """
    A custom progress bar to track file processing progress.

    Attributes:
        completed (bool): Indicates if the process is complete.
        current_batch_percentage (float): Percentage of the current batch progress.
        total_files_to_process (int): Total number of files to be processed.
        total_percentage (float): Total percentage of progress.
    """

    def __init__(self):
        """
        Initializes the progress bar with default values.
        """
        self.completed = False
        self.current_batch_percentage = 0
        self.total_files_to_process = 0
        self.total_percentage = 0

    def initialise(self, total_files_to_process: int):
        """
        Sets the total number of files to be processed.

        Args:
            total_files_to_process (int): The total number of files to process.
        """
        self.total_files_to_process = total_files_to_process

    def set_current_batch_percentage(self, current_file_batch_size: int):
        """
        Calculates and updates the current batch progress percentage.

        Args:
            current_file_batch_size (int): The number of files in the current batch.
        """
        self.current_batch_percentage = 100 * (current_file_batch_size / self.total_files_to_process)

    def update(self, current_chunks_count: int, total_current_chunks_count: int):
        """
        Updates the total progress percentage based on chunk completion.

        Args:
            current_chunks_count (int): Number of processed chunks in the current batch.
            total_current_chunks_count (int): Total number of chunks in the current batch.
        """
        self.total_percentage += self.current_batch_percentage * (current_chunks_count / total_current_chunks_count)

    def is_completed(self) -> bool:
        """
        Checks if the progress has reached 100%.

        Returns:
            bool: True if progress is complete, otherwise False.
        """
        return self.total_percentage >= 100

    def mark_finish(self):
        """
        Marks the progress as complete and sets total progress to 100%.
        """
        self.total_percentage = 100
        self.completed = True
