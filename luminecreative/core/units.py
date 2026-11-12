"""core/units.py

Responsabilidad:
    - Conversiones puras de unidades, genéricas y reutilizables por
      cualquier herramienta: mm<->cm, cm<->px (dada una resolución),
      PPI<->px/cm.

No conoce:
    - Remuestreo, proporciones, vista previa, Image.resize ni ninguna
      herramienta de imagen concreta. Tampoco valida sus entradas (eso
      es responsabilidad de quien llame, p. ej.
      app.controllers.design_controller.check_positive/parse_positive,
      ya usados por tools/size_resolution antes de llegar aquí).

Notas:
    - Pensado para crecer con nuevas unidades (pulgadas, puntos, etc.)
      agregando funciones aquí, sin tocar la lógica de ninguna
      herramienta. tools/size_resolution sigue usando cm y PPI como
      referencia interna; este módulo solo traduce entre esas
      referencias y lo que el usuario ve en la interfaz.
"""
from __future__ import annotations

MM_PER_CM = 10.0
CM_PER_INCH = 2.54


def mm_to_cm(mm: float) -> float:
    """cm = mm / 10."""
    return mm / MM_PER_CM


def cm_to_mm(cm: float) -> float:
    """mm = cm × 10."""
    return cm * MM_PER_CM


def cm_to_in(cm: float) -> float:
    """pulgadas = cm / 2.54."""
    return cm / CM_PER_INCH


def in_to_cm(inches: float) -> float:
    """cm = pulgadas × 2.54."""
    return inches * CM_PER_INCH


def cm_to_px(cm: float, dpi: float) -> float:
    """px = cm × DPI / 2.54 (sin redondear; quien llame decide si redondea)."""
    return cm * dpi / CM_PER_INCH


def px_to_cm(px: float, dpi: float) -> float:
    """cm = px × 2.54 / DPI."""
    return px * CM_PER_INCH / dpi


def dpi_to_px_per_cm(dpi: float) -> float:
    """px_por_cm = PPI / 2.54."""
    return dpi / CM_PER_INCH


def px_per_cm_to_dpi(px_per_cm: float) -> float:
    """PPI = px_por_cm × 2.54."""
    return px_per_cm * CM_PER_INCH
