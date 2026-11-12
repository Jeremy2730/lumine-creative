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
    - Estado de interacción: la bandera "ocupado" ya no vive aquí sino en
      ``InteractionState`` (app/interaction.py), que además sabe qué acciones
      bloquea cada herramienta (``can(Action)``). ``is_busy`` se conserva
      como atajo de ``interaction.is_processing``.
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
      aplicación (un solo ``InteractionState`` y un solo runner). Las
      herramientas (``run_tool``) y los flujos de archivo
      (``FileController``: abrir, guardar) pasan por ella, así que nunca
      se solapan. Acepta un ``on_error`` opcional para encadenar acciones
      que no deben continuar si la tarea falla (p. ej. cerrar tras un
      guardado que falló).
    - Progreso: ``run_task(progress=True)`` entrega a ``work`` un
      ``ProgressReporter``; los eventos llegan a ``process_pending()`` (hilo
      de la GUI) y se pasan a ``view.show_progress`` SI la vista lo
      implementa (es opcional: las vistas sin él siguen funcionando) y solo
      mientras la tarea siga en curso. Las herramientas sin etapas no emiten
      eventos y la vista muestra su barra indeterminada de siempre.
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

from app.interaction import Action, InteractionState
from app.services.processing_service import ProcessingService
from app.services.task_runner import BackgroundTaskRunner
from core.exceptions import DesignToolError, NoImageLoadedError, ValidationError
from core.models import ImageSnapshot
from core.progress import ProgressEvent, ProgressReporter

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
        interaction: InteractionState | None = None,
    ) -> None:
        self._service = service
        self._runner = runner
        self._interaction = interaction or InteractionState()
        self._view: DesignView | None = None

    # ---- ciclo de vida ----
    def attach_view(self, view: DesignView) -> None:
        self._view = view

    @property
    def interaction(self) -> InteractionState:
        """Estado central: la GUI lo observa y pregunta ``can(Action)``."""
        return self._interaction

    @property
    def is_busy(self) -> bool:
        return self._interaction.is_processing

    def can(self, action: Action) -> bool:
        return self._interaction.can(action)

    def shutdown(self) -> None:
        """Cierre de la aplicación: descarta lo pendiente (el hilo de trabajo es daemon)."""
        self._runner.close()

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
            work=lambda reporter: self._service.apply_tool(name, progress=reporter, **params),
            on_success=lambda snap: self._show(
                snap, f"{msg.success} ({snap.size[0]} × {snap.size[1]} px)"
            ),
            error=msg.error,
            progress=True,
            tool=name,
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
        progress: bool = False,
        tool: str | None = None,
    ) -> bool:
        """Ejecuta ``work`` en segundo plano con la compuerta de "ocupado".

        Único punto de exclusión de tareas de la aplicación: herramientas,
        abrir y guardar pasan por aquí, así que nunca hay dos a la vez ni
        una segunda bandera que pueda divergir. Devuelve ``False`` si la
        tarea se rechazó por estar ocupado. ``on_error`` (opcional) se
        invoca DESPUÉS del tratamiento estándar del error (log + mensaje).
        Con ``progress=True``, ``work`` recibe un ``ProgressReporter``. ``tool`` (nombre
        en el registro) decide la política de interacción mientras dura la tarea.
        """
        view = self._view_or_fail()
        if not self._interaction.begin(tool):
            self._status("⏳ Espera a que termine el proceso actual.", StatusLevel.WARNING)
            return False
        view.set_busy(True)
        self._status(start, StatusLevel.INFO)

        def succeeded(result: Any) -> None:
            self._interaction.end()  # primero se liberan los bloqueos: nada queda atrapado
            self._view_or_fail().set_busy(False)
            on_success(result)

        def failed(exc: Exception) -> None:
            self._interaction.fail()
            self._view_or_fail().set_busy(False)
            logger.error("%s | %s", error, exc, exc_info=exc)  # detalle técnico -> log
            if isinstance(exc, DesignToolError):
                message = exc.display_message(error)
            else:
                message = error
            self._status(message, StatusLevel.ERROR)
            if on_error is not None:
                on_error(exc)

        self._runner.submit(
            work, succeeded, failed, on_progress=self._on_progress if progress else None
        )
        return True

    def _on_progress(self, event: ProgressEvent) -> None:
        """Hilo de la GUI (vía drain). Ignora eventos de una tarea que ya terminó."""
        if not self._interaction.is_processing:
            return
        show = getattr(self._view, "show_progress", None)
        if show is not None:
            show(event)

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
