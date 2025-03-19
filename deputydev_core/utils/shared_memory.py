import pickle
import multiprocessing
from multiprocessing import shared_memory
from typing import Dict, Any


class SharedMemory:
    _locks = {}  # Dictionary for key-based locks

    @classmethod
    def _get_lock(cls, shm_name):
        """Get or create a lock for a specific key."""
        if shm_name not in cls._locks:
            cls._locks[shm_name] = multiprocessing.Lock()
        return cls._locks[shm_name]

    @classmethod
    def create(cls, shm_name: str, data: Dict) -> None:
        """Creates or overwrites shared memory with pickled data, using a lock."""
        data_bytes = pickle.dumps(data)  # Serialize object

        with cls._get_lock(shm_name):  # Ensure only one process writes at a time
            try:
                existing_shm = shared_memory.SharedMemory(name=shm_name, create=False)
                if len(data_bytes) > existing_shm.size:
                    # if Existing shared memory too small. Recreating...")
                    existing_shm.close()
                    existing_shm.unlink()
                    raise FileNotFoundError
                # Overwriting existing shared memory...
                shm = existing_shm
            except FileNotFoundError:
                # Creating new shared memory...
                shm = shared_memory.SharedMemory(name=shm_name, create=True, size=len(data_bytes))

            shm.buf[:len(data_bytes)] = data_bytes  # Write serialized data
            shm.close()

    @classmethod
    def read(cls, shm_name: str) -> Any:
        """Reads from shared memory safely using a lock."""
        with cls._get_lock(shm_name):  # Ensure safe access while reading
            try:
                shm = shared_memory.SharedMemory(name=shm_name, create=False)
                raw_data = bytes(shm.buf[:])
                data = pickle.loads(raw_data)  # Deserialize object
                shm.close()
                return data
            except FileNotFoundError:
                return None

    @classmethod
    def delete(cls, shm_name: str) -> None:
        """Deletes shared memory safely using a lock."""
        with cls._get_lock(shm_name):  # Ensure only one process deletes at a time
            try:
                shm = shared_memory.SharedMemory(name=shm_name, create=False)
                shm.close()
                shm.unlink()
            except FileNotFoundError:
                pass
