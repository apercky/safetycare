"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor


def setup_logging(
    log_level: str = "INFO",
    json_logs: bool = False,
    log_file: str | None = None,
) -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_logs: If True, output logs as JSON (for production)
        log_file: Optional file path to write logs to
    """
    # Set up standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.INFO),
        stream=sys.stdout,
        force=True,
    )

    # Configure file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        logging.getLogger().addHandler(file_handler)

    # Shared processors for all configurations
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if json_logs:
        # Production: JSON output
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: colored console output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None, **initial_context: Any) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        **initial_context: Initial context values to bind to the logger
    
    Returns:
        A bound structlog logger instance
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


class LoggerMixin:
    """Mixin class that provides a logger property."""

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get a logger bound with the class name."""
        return get_logger(self.__class__.__name__)


def log_request_context(
    request_id: str,
    method: str,
    path: str,
    client_ip: str | None = None,
) -> None:
    """
    Bind request context to structlog context vars.
    
    This should be called at the start of each request to add
    request-specific context to all log messages.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=method,
        path=path,
        client_ip=client_ip,
    )


def clear_request_context() -> None:
    """Clear the request context from structlog context vars."""
    structlog.contextvars.clear_contextvars()
