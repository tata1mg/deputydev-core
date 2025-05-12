from typing import Any

from deputydev_core.utils.context_vars import get_context_value, set_context_values


class ContextValue:
    @classmethod
    def set(cls, key: str, data: Any) -> None:
        set_context_values(**{key: data})

    @classmethod
    def get(cls, key: str) -> Any:
        return get_context_value(key)
