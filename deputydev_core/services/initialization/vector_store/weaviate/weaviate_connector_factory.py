from typing import Type, Union
from deputydev_core.utils.os_utils import get_supported_os
from deputydev_core.utils.constants.constants import SupportedPlatforms
from deputydev_core.services.initialization.vector_store.weaviate.weaviate_connector import (
    DarwinWeaviateConnector,
    LinuxWeaviateConnector,
    WindowsWeaviateConnector,
)


class WeaviateConnectorFactory:
    OS_CONNECTOR_MAPPING = {
        SupportedPlatforms.MAC: DarwinWeaviateConnector,
        SupportedPlatforms.LINUX: LinuxWeaviateConnector,
        SupportedPlatforms.WINDOWS: WindowsWeaviateConnector,
    }

    @classmethod
    def get_compatible_connector(
        cls,
    ) -> Type[Union[DarwinWeaviateConnector, LinuxWeaviateConnector, WindowsWeaviateConnector]]:
        return cls.OS_CONNECTOR_MAPPING[get_supported_os()]
