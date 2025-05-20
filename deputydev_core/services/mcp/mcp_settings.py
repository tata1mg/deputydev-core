import os
from typing import Optional, Dict, Tuple
from deputydev_core.services.mcp.dataclass.main import (
    McpSettingsModel,
    ServerConfigModel,
)
from deputydev_core.utils.constants.constants import LocalFiles, LocalDirectories
import json
import pydantic


class McpSettings:
    def __init__(self, mcp_config_path: str = None):
        self.mcp_config_path = (
            mcp_config_path or McpSettings.get_mcp_settings_file_path()
        )

    @staticmethod
    def get_settings_directory_path():
        token_dir = os.path.join(
            os.path.expanduser("~"), LocalDirectories.LOCAL_ROOT_DIRECTORY.value
        )
        token_file = os.path.join(token_dir, LocalFiles.MCP_SETTINGS_FILE.value)
        return token_dir, token_file

    @staticmethod
    def get_mcp_settings_file_path() -> str:
        setting_dir, settings_path = McpSettings.get_settings_directory_path()
        if not os.path.exists(settings_path):
            os.makedirs(setting_dir, exist_ok=True)
            with open(settings_path, "w") as f:
                f.write("""{"mcp_servers": {}}""")
        return settings_path

    def read_and_validate_mcp_settings_file(self) -> Optional[McpSettingsModel]:
        try:
            with open(self.mcp_config_path, "r") as f:
                content = f.read()

            try:
                config = json.loads(content)
            except json.JSONDecodeError:
                raise json.JSONDecodeError(
                    "Invalid MCP settings format. Please ensure your settings follow the correct JSON format."
                )

            try:
                # Validate against schema
                mcp_settings = McpSettingsModel.model_validate(config)
                return mcp_settings
            except pydantic.ValidationError as e:
                raise pydantic.ValidationError(f"Invalid MCP settings schema: {str(e)}")

        except Exception as error:
            raise Exception(f"Failed to read MCP settings: {error}")

    def get_server_config(self, server_name: str) -> Optional[ServerConfigModel]:
        servers_config = self.read_and_validate_mcp_settings_file()
        if server_name not in servers_config.mcp_servers:
            raise ValueError("MCP server config is not present")
        return servers_config.mcp_servers[server_name]

    def update_server_config(self, server_name: str, mcp_config: ServerConfigModel):
        settings = self.read_and_validate_mcp_settings_file()
        if server_name not in settings.mcp_servers:
            raise ValueError(f"MCP server config '{server_name}' is not present.")

        # Update the config
        settings.mcp_servers[server_name] = mcp_config

        # Write back to file
        with open(self.mcp_config_path, "w") as f:
            json.dump(settings.model_dump(), f, indent=2)
