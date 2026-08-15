import logging
import logging.handlers
from pathlib import Path

from app.config import get_settings

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging() -> None:
    """Two handlers on the root logger: stdout (live while uvicorn runs) and
    a rotating file (10MB x 5 backups) at logs/app.log. Every module gets its
    own logger via logging.getLogger(__name__) and inherits these handlers
    through propagation — nothing else needs to configure logging itself."""
    LOG_DIR.mkdir(exist_ok=True)
    level = getattr(logging, get_settings().log_level.upper(), logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(stream_handler)
    root.addHandler(file_handler)
