import logging
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

# LOGGING: Use __file__ for reliable path resolution
LOGS_PATH = Path(__file__).resolve().parents[2] / "logs"
LOGS_PATH.mkdir(parents=True, exist_ok=True)


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        level: str | int
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # BUGFIX: frame/depth walking + the actual logger call were previously
        # indented inside `except ValueError`, so every record with a valid
        # level name (INFO/WARNING/...) was silently dropped.
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(level: str = "INFO") -> None:
    LOGS_PATH.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        handlers=[
            InterceptHandler(),
        ],
        level=level,
        force=True,
    )

    for name in list(logging.root.manager.loggerDict):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True

    logging.captureWarnings(True)

    logger.remove()
    logger.add(
        f"{LOGS_PATH}/{datetime.now().date()}.log",
        rotation="00:00",
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message} | {{extra}}",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )
    logger.add(
        sys.stdout,
        level=level,
        colorize=True,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message} | {{extra}}",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )
    # LOGGING: Tune noisy loggers if needed
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
