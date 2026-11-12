"""tools/size_resolution/core.py

Responsabilidad:
    - Herramienta "Tamaño y resolución": fija ancho/alto físicos (cm) y una
      resolución (PPI). Si "remuestrear" está activado, recalcula los
      píxeles y hace un resize real; si está desactivado, los píxeles no
      cambian y solo se actualizan los metadatos de resolución.
    - Funciones puras de conversión cm <-> px <-> DPI efectivo y de
      proporción, reutilizadas por tools/size_resolution/controller.py
      para la vista previa en vivo del diálogo (sin aplicar nada todavía).

No conoce:
    - GUI; valida solo lo estrictamente numérico (medidas/resolución > 0).

Notas:
    - Movido literalmente desde tools/image_resolution.py (Fase 1 de la
      reorganización por herramienta) — mismo código, mismas fórmulas,
      mismos defaults. Ya no hay una herramienta "Redimensionar" aparte
      (se eliminó: su responsabilidad quedó cubierta por esta).
"""
from __future__ import annotations

import math
from enum import Enum

from PIL import Image

from core.exceptions import ValidationError
from core.operation import ImageOperation


class Axis(str, Enum):
    """Dimensión que el usuario fija; la otra se recalcula (proporción o DPI fijo)."""

    WIDTH = "width"
    HEIGHT = "height"


#: Métodos de remuestreo que expone la GUI (sección 9 del encargo).
RESAMPLE_METHODS: dict[str, Image.Resampling] = {
    "LANCZOS": Image.Resampling.LANCZOS,
    "BICUBIC": Image.Resampling.BICUBIC,
    "BILINEAR": Image.Resampling.BILINEAR,
    "NEAREST": Image.Resampling.NEAREST,
}
DEFAULT_METHOD = "LANCZOS"


def _check_positive(value: float, label: str) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValidationError(f"⚠️ {label} debe ser un número mayor que cero.")
    return value


def cm_to_px(cm: float, dpi: float) -> int:
    """px = cm × DPI / 2.54, redondeado al entero más cercano."""
    _check_positive(cm, "La medida")
    _check_positive(dpi, "La resolución")
    return round(cm * dpi / 2.54)


def px_to_cm(px: float, dpi: float) -> float:
    """cm = px × 2.54 / DPI."""
    _check_positive(dpi, "La resolución")
    return px * 2.54 / dpi


def effective_dpi(px: float, cm: float) -> float:
    """DPI efectivo = píxeles / (cm / 2.54). Usado cuando no hay remuestreo:
    el tamaño físico deseado determina qué resolución queda registrada."""
    _check_positive(cm, "La medida")
    return px * 2.54 / cm


def paired_dimension_cm(reference_px: tuple[int, int], value_cm: float, axis: Axis) -> float:
    """Medida del lado opuesto que conserva la proporción de píxeles de la imagen original."""
    _check_positive(value_cm, "La medida")
    width_px, height_px = reference_px
    if axis is Axis.WIDTH:
        return value_cm * (height_px / width_px)
    return value_cm * (width_px / height_px)


def compute_target_px(width_cm: float, height_cm: float, dpi: float) -> tuple[int, int]:
    """Tamaño resultante en píxeles para un ancho/alto (cm) a una resolución (PPI)."""
    return cm_to_px(width_cm, dpi), cm_to_px(height_cm, dpi)


class SizeResolutionAdjuster(ImageOperation):
    """Fija tamaño físico y resolución. ``resample`` decide si cambian los píxeles."""

    name = "size_resolution"

    def __init__(
        self,
        width_cm: float,
        height_cm: float,
        dpi: float,
        *,
        resample: bool,
        method: str = DEFAULT_METHOD,
    ) -> None:
        self.width_cm = _check_positive(width_cm, "El ancho")
        self.height_cm = _check_positive(height_cm, "El alto")
        self.dpi = _check_positive(dpi, "La resolución")
        self.resample = resample
        if method not in RESAMPLE_METHODS:
            raise ValidationError(f"⚠️ Método de remuestreo desconocido: '{method}'.")
        self.method = method

    @property
    def label(self) -> str:
        if self.resample:
            return f"Tamaño {self.width_cm:g}×{self.height_cm:g} cm @ {self.dpi:g} PPI"
        return f"Resolución {self.dpi:g} PPI (sin remuestrear)"

    def apply(self, image: Image.Image) -> Image.Image:
        if self.resample:
            target_px = compute_target_px(self.width_cm, self.height_cm, self.dpi)
            result = image.resize(target_px, RESAMPLE_METHODS[self.method])
        else:
            # No se tocan los píxeles: solo cambian los metadatos de resolución.
            result = image.copy()
        result.info = dict(result.info)
        result.info["dpi"] = (self.dpi, self.dpi)
        return result
