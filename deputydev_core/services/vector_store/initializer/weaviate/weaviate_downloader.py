import os
import requests
import platform
import asyncio
import aiohttp
import shutil, stat
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.constants.weaviate import SupportedPlatforms

class WeaviateDownloader:
    """Handles downloading and running the Weaviate binary.
    Abstracts OS-specific behavior.
    """

    @classmethod
    async def download_and_run_weaviate(cls) -> asyncio.subprocess.Process:
        """Download and run the full Weaviate binary."""

        if cls._should_download_full_binary():
            try:
                executable_path = cls._download_binary()
                cls._set_correct_permissions(executable_path)
                weaviate_process = await cls._run_binary(executable_path)
                return weaviate_process
            except Exception as e:
                AppLogger.log_error(f"Failed to download and run Weaviate: {str(e)}")
                raise

    @classmethod
    async def _should_download_full_binary(cls) -> bool:
        # TODO: Remove the check for windows if want to run full binary for mac and linux as well
        return platform.system().lower() == SupportedPlatforms.WINDOWS and not await cls._is_weaviate_running()

    @classmethod
    async def _download_binary(cls) -> str:
        """Download the full Weaviate binary if not already downloaded"""

        download_url = cls._weaviate_binary_download_url()

        deputydev_dir = os.path.expanduser("~/.deputydev")
        weaviate_zip = os.path.join(deputydev_dir, "weaviate.zip")
        weaviate_binary = os.path.join(deputydev_dir, "weaviate_binary")
        weaviate_executable = os.path.join(weaviate_binary,
                                           "weaviate.exe" if cls._os_type() == SupportedPlatforms.WINDOWS else "weaviate")

        if not os.path.exists(weaviate_executable):
            # Download Weaviate binary
            AppLogger.log_info(f"Downloading Weaviate binary from {download_url}")
            response = requests.get(download_url)
            response.raise_for_status()  # seems same handling for 4XX, 5XX. Why is this required?

            # Save and extract the binary
            with open(weaviate_zip, "wb") as f:
                f.write(response.content)
            shutil.unpack_archive(weaviate_zip, weaviate_binary)
            os.remove(weaviate_zip)

            AppLogger.log_info("Weaviate binary downloaded and extracted successfully")
        else:
            AppLogger.log_info("Weaviate binary already exists")

        return weaviate_executable

    @classmethod
    def _set_correct_permissions(cls, executable_path):
        """Executable permission in only required for linux and mac"""

        if cls._os_type() != SupportedPlatforms.WINDOWS:
            # Ensure correct permissions
            current_permissions = os.stat(executable_path).st_mode
            if not (current_permissions & stat.S_IXUSR):
                AppLogger.log_info("Setting correct permissions for Weaviate binary")
                os.chmod(executable_path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            else:
                AppLogger.log_info("Weaviate binary already has correct permissions")

    @classmethod
    async def _run_binary(cls, executable_path) -> asyncio.subprocess.Process:
        """Run the binary if not already running"""

        if not cls._is_weaviate_running():
            AppLogger.log_info("Starting Weaviate binary")
            weaviate_process = await asyncio.create_subprocess_exec(
                executable_path, "--host", "127.0.0.1", "--port", "8079", "--scheme", "http",   # TODO: host and port from BE
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                await cls.wait_for_weaviate_ready()
                AppLogger.log_info("Weaviate started successfully.")
                return weaviate_process
            except TimeoutError:
                weaviate_process.terminate()
                await weaviate_process.wait()
                raise Exception("Weaviate failed to start within timeout")

    @classmethod
    async def _is_weaviate_running(cls) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8079/v1/.well-known/ready") as resp:  # TODO: get from config
                    return resp.status == 200
        except:
            return False

    @classmethod
    async def wait_for_weaviate_ready(cls, timeout=60, interval=1):   # TODO: get timeout and interval from config
        """Check for weaviate to be up every given interval for a maximum of given timeout"""

        start = asyncio.get_event_loop().time()

        while True:
            now = asyncio.get_event_loop().time()
            if now - start > timeout:
                raise TimeoutError("Weaviate startup timed out")
            if cls._is_weaviate_running():
                return True

            await asyncio.sleep(interval)

    @classmethod
    def _weaviate_binary_download_url(cls):
        version = "v1.27.0"  # TODO: get from config
        os_type = cls._os_type()
        arch = cls._system_architecture()

        if os_type == SupportedPlatforms.MAC:
            filename = f"weaviate-{version}-darwin-all.zip"
        elif os_type == SupportedPlatforms.LINUX:
            filename = f"weaviate-{version}-linux-{arch}.tar.gz"
        elif os_type == SupportedPlatforms.WINDOWS:
            filename = f"weaviate-{version}-windows-{arch}.zip"

        return f"https://github.com/weaviate/weaviate/releases/download/{version}/{filename}"

    @staticmethod
    def _os_type():
        platform.system().lower()

    @staticmethod
    def _system_architecture():
        machine = platform.machine().lower()

        # TODO: Revisit the arch list
        if machine in ["x86_64", "amd64"]:
            arch = "amd64"
        elif machine in ["arm64", "aarch64"]:
            arch = "arm64"
        else:
            raise Exception(f"Unsupported architecture: {machine}")
        return arch