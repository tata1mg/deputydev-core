import os
import shutil
from deputydev_core.utils.app_logger import AppLogger

def clean_directory_except(target_dir: str, except_path: str):
    try:
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            # Skip the item to preserve
            if os.path.abspath(item_path) == os.path.abspath(except_path):
                continue

            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
    except Exception as e:
        AppLogger.log_debug(f"Error cleaning directory - {target_dir}: {str(e)}")