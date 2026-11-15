"""tools/remove/controller.py

Responsabilidad:
    - Ciclo de vida de UNA sesión de trabajo de Remove: abrirla, ejecutar RMBG
      cuando el usuario lo pide, mostrar el resultado como VISTA PREVIA,
      cancelar o descartar, y salir. Gobierna el estado de la sesión
      (``RemoveState``) y qué acciones ofrece en cada momento.
    - Ser quien recibe el estado, el "ocupado" y el progreso de la tarea
      (hace de ``sink`` de ``DesignController.run_preview``) y los reenvía a su
      ventana SOLO mientras exista, de modo que un evento tardío nunca toca
      widgets destruidos.

No conoce:
    - tkinter ni CustomTkinter (la ventana es ``RemoveView``; ver dialog.py), ni
      rembg (usa el pipeline existente a través de ``DesignController``).

Notas:
    - Abrir NO procesa y NO toca el documento principal: solo lee su imagen para
      mostrarla. El resultado de RMBG se calcula con ``preview`` (sin confirmar) y
      vive aquí como ``PreviewResult``. En esta fase no hay "Aplicar": el
      resultado solo se puede ver, descartar o perder al salir (con confirmación).
    - Cancelar y Salir son distintos:
        * Cancelar: procesando, pide DESCARTAR el resultado cuando termine (la
          inferencia de ONNX no se puede interrumpir; no se dice que se canceló
          mientras sigue ejecutándose); con un resultado en pantalla, lo descarta.
        * Salir: cierra la sesión y devuelve el control a Lumine. Si hay un
          resultado sin aplicar o una inferencia en curso, pide confirmación; en
          el segundo caso la ventana se cierra cuando la inferencia termina.
    - Estados: READY → PROCESSING → COMPLETED | CANCELLED | ERROR; desde
      CANCELLED y ERROR se puede volver a procesar; CLOSED es final. Los
      permisos del visor los da ``InteractionState`` (ámbito TOOL); los de los
      botones, este estado (``can_run``/``can_cancel``/``can_exit``).
    - Una instancia = una sesión: tras CLOSED no se reutiliza. Todo ocurre en el
      hilo principal (los callbacks llegan por ``drain()``).
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Protocol

from PIL import Image

from app.controllers.design_controller import DesignController, StatusLevel
from app.interaction import Action, InteractionState, Scope
from core.models import PreviewResult
from core.progress import ProgressEvent

logger = logging.getLogger(__name__)

__all__ = ["RemoveController", "RemoveState", "RemoveView", "TOOL_NAME"]

TOOL_NAME = "remove_background"  # clave en el ToolRegistry y en TOOL_POLICIES


class RemoveState(str, Enum):
    READY = "ready"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"
    CLOSED = "closed"


class RemoveView(Protocol):
    """Lo que la sesión necesita de su ventana (el diálogo real o un doble de pruebas)."""

    def show_image(self, image: Image.Image, *, keep_view: bool) -> None: ...

    def show_status(self, message: str, level: StatusLevel) -> None: ...

    def show_progress(self, event: ProgressEvent) -> None: ...

    def set_busy(self, busy: bool) -> None: ...

    def state_changed(self) -> None:
        """El estado o los permisos cambiaron: la ventana vuelve a leerlos."""

    def confirm_exit(self, *, processing: bool) -> bool:
        """Pregunta si se sale pese a lo que se perdería. ``True`` = salir."""

    def close(self) -> None:
        """Destruye la ventana (se llama una sola vez)."""


_MSG_READY = "Remove listo. Pulsa «Quitar fondo» para procesar la imagen."
_MSG_DONE = "✅ Fondo eliminado. Es una vista previa: el documento principal no se ha modificado."
_MSG_CANCELLING = (
    "⏳ Cancelando: la IA no se puede interrumpir; el resultado se descartará al terminar."
)
_MSG_CLOSING = "⏳ Saliendo: Remove se cerrará cuando termine la IA (el resultado se descartará)."
_MSG_CANCELLED = "Resultado descartado. El documento principal no cambió."


class RemoveController:
    def __init__(self, design: DesignController) -> None:
        self._design = design
        self._state = RemoveState.READY
        self._view: RemoveView | None = None
        self._original: Image.Image | None = None
        self._result: PreviewResult | None = None
        self._opened = False
        self._cancel_requested = False
        self._exit_requested = False

    # ---- consulta ----
    @property
    def state(self) -> RemoveState:
        return self._state

    @property
    def result(self) -> PreviewResult | None:
        """Resultado sin aplicar (solo en COMPLETED). Descartarlo lo deja en ``None``."""
        return self._result

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_requested

    @property
    def exit_requested(self) -> bool:
        return self._exit_requested

    @property
    def can_run(self) -> bool:
        return self._opened and self._state in (
            RemoveState.READY,
            RemoveState.CANCELLED,
            RemoveState.ERROR,
        )

    @property
    def can_cancel(self) -> bool:
        if self._state is RemoveState.COMPLETED:
            return True
        return (
            self._state is RemoveState.PROCESSING
            and not self._cancel_requested
            and not self._exit_requested
        )

    @property
    def can_exit(self) -> bool:
        return self._opened and self._state is not RemoveState.CLOSED and not self._exit_requested

    @property
    def interaction(self) -> InteractionState:
        """Estado central: la ventana lo observa para saber cuándo releer los permisos del visor."""
        return self._design.interaction

    def can_interact(self, action: Action) -> bool:
        """Permiso de navegación del visor de Remove (ámbito TOOL de ``InteractionState``)."""
        return self._design.interaction.can(action, Scope.TOOL)

    # ---- apertura ----
    def open(self) -> bool:
        """Abre el espacio de trabajo. No procesa ni toca el documento. ``False`` si no se puede."""
        if self._opened or self._state is RemoveState.CLOSED:
            return False
        snapshot = self._design.current_snapshot()
        if snapshot is None:
            self._design.warn("⚠️ Primero abre una imagen.")
            return False
        if not self._design.can(Action.OPEN_TOOL):
            self._design.warn("⏳ Espera a que termine el proceso actual.")
            return False
        if not self._design.interaction.enter_workspace(TOOL_NAME):
            return False
        self._original = snapshot.image  # solo lectura: ni el visor ni preview la modifican
        self._opened = True
        return True

    def attach_view(self, view: RemoveView) -> None:
        """Conecta la ventana y le entrega la imagen original sin procesar."""
        if self._state is RemoveState.CLOSED or self._original is None:
            return
        self._view = view
        view.show_image(self._original, keep_view=False)
        view.show_status(_MSG_READY, StatusLevel.INFO)
        view.state_changed()

    # ---- acciones del usuario ----
    def run(self) -> bool:
        """«Quitar fondo»: lanza RMBG (vista previa, sin confirmar). ``False`` si no procede."""
        if not self.can_run:
            return False
        previous = self._state
        self._set(RemoveState.PROCESSING)
        accepted = self._design.run_preview(
            TOOL_NAME, on_success=self._on_result, on_error=self._on_error, sink=self
        )
        if not accepted:  # ocupado o sin imagen: la sesión sigue como estaba
            self._set(previous)
        return accepted

    def cancel(self) -> None:
        """«Cancelar»: descarta el resultado (ya mostrado, o el que está por llegar)."""
        if not self.can_cancel:
            return
        if self._state is RemoveState.PROCESSING:
            self._cancel_requested = True
            self._status(_MSG_CANCELLING, StatusLevel.WARNING)
            self._changed()
            return
        self._discard(_MSG_CANCELLED)

    def request_exit(self) -> None:
        """«Salir» (o la X de la ventana): cierra la sesión, con confirmación si se perdería algo."""
        if not self.can_exit:
            return
        view = self._view
        needs_confirmation = self._state in (RemoveState.PROCESSING, RemoveState.COMPLETED)
        if needs_confirmation and view is not None:
            processing = self._state is RemoveState.PROCESSING
            if not view.confirm_exit(processing=processing):
                return
            # La pregunta es modal y la tarea pudo terminar mientras tanto: se vuelve a mirar.
            if self._state is RemoveState.CLOSED or self._exit_requested:
                return
        if self._state is RemoveState.PROCESSING:
            self._exit_requested = True
            self._status(_MSG_CLOSING, StatusLevel.WARNING)
            self._changed()
            return  # se cerrará cuando la inferencia termine (ver _on_result / _on_error)
        self._close()

    def close(self) -> None:
        """Cierre incondicional (aborto por un fallo al construir la ventana). Idempotente."""
        self._close()

    # ---- sink de la tarea (lo llama DesignController en el hilo principal) ----
    def show_status(self, message: str, level: StatusLevel) -> None:
        self._status(message, level)

    def show_progress(self, event: ProgressEvent) -> None:
        if self._view is not None:
            self._view.show_progress(event)

    def set_busy(self, busy: bool) -> None:
        if self._view is not None:
            self._view.set_busy(busy)

    # ---- resultado de la tarea ----
    def _on_result(self, preview: Any) -> None:
        if self._state is RemoveState.CLOSED:
            return
        if self._exit_requested:
            self._close()
        elif self._cancel_requested:
            self._discard(_MSG_CANCELLED)
        else:
            self._result = preview
            self._set(RemoveState.COMPLETED)
            if self._view is not None:
                self._view.show_image(preview.image, keep_view=True)
            self._status(_MSG_DONE, StatusLevel.SUCCESS)

    def _on_error(self, exc: Exception) -> None:
        # DesignController ya registró el error (log) y mostró su mensaje por el sink.
        if self._state is RemoveState.CLOSED:
            return
        if self._exit_requested:
            self._close()
            return
        self._cancel_requested = False
        self._set(RemoveState.ERROR)

    # ---- internos ----
    def _discard(self, message: str) -> None:
        self._result = None
        self._cancel_requested = False
        self._set(RemoveState.CANCELLED)
        if self._view is not None and self._original is not None:
            self._view.show_image(self._original, keep_view=True)
        self._status(message, StatusLevel.INFO)

    def _close(self) -> None:
        if self._state is RemoveState.CLOSED:
            return
        view, self._view = self._view, None  # desde aquí ningún evento llega a la ventana
        self._state = RemoveState.CLOSED
        self._result = None
        self._original = None
        try:
            if view is not None:
                view.close()
        except Exception:  # noqa: BLE001 - salir debe devolver SIEMPRE el control a Lumine
            logger.exception("Falló el cierre de la ventana de Remove")
        finally:
            self._design.interaction.leave_workspace()

    def _set(self, state: RemoveState) -> None:
        self._state = state
        self._changed()

    def _changed(self) -> None:
        if self._view is not None:
            self._view.state_changed()

    def _status(self, message: str, level: StatusLevel) -> None:
        if self._view is not None:
            self._view.show_status(message, level)
