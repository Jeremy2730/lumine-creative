"""config/logging_config.py

Responsabilidad:
    - Configurar el logging raíz: archivo rotativo en logs/ + consola.
      Los detalles técnicos de los errores van aquí, nunca a la GUI.

No conoce:
    - Qué módulo escribe cada log; solo define el formato y los handlers.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path, level: int = logging.INFO) -> None:
    """Configura el logging raíz. Los detalles técnicos van al archivo."""
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(
            log_dir / "herramienta_diseno.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        ),
        logging.StreamHandler(),
    ]
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        handlers=handlers,
        force=True,
    )
