import logging
import sys
from typing import Any, Dict

from deputydev_core.utils.context_vars import get_context_value, set_context_values

# Root logger as a safe default
_root_logger = logging.getLogger()


class AppLogger:
    # ---------- Context ----------
    @classmethod
    def set_logger_context(cls, context: Dict[str, Any]) -> None:
        set_context_values(app_logger_context=context)

    # ---------- Framework detection (lazy) ----------
    @classmethod
    def __is_called_from_sanic(cls) -> bool:
        """Return True if a Sanic app is present (no import unless needed)."""
        try:
            from sanic import Sanic  # lazy import

            app = Sanic.get_app()
            return True if app else False
        except Exception:  # noqa: BLE001
            return False

    @classmethod
    def __is_called_from_fastapi(cls) -> bool:
        """Best-effort check for FastAPI/Uvicorn runtime without hard dependency."""
        try:
            # Fast path: FastAPI is importable and uvicorn/gunicorn present
            import fastapi  # noqa: F401

            if "uvicorn" in sys.modules or "gunicorn" in sys.modules:
                return True

            # Fallback: if FastAPI's logger has handlers, we assume FastAPI stack
            from fastapi.logger import logger as fastapi_logger  # lazy import

            return bool(fastapi_logger.handlers)
        except Exception:  # noqa: BLE001
            return False

    # ---------- Logger selection ----------
    @classmethod
    def __get_selected_logger(cls) -> logging.Logger:
        """Choose a framework-aware logger lazily, else return root logger."""
        # Sanic logger if a Sanic app is active
        if cls.__is_called_from_sanic():
            try:
                from sanic.log import logger as sanic_logger  # lazy import

                return sanic_logger
            except Exception:  # noqa: BLE001
                return _root_logger

        # FastAPI / Uvicorn logger if running under FastAPI stack
        if cls.__is_called_from_fastapi():
            # Prefer FastAPI’s bundled logger, fall back to Uvicorn’s error logger
            try:
                from fastapi.logger import logger as fastapi_logger  # lazy import

                return fastapi_logger
            except Exception:  # noqa: BLE001
                return logging.getLogger("uvicorn.error")

        # Default
        return _root_logger

    # ---------- Context enrichment ----------
    @classmethod
    def __get_meta_info(cls) -> Dict[str, Any]:
        return {
            "team_id": get_context_value("team_id"),
            "scm_pr_id": get_context_value("scm_pr_id"),
            "repo_name": get_context_value("repo_name"),
            "request_id": get_context_value("request_id"),
        }

    @classmethod
    def __get_logger_context(cls) -> Dict[str, Any]:
        data: Dict[str, Any] = get_context_value("app_logger_context") or {}
        meta_info = cls.__get_meta_info()
        if any(meta_info.values()):
            data.update(meta_info)
        return data

    @classmethod
    def build_message(cls, message: str) -> str:
        return f"{cls.__get_logger_context()} -- message -- {message}"

    # ---------- Public logging helpers ----------
    @classmethod
    def log_info(cls, message: str) -> None:
        cls.__get_selected_logger().info(cls.build_message(message))

    @classmethod
    def log_error(cls, message: str) -> None:
        # .exception logs stack trace if called inside an except block
        cls.__get_selected_logger().exception(cls.build_message(message))

    @classmethod
    def log_warn(cls, message: str) -> None:
        cls.__get_selected_logger().warning(cls.build_message(message))

    @classmethod
    def log_debug(cls, message: str) -> None:
        cls.__get_selected_logger().debug(cls.build_message(message))

    # ---------- Basic configuration ----------
    @classmethod
    def set_logger_config(cls, debug: bool = False, stream: Any = None) -> None:
        config: Dict[str, Any] = {
            "level": logging.DEBUG if debug else logging.INFO,
        }
        if stream is not None:
            config["stream"] = stream
        logging.basicConfig(**config)
