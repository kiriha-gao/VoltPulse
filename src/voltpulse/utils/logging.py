import logging
import os
import sys
from pathlib import Path
from typing import Optional


def get_logger(name: str = "voltpulse", log_dir: Optional[str] = None, log_level: str = "INFO") -> logging.Logger:
    """
    Configures and returns a structured logger conforming to VoltPulse Specification Section 31.
    Logs are written to both standard output and files in `logs/`.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler (UTF-8 safe on Windows)
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    if log_dir is None:
        log_dir = "logs"
    
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path / "voltpulse.log", encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
