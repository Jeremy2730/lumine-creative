"""tools/size_resolution/controller.py

Responsabilidad:
    - Coordinación y validación específicas de "Tamaño y resolución":
      vista previa en vivo (cm<->px<->DPI, sin tocar hilos ni aplicar
      nada) y el despacho de la acción real a través del
      DesignController genérico.

No conoce:
    - GUI (no importa CustomTkinter). El diálogo le pasa texto/valores ya
      leídos de sus campos y recibe de vuelta números para mostrar.
    - Otras herramientas: no importa ni manipula remove_background,
      sharpen ni comic_effect.

Notas:
    - Extraído de app/controllers/design_controller.py (Fase 1 de la
      reorganización por herramienta). Antes estos 6 métodos
      (resample_methods, preview_size_px, paired_dimension_cm,
      effective_dpi_from_cm, cm_from_dpi, y la acción equivalente a
      ``apply``) vivían directamente en el controlador genérico, junto a
      la lógica de las demás herramientas. Mismos contratos, mismos
      resultados, mismos mensajes de error — solo cambiaron de archivo.
    - Envuelve a DesignController en vez de heredar de él: usa
      ``check_positive``/``parse_positive``/``run_tool``/``warn`` (los
      cuatro genéricos que DesignController expone públicamente) para
      validar y despachar, sin duplicar esa lógica.
    - Unidades de interfaz (mm/cm/px, PPI/px·cm): la referencia interna
      sigue siendo cm y PPI exclusivamente (cero cambios en core.py).
      ``length_to_cm``/``length_from_cm``/``resolution_to_ppi``/
      ``resolution_from_ppi`` son la única capa que traduce entre lo que
      el usuario ve en el diálogo y esa referencia, delegando el cálculo
      en core/units.py (genérico, no acoplado a esta herramienta).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core import units
from core.exceptions import ValidationError
from tools.size_resolution.core import (
    RESAMPLE_METHODS,
    Axis,
    compute_target_px,
    effective_dpi,
    paired_dimension_cm,
    px_to_cm,
)

if TYPE_CHECKING:
    from app.controllers.design_controller import DesignController


class SizeResolutionController:
    """Coordinación de "Tamaño y resolución" sobre un DesignController genérico."""

    def __init__(self, design_controller: "DesignController") -> None:
        self._controller = design_controller

    # ---- validación de texto (delega en el controlador genérico) ----
    def parse_positive(self, text: str, label: str) -> float:
        return self._controller.parse_positive(text, label)

    # ---- vista previa (solo cálculo; no aplica nada, no usa hilos) ----
    @property
    def resample_methods(self) -> tuple[str, ...]:
        """Métodos de remuestreo disponibles, para poblar el selector de la GUI."""
        return tuple(RESAMPLE_METHODS)

    def preview_size_px(self, width_cm: float, height_cm: float, dpi: float) -> tuple[int, int]:
        """Píxeles resultantes si se aplicara con remuestreo (para la vista previa)."""
        return compute_target_px(width_cm, height_cm, dpi)

    def paired_dimension_cm(
        self, reference_px: tuple[int, int], value_cm: float, axis: str
    ) -> float:
        """Medida del lado opuesto que conserva la proporción (modo remuestrear)."""
        return paired_dimension_cm(reference_px, value_cm, Axis(axis))

    def effective_dpi_from_cm(self, reference_px: float, value_cm: float) -> float:
        """DPI que resultaría de fijar ``value_cm`` sin remuestrear (píxel fijo)."""
        return effective_dpi(reference_px, value_cm)

    def cm_from_dpi(self, reference_px: float, dpi: float) -> float:
        """cm que resultan de un DPI dado sin remuestrear (píxel fijo)."""
        return px_to_cm(reference_px, dpi)

    # ---- unidades de interfaz (traducen hacia/desde cm y PPI canónicos) ----
    def length_to_cm(self, value: float, unit: str, dpi: float) -> float:
        """Valor tal como lo escribió el usuario (en ``unit``) -> cm canónico."""
        if unit == "mm":
            return units.mm_to_cm(value)
        if unit == "px":
            return units.px_to_cm(value, dpi)
        if unit == "in":
            return units.in_to_cm(value)
        return value  # "cm"

    def length_from_cm(self, value_cm: float, unit: str, dpi: float) -> float:
        """cm canónico -> valor a mostrar en ``unit``."""
        if unit == "mm":
            return units.cm_to_mm(value_cm)
        if unit == "px":
            return units.cm_to_px(value_cm, dpi)
        if unit == "in":
            return units.cm_to_in(value_cm)
        return value_cm  # "cm"

    def resolution_to_ppi(self, value: float, unit: str) -> float:
        """Valor tal como lo escribió el usuario (en ``unit``) -> PPI canónico."""
        if unit == "px/cm":
            return units.px_per_cm_to_dpi(value)
        return value  # "PPI"

    def resolution_from_ppi(self, dpi: float, unit: str) -> float:
        """PPI canónico -> valor a mostrar en ``unit``."""
        if unit == "px/cm":
            return units.dpi_to_px_per_cm(dpi)
        return dpi  # "PPI"

    # ---- acción real (valida y despacha a través del controlador genérico) ----
    def apply(
        self,
        width_cm: float,
        height_cm: float,
        dpi: float,
        *,
        resample: bool,
        method: str = "LANCZOS",
    ) -> None:
        try:
            width_cm = self._controller.check_positive(width_cm, "El ancho")
            height_cm = self._controller.check_positive(height_cm, "El alto")
            dpi = self._controller.check_positive(dpi, "La resolución")
        except ValidationError as exc:
            self._controller.warn(exc.display_message("⚠️ Valor inválido."))
            return
        self._controller.run_tool(
            "size_resolution",
            width_cm=width_cm,
            height_cm=height_cm,
            dpi=dpi,
            resample=resample,
            method=method,
        )
