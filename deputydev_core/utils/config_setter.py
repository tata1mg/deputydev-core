from deputydev_core.utils.config_manager import ConfigManager


def set_config(config):
    ConfigManager.in_memory = True
    ConfigManager.set(config)
