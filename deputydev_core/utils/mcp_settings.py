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
        self.mcp_config_path = McpSettings.get_mcp_settings_file_path(mcp_config_path)

    @staticmethod
    def get_settings_file_path():
        mcp_settings_dir = os.path.join(
            os.path.expanduser("~"), LocalDirectories.LOCAL_ROOT_DIRECTORY.value
        )
        mcp_settings_file_path = os.path.join(mcp_settings_dir, LocalFiles.MCP_SETTINGS_FILE.value)
        return mcp_settings_file_path

    @staticmethod
    def get_mcp_settings_file_path(mcp_config_path: str) -> str:
        mcp_config_path = mcp_config_path
        if not os.path.exists(mcp_config_path):
            # Create the file with an empty structure
            with open(mcp_config_path, "w") as f:
                f.write(json.dumps({"mcp_servers": {}}))
        return mcp_config_path

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
                raise Exception(f"Invalid MCP settings schema: {str(e)} {config}")

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
            json.dump(settings.model_dump(exclude_defaults=True), f, indent=2)

