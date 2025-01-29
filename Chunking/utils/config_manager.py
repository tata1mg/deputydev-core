import json
from typing import Any, Dict, Optional

from utils.singleton import Singleton


class ConfigManager(metaclass=Singleton):
    config: Dict[str, Any] = {'CHUNKING': {'CHARACTER_SIZE': 2000, 'NUMBER_OF_CHUNKS': 10}, 'EMBEDDING': {'MODEL': 'text-embedding-3-small', 'TOKEN_LIMIT': 8192}, 'AUTH_TOKEN_ENV_VAR': 'DEPUTYDEV_AUTH_TOKEN', 'POLLING_INTERVAL': 5, 'NUMBER_OF_WORKERS': 1, 'WEAVIATE_HOST': '127.0.0.1', 'WEAVIATE_HTTP_PORT': 8079, 'WEAVIATE_GRPC_PORT': 50050, 'ENABLED_FEATURES': ['CODE_GENERATION', 'DOCS_GENERATION', 'TEST_GENERATION', 'TASK_PLANNER', 'ITERATIVE_CHAT', 'GENERATE_AND_APPLY_DIFF', 'PLAN_CODE_GENERATION'], 'PR_CREATION_ENABLED': True, 'USE_NEW_CHUNKING': True, 'USE_LLM_RE_RANKING': False, 'USE_VECTOR_DB': True, 'HOST_AND_TIMEOUT': {'HOST': 'http://localhost:8081', 'TIMEOUT': 10000}}
    in_memory: bool = False

    @classmethod
    def json_file_to_dict(cls, _file: str) -> Optional[Dict[str, Any]]:
        """
        convert json file data to dict
        """
        config = None
        try:
            with open(_file) as config_file:
                config = json.load(config_file)
        except (TypeError, FileNotFoundError, ValueError):
            pass

        return config

    @classmethod
    def initialize(cls, config_path: str = "./config.json", in_memory: bool = False):
        cls.config_path = config_path
        if in_memory:
            cls.in_memory = True
            cls.config = {}
            return
        config = cls.json_file_to_dict(cls.config_path)
        if config is None:
            config = {}
        cls.config = config

    @classmethod
    def get(cls, key: str, default: Optional[Any] = None) -> Any:
        return cls.config.get(key, default)

    @classmethod
    def set(cls, values: Dict[str, Any]):
        cls.config.update(values)
        if not cls.in_memory:
            try:
                with open(cls.config_path, "w") as config_file:
                    json.dump(cls.config, config_file, indent=4)
            except (TypeError, FileNotFoundError, ValueError):
                pass

    @classmethod
    @property
    def configs(cls) -> Dict[str, Any]:
        return cls.config
