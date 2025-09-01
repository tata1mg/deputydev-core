import os
import platform
import shutil

from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.constants.constants import SupportedPlatforms


def clean_directory_except(target_dir: str, except_path: str):
    try:
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            # Skip the item to preserve
            if os.path.abspath(item_path) == os.path.abspath(except_path):
                continue

            if os.path.isfile(item_path) or os.path.islink(item_path):  # noqa: PTH107
                os.remove(item_path)  # noqa: PTH107
            elif os.path.isdir(item_path):  # noqa: PTH112
                shutil.rmtree(item_path)
    except Exception as e: # noqa: BLE001
        AppLogger.log_debug(f"Error cleaning directory - {target_dir}: {str(e)}")


def get_supported_os() -> SupportedPlatforms:
    try:
        return SupportedPlatforms(platform.system().lower())
    except Exception:  # noqa: BLE001
        raise RuntimeError(f"Unsupported OS: {platform.system().lower()}")
