from datetime import datetime, timezone
from functools import wraps
from typing import Union
from deputydev_core.utils.app_logger import AppLogger
from deputydev_core.utils.constants.constants import TimeFormat
from deputydev_core.utils.context_vars import set_context_values


def get_time_difference(
    start_time: Union[datetime, str], end_time: Union[datetime, str], format: TimeFormat = TimeFormat.MINUTES.value
) -> float:
    """
    Calculate the time difference between two datetime values.

    Parameters:
    start_time (Union[datetime, str]): The start time in datetime or ISO 8601 string format.
    end_time (Union[datetime, str]): The end time in datetime or ISO 8601 string format.
    format (TimeFormat): The format for the time difference ('seconds' or 'minutes'). Default is 'minutes'.

    Returns:
    float: The time difference in the specified format.
    """
    if isinstance(start_time, str):
        start_time = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S.%f%z")
    if start_time.tzinfo != timezone.utc:
        start_time.astimezone(timezone.utc)

    if isinstance(end_time, str):
        end_time = datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%S.%f%z")
    if end_time.tzinfo != timezone.utc:
        end_time.astimezone(timezone.utc)

    time_difference = (end_time - start_time).total_seconds()
    if format == TimeFormat.MINUTES.value:
        return time_difference / 60
    else:
        return time_difference


def log_time(func):
    """
    Decorator to log the execution time of methods.

    Args:
        func: The asynchronous function to be decorated.

    Returns:
        The decorated function with logging.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        """
        Wrapper function to log the start time, end time, and any exceptions raised during execution.

        Args:
            args: Positional arguments for the decorated function.
            kwargs: Keyword arguments for the decorated function.

        Returns:
            The result of the decorated function.

        Raises:
            Exception: Any exception raised by the decorated function.
        """

        # Currently we are checking request_id, if it is present in kwargs or not, it's not an ideal way to attach
        # request_id but requests received in background doesn't have request_id which makes finding log traces
        # difficult. This is a temporary check where we are checking if we are receiving request_id in payload or not and then
        # adding it into logs, will have to find a better alternative
        request_id = None
        start_time = datetime.now(timezone.utc)
        # Format the datetime as per the specified format
        formatted_start_time = start_time.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        if kwargs.get("data") and kwargs["data"].get("request_id"):
            request_id = kwargs["data"]["request_id"]
        start_message = f"Start: {func.__name__} at {formatted_start_time}"
        if request_id:
            start_message = start_message + f", for request ID - {request_id}"
            set_context_values(request_id=request_id)
        AppLogger.log_info(start_message)

        try:
            result = await func(*args, **kwargs)
        except Exception as e:
            end_time = datetime.now(timezone.utc)
            formatted_end_time = end_time.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
            exception_message = f"Error: {func.__name__} at {formatted_end_time}"
            if request_id:
                exception_message = exception_message + f", for request ID - {request_id}"
            exception_message = exception_message + f" - {e}"
            AppLogger.log_error(exception_message)
            raise e

        end_time = datetime.now(timezone.utc)
        formatted_end_time = end_time.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        end_message = f"End: {func.__name__} at {formatted_end_time} - Elapsed: {get_time_difference(start_time, end_time, TimeFormat.SECONDS.value):6f} seconds"
        if request_id:
            end_message = end_message + f", for request ID - {request_id}"
        AppLogger.log_info(end_message)

        return result

    return wrapper
