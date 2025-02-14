import logging
from typing import Any, Dict

from sanic import Sanic
from sanic.log import logger as sanic_logger

from deputydev_core.utils.context_vars import get_context_value, set_context_values

logger = logging.getLogger()


class AppLogger:
    @classmethod
    def set_logger_context(cls, context: Dict[str, Any]) -> None:
        set_context_values(app_logger_context=context)

    @classmethod
    def __is_called_from_sanic(cls) -> bool:
        # INFO: sanic is being imported in this method because we do not want sanic to be a dependency where we don't need it
        # This allows the AppLogger to be used without sanic
        try:

            app = Sanic.get_app()
            return True if app else False
        except Exception:
            return False

    @classmethod
    def __get_selected_logger(cls) -> logging.Logger:
        if cls.__is_called_from_sanic():

            return sanic_logger

        return logger

    @classmethod
    def __get_meta_info(cls) -> Dict[str, Any]:
        meta_info = {
            "team_id": get_context_value("team_id"),
            "scm_pr_id": get_context_value("scm_pr_id"),
            "repo_name": get_context_value("repo_name"),
            "request_id": get_context_value("request_id"),
        }
        return meta_info

    @classmethod
    def __get_logger_context(cls) -> Dict[str, Any]:
        data: Dict[str, Any] = get_context_value("app_logger_context") or {}
        meta_info = cls.__get_meta_info()
        if any(meta_info.values()):
            data.update(meta_info)
        return data

    @classmethod
    def build_message(cls, message: str) -> str:
        msg = f"{cls.__get_logger_context()} -- message -- {message}"
        return msg

    @classmethod
    def log_info(cls, message: str) -> None:
        cls.__get_selected_logger().info(cls.build_message(message))

    @classmethod
    def log_error(cls, message: str) -> None:
        cls.__get_selected_logger().exception(cls.build_message(message))

    @classmethod
    def log_warn(cls, message: str) -> None:
        cls.__get_selected_logger().warn(cls.build_message(message))

    @classmethod
    def log_debug(cls, message: str) -> None:
        cls.__get_selected_logger().info(cls.build_message(message))

    @classmethod
    def set_logger_config(cls, debug: bool = False, stream: Any = None) -> None:
        config: Dict[str, Any] = {
            "level": logging.DEBUG if debug else logging.INFO,
        }
        if stream:
            config["stream"] = stream
        logging.basicConfig(**config)
