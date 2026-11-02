"""tools/size_resolution/__init__.py

Responsabilidad:
    - Exponer la API pública de la herramienta "Tamaño y resolución": el
      algoritmo (SizeResolutionAdjuster y las funciones puras cm<->px<->DPI)
      y su controlador específico (SizeResolutionController).

No conoce:
    - GUI: el diálogo (dialog.py) NO se reexporta aquí, para que importar
      este paquete nunca requiera CustomTkinter. Quien necesite el diálogo
      lo importa explícitamente desde tools.size_resolution.dialog.
"""
from tools.size_resolution.controller import SizeResolutionController
from tools.size_resolution.core import (
    DEFAULT_METHOD,
    RESAMPLE_METHODS,
    Axis,
    SizeResolutionAdjuster,
    cm_to_px,
    compute_target_px,
    effective_dpi,
    paired_dimension_cm,
    px_to_cm,
)

__all__ = [
    "Axis",
    "DEFAULT_METHOD",
    "RESAMPLE_METHODS",
    "SizeResolutionAdjuster",
    "SizeResolutionController",
    "cm_to_px",
    "compute_target_px",
    "effective_dpi",
    "paired_dimension_cm",
    "px_to_cm",
]
