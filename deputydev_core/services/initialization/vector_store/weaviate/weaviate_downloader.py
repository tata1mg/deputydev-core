import asyncio
import os
import platform
import shutil
import stat
from typing import Dict, Optional

import aiohttp
import requests

from deputydev_core.services.initialization.vector_store.weaviate.dataclasses.weaviate_dataclasses import (
    WeaviateDownloadPlatformConfig,
    WeaviateSupportedArchitecture,
    WeaviateSupportedPlatforms,
)
from deputydev_core.utils.app_logger import AppLogger


class WeaviateDownloader:
    """
    This class is responsible for downloading the Weaviate binary based on the user's OS and architecture,
    extracting it, and running it. It also includes methods for checking if Weaviate is running and waiting
    for it to be ready.
    Attributes:
        download_dir (str): Directory to download the Weaviate binary.
        weaviate_version (str): Version of Weaviate to download.
        weaviate_host (str): Hostname for the Weaviate instance.
        weaviate_http_port (int): HTTP port for the Weaviate instance.
        weaviate_grpc_port (int): gRPC port for the Weaviate instance.
        startup_timeout (int): Timeout for Weaviate startup.
        startup_healthcheck_interval (int): Interval for health checks during startup.
    """

    platform_config: Dict[WeaviateSupportedPlatforms, WeaviateDownloadPlatformConfig] = {
        WeaviateSupportedPlatforms.WINDOWS: WeaviateDownloadPlatformConfig(
            supported_archs=[WeaviateSupportedArchitecture.AMD64, WeaviateSupportedArchitecture.ARM64],
            combined_package=False,
            package_ext=".zip",
            extracted_file_name="weaviate.exe",
        ),
        WeaviateSupportedPlatforms.LINUX: WeaviateDownloadPlatformConfig(
            supported_archs=[WeaviateSupportedArchitecture.AMD64, WeaviateSupportedArchitecture.ARM64],
            combined_package=False,
            package_ext=".tar.gz",
            extracted_file_name="weaviate",
        ),
        WeaviateSupportedPlatforms.MAC: WeaviateDownloadPlatformConfig(
            supported_archs=[WeaviateSupportedArchitecture.AMD64, WeaviateSupportedArchitecture.ARM64],
            combined_package=True,
            package_ext=".zip",
            extracted_file_name="weaviate",
        ),
    }

    def __init__(
        self,
        download_dir: str,
        weaviate_version: str,
        weaviate_host: str,
        weaviate_http_port: int,
        weaviate_grpc_port: int,
        startup_timeout: int,
        startup_healthcheck_interval: int,
    ) -> None:
        self.weaviate_version = weaviate_version
        self.download_dir = os.path.expanduser(download_dir)
        self.weaviate_host = weaviate_host
        self.weaviate_http_port = weaviate_http_port
        self.weaviate_grpc_port = weaviate_grpc_port
        self.startup_timeout = startup_timeout
        self.startup_healthcheck_interval = startup_healthcheck_interval

    @staticmethod
    def _get_os_type() -> WeaviateSupportedPlatforms:
        try:
            return WeaviateSupportedPlatforms(platform.system().lower())
        except Exception:
            raise RuntimeError(f"Unsupported OS: {platform.system().lower()}")

    @staticmethod
    def _get_system_architecture() -> WeaviateSupportedArchitecture:
        machine = platform.machine().lower()

        if machine in ["x86_64", "amd64"]:
            return WeaviateSupportedArchitecture.AMD64
        elif machine in ["arm64", "aarch64"]:
            return WeaviateSupportedArchitecture.ARM64
        else:
            raise RuntimeError(f"Unsupported architecture: {machine}")

    def _get_weaviate_binary_download_url(
        self,
        os_type: WeaviateSupportedPlatforms,
        arch: WeaviateSupportedArchitecture,
        platform_config: WeaviateDownloadPlatformConfig,
    ) -> str:
        """Get the download URL for the Weaviate binary based on OS and architecture."""
        return (
            f"weaviate-{self.weaviate_version}-{os_type.value}-{arch.value}.{platform_config.package_ext}"
            if not platform_config.combined_package
            else f"weaviate-{self.weaviate_version}-{os_type.value}-all{platform_config['package_ext']}"
        )

    async def _download_binary(self) -> str:
        """Download the full Weaviate binary if not already downloaded"""
        os_type = self._get_os_type()
        arch = self._get_system_architecture()

        selected_platform_config = self.platform_config[os_type]
        if arch not in selected_platform_config.supported_archs:
            raise RuntimeError(f"Unsupported architecture: {arch.value} for OS: {os_type.value}")

        weaviate_download_dir = os.path.join(self.download_dir, "weaviate_binary")
        weaviate_executable_path = os.path.join(weaviate_download_dir, selected_platform_config.extracted_file_name)

        if not os.path.exists(weaviate_executable_path):
            # Download Weaviate binary
            download_url = self._get_weaviate_binary_download_url(
                os_type=os_type, arch=arch, platform_config=selected_platform_config
            )
            archive_path = os.path.join(weaviate_download_dir, f"weaviate.{selected_platform_config.package_ext}")
            AppLogger.log_info(f"Downloading Weaviate binary from {download_url}")
            response = requests.get(download_url)
            response.raise_for_status()  # seems same handling for 4XX, 5XX. Why is this required?

            # Save and extract the binary
            with open(archive_path, "wb") as f:
                f.write(response.content)
            shutil.unpack_archive(archive_path, weaviate_download_dir)
            os.remove(archive_path)

            AppLogger.log_info("Weaviate binary downloaded and extracted successfully")
        else:
            AppLogger.log_info("Weaviate binary already exists")

        return weaviate_executable_path

    def _set_correct_permissions(self, executable_path: str) -> None:
        """Executable permission in only required for linux and mac"""

        if self._get_os_type() != WeaviateSupportedPlatforms.WINDOWS:
            # Ensure correct permissions
            current_permissions = os.stat(executable_path).st_mode
            if not (current_permissions & stat.S_IXUSR):
                AppLogger.log_info("Setting correct permissions for Weaviate binary")
                os.chmod(executable_path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            else:
                AppLogger.log_info("Weaviate binary already has correct permissions")

    async def _is_weaviate_running(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.weaviate_host}:{self.weaviate_http_port}/v1/.well-known/ready"
                ) as resp:
                    return resp.status == 200
        except Exception as e:
            AppLogger.log_error(f"Error checking Weaviate status: {str(e)}")
            return False

    async def wait_for_weaviate_ready(self) -> bool:
        """Check for weaviate to be up every given interval for a maximum of given timeout"""
        loop = asyncio.get_running_loop()
        start = loop.time()

        while True:
            now = loop.time()
            if now - start > self.startup_timeout:
                raise TimeoutError("Weaviate startup timed out")
            if await self._is_weaviate_running():
                return True

            await asyncio.sleep(self.startup_healthcheck_interval)

    async def _run_binary(self, executable_path: str) -> Optional[asyncio.subprocess.Process]:
        """Run the binary if not already running, and return the new process"""

        if not await self._is_weaviate_running():
            AppLogger.log_info("Starting Weaviate binary")
            env = os.environ.copy()
            env["CLUSTER_ADVERTISE_ADDR"] = f"{self.weaviate_host}"
            env["LIMIT_RESOURCES"] = "true"
            env["PERSISTENCE_DATA_PATH"] = os.path.join(self.download_dir, "weaviate_data")
            env["GRPC_PORT"] = str(self.weaviate_grpc_port)
            env["LOG_LEVEL"] = "panic"
            weaviate_process = await asyncio.create_subprocess_exec(
                executable_path,
                "--host",
                self.weaviate_host,
                "--port",
                str(self.weaviate_http_port),
                "--scheme",
                "http",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                await self.wait_for_weaviate_ready()
                AppLogger.log_info("Weaviate started successfully.")
                return weaviate_process
            except TimeoutError:
                weaviate_process.terminate()
                await weaviate_process.wait()
                raise RuntimeError("Weaviate failed to start within timeout")

        else:
            AppLogger.log_info("Weaviate is already running")
            return None

    async def download_and_run_weaviate(self) -> Optional[asyncio.subprocess.Process]:
        """Download and run the weaviate binary. Return the process if a new one was started"""

        try:
            executable_path = await self._download_binary()
            self._set_correct_permissions(executable_path)
            weaviate_process = await self._run_binary(executable_path)
            return weaviate_process
        except Exception as e:
            AppLogger.log_error(f"Failed to download and run Weaviate: {str(e)}")
            raise
