from __future__ import annotations

import logging
import sys
from pathlib import Path


def configure_logging(log_path: str = "code/run.log") -> logging.Logger:
    logger = logging.getLogger("support_triage")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    stderr = logging.StreamHandler(sys.stderr)
    stderr.setFormatter(formatter)
    logger.addHandler(stderr)
    return logger
