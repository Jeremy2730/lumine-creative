"""app/controllers/design_controller.py

Responsabilidad:
    - Intermediario entre la GUI y ProcessingService: recibe acciones,
      valida entradas del usuario (medidas, modo), despacha el trabajo en
      segundo plano y traduce errores técnicos a mensajes comprensibles.
    - Definir el contrato DesignView que cualquier vista (GUI, consola,
      vista falsa de test) debe implementar.

No conoce:
    - Algoritmos de Pillow/rembg ni widgets de CustomTkinter.

Notas:
    - Solo permite una operación a la vez (is_busy); los resultados de
      hilos llegan vía process_pending(), llamado periódicamente por la
      GUI.
    - Fase 1 de la reorganización por herramienta: "Tamaño y resolución"
      ya NO vive aquí. Sus 6 métodos específicos (resample_methods,
      preview_size_px, paired_dimension_cm, effective_dpi_from_cm,
      cm_from_dpi y la acción de aplicar) se extrajeron a
      tools/size_resolution/controller.py, que envuelve a este
      DesignController y usa `check_positive`, `parse_positive`,
      `run_tool` y `warn` (los cuatro genéricos de abajo) para validar y
      despachar. Lo mismo ocurrió con "Redimensionar", que se eliminó
      por completo: su responsabilidad ya la cubre "Tamaño y
      resolución".
    - ``run_task`` es la ÚNICA compuerta de exclusión de tareas de la
      aplicación (una sola bandera ``_busy`` y un solo runner). Las
      herramientas (``run_tool``) y los flujos de archivo
      (``FileController``: abrir, guardar) pasan por ella, así que nunca
      se solapan. Acepta un ``on_error`` opcional para encadenar acciones
      que no deben continuar si la tarea falla (p. ej. cerrar tras un
      guardado que falló).
    - ``open_image`` y ``save`` son código HEREDADO: la GUI ya no los usa
      (abrir/guardar viven en ``FileController``). Se conservan porque
      pruebas existentes dependen de ellos; pendiente retirarlos al
      migrarlas. ``save`` escribe un PNG ``_editada`` en Descargas sin
      preguntar y NO tiene noción de documento.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from app.services.processing_service import ProcessingService
from app.services.task_runner import BackgroundTaskRunner
from core.exceptions import DesignToolError, NoImageLoadedError, ValidationError
from core.models import ImageSnapshot

logger = logging.getLogger(__name__)


class StatusLevel(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class DesignView(Protocol):
    """Lo que el controlador necesita de cualquier interfaz (GUI, consola, fake de tests)."""

    def show_snapshot(self, snapshot: ImageSnapshot) -> None: ...

    def show_status(self, message: str, level: StatusLevel) -> None: ...

    def set_busy(self, busy: bool) -> None: ...


@dataclass(frozen=True)
class _ToolMessages:
    start: str
    success: str
    error: str


_TOOL_MESSAGES: dict[str, _ToolMessages] = {
    "remove_background": _ToolMessages(
        "🧼 Quitando fondo...", "✅ Fondo eliminado.", "❌ No se pudo eliminar el fondo."
    ),
    "comic_effect": _ToolMessages(
        "🎨 Aplicando efecto semitono...",
        "✅ Efecto semitono aplicado.",
        "❌ No se pudo aplicar el efecto semitono.",
    ),
    "size_resolution": _ToolMessages(
        "📐 Ajustando tamaño y resolución...",
        "✅ Tamaño y resolución aplicados.",
        "❌ No se pudo ajustar el tamaño y la resolución.",
    ),
    "sharpen": _ToolMessages(
        "🔍 Aplicando nitidez...", "✅ Nitidez aplicada.", "❌ No se pudo aplicar la nitidez."
    ),
}


class DesignController:
    """Intermediario GUI -> ProcessingService. No contiene algoritmos de imagen."""

    def __init__(
        self,
        service: ProcessingService,
        runner: BackgroundTaskRunner,
    ) -> None:
        self._service = service
        self._runner = runner
        self._view: DesignView | None = None
        self._busy = False

    # ---- ciclo de vida ----
    def attach_view(self, view: DesignView) -> None:
        self._view = view

    @property
    def is_busy(self) -> bool:
        return self._busy

    def process_pending(self) -> None:
        """La GUI lo llama periódicamente para recibir resultados de los hilos."""
        self._runner.drain()

    # ---- validación genérica (>0; cualquier herramienta futura puede usarla) ----
    def check_positive(self, value: float, label: str) -> float:
        """Valida un número ya parseado: debe ser finito y > 0."""
        if not math.isfinite(value) or value <= 0:
            raise ValidationError(f"⚠️ {label} debe ser mayor que cero.")
        return value

    def parse_positive(self, text: str, label: str) -> float:
        """Convierte texto a un número > 0 o lanza ``ValidationError``."""
        try:
            value = float(text.strip().replace(",", "."))
        except ValueError:
            raise ValidationError(f"⚠️ {label}: introduce un número válido.") from None
        return self.check_positive(value, label)

    # ---- acciones ----
    def open_image(self, path: str | Path) -> None:
        self.run_task(
            start="📂 Abriendo imagen...",
            work=lambda: self._service.open_image(Path(path)),
            on_success=lambda snap: self._show(
                snap, f"✅ Imagen cargada: {Path(path).name} ({snap.size[0]} × {snap.size[1]} px)"
            ),
            error="❌ No se pudo abrir la imagen.",
        )

    def remove_background(self) -> None:
        self.run_tool("remove_background")

    def comic_effect(self) -> None:
        self.run_tool("comic_effect")

    def sharpen(self) -> None:
        self.run_tool("sharpen")

    def warn(self, message: str) -> None:
        """Muestra un aviso sin despachar trabajo (lo usan los controladores
        de herramienta específicos, ej. SizeResolutionController, cuando su
        propia validación falla antes de llegar a ``run_tool``)."""
        self._status(message, StatusLevel.WARNING)

    def save(self) -> None:
        if not self._require_image():
            return
        self.run_task(
            start="💾 Guardando resultado...",
            work=self._service.save_result,
            on_success=lambda path: self._status(
                f"💾 Imagen guardada en: {path}", StatusLevel.SUCCESS
            ),
            error="❌ No se pudo guardar el resultado.",
        )

    # ---- despacho genérico de herramientas (público: lo usan los
    # controladores de herramienta específicos, ej. SizeResolutionController) ----
    def run_tool(self, name: str, **params: object) -> None:
        if not self._require_image():
            return
        msg = _TOOL_MESSAGES[name]
        self.run_task(
            start=msg.start,
            work=lambda: self._service.apply_tool(name, **params),
            on_success=lambda snap: self._show(
                snap, f"{msg.success} ({snap.size[0]} × {snap.size[1]} px)"
            ),
            error=msg.error,
        )

    def _require_image(self) -> bool:
        if self._service.has_image:
            return True
        self._status(NoImageLoadedError.default_user_message or "", StatusLevel.WARNING)
        return False

    def run_task(
        self,
        *,
        start: str,
        work: Callable[[], Any],
        on_success: Callable[[Any], None],
        error: str,
        on_error: Callable[[Exception], None] | None = None,
    ) -> bool:
        """Ejecuta ``work`` en segundo plano con la compuerta de "ocupado".

        Único punto de exclusión de tareas de la aplicación: herramientas,
        abrir y guardar pasan por aquí, así que nunca hay dos a la vez ni
        una segunda bandera que pueda divergir. Devuelve ``False`` si la
        tarea se rechazó por estar ocupado. ``on_error`` (opcional) se
        invoca DESPUÉS del tratamiento estándar del error (log + mensaje).
        """
        if self._busy:
            self._status("⏳ Espera a que termine el proceso actual.", StatusLevel.WARNING)
            return False
        self._busy = True
        self._view_or_fail().set_busy(True)
        self._status(start, StatusLevel.INFO)

        def succeeded(result: Any) -> None:
            self._busy = False
            self._view_or_fail().set_busy(False)
            on_success(result)

        def failed(exc: Exception) -> None:
            self._busy = False
            self._view_or_fail().set_busy(False)
            logger.error("%s | %s", error, exc, exc_info=exc)  # detalle técnico -> log
            if isinstance(exc, DesignToolError):
                message = exc.display_message(error)
            else:
                message = error
            self._status(message, StatusLevel.ERROR)
            if on_error is not None:
                on_error(exc)

        self._runner.submit(work, succeeded, failed)
        return True

    def _show(self, snapshot: ImageSnapshot, message: str) -> None:
        view = self._view_or_fail()
        view.show_snapshot(snapshot)
        view.show_status(message, StatusLevel.SUCCESS)

    def _status(self, message: str, level: StatusLevel) -> None:
        self._view_or_fail().show_status(message, level)

    def _view_or_fail(self) -> DesignView:
        if self._view is None:
            raise RuntimeError("DesignController: no hay vista asociada (attach_view).")
        return self._view
