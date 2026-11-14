import logging
import sys
import structlog


SENSITIVE_KEYS = {"password", "token", "pin", "phone", "secret", "authorization", "cookie"}


def mask_sensitive_data(_, __, event_dict: dict) -> dict:
    """Mask sensitive keys from logging outputs."""
    for key in list(event_dict.keys()):
        lower_key = key.lower()
        if any(s in lower_key for s in SENSITIVE_KEYS):
            event_dict[key] = "[REDACTED]"
    return event_dict


def setup_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            mask_sensitive_data,
            structlog.processors.JSONRenderer()
            if sys.stdout.isatty() is False
            else structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()
