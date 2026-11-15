"""tools/remove/controller.py

Responsabilidad:
    - Ciclo de vida de UNA sesión de trabajo de Remove: abrirla, ejecutar RMBG
      cuando el usuario lo pide, mostrar el resultado como VISTA PREVIA, y
      terminarla con OK (confirmar en el documento principal) o Cancelar
      (descartar). Gobierna el estado de la sesión (``RemoveState``) y qué
      acciones ofrece en cada momento.
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
      vive aquí como ``PreviewResult`` hasta que se pulsa OK o se descarta.
    - Botones: «Quitar fondo» (``run``), «Cancelar» (``cancel``) y «OK» (``ok``).
      No hay «Salir» ni cierre con la X: la ventana solo se cierra con OK o con
      Cancelar (``refuse_close`` atiende los intentos de cerrarla de otra forma).
    - OK solo existe con un resultado terminado (COMPLETED): usa
      ``DesignController.commit_preview`` (motor: ``commit``; rechaza un resultado
      obsoleto), el documento principal se actualiza por el mecanismo de siempre y
      la sesión se cierra. Si confirmar falla, la sesión NO se cierra: queda en ERROR
      con el documento intacto.
    - Cancelar:
        * sin tarea en curso: descarta el resultado (si lo hay) y cierra la
          sesión; el documento principal no cambia;
        * con RMBG trabajando: la inferencia de ONNX no se puede interrumpir, así
          que solo se PIDE descartar el resultado (no se dice "cancelado" mientras
          sigue ejecutándose); al terminar se descarta y la sesión queda abierta en
          CANCELLED mostrando el original (se puede reintentar o pulsar Cancelar
          otra vez para volver a Lumine). Nunca se cierra con una tarea activa.
    - Estados: READY → PROCESSING → COMPLETED | CANCELLED | ERROR; desde
      CANCELLED y ERROR se puede volver a procesar; CLOSED es final. Los
      permisos del visor los da ``InteractionState`` (ámbito TOOL); los de los
      botones, este estado (``can_run``/``can_ok``/``can_cancel``).
    - Mensajes de estado: los de la tarea llegan como eventos de progreso y aquí
      se traducen a texto (``show_progress``). La barra de la ventana es
      indeterminada mientras se procesa: la inferencia no informa de su avance y
      las fracciones por etapa son provisionales, así que no se muestra ningún
      porcentaje.
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
from core.exceptions import DesignToolError
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

    def set_busy(self, busy: bool) -> None: ...

    def state_changed(self) -> None:
        """El estado o los permisos cambiaron: la ventana vuelve a leerlos."""

    def close(self) -> None:
        """Destruye la ventana (se llama una sola vez)."""


_MSG_READY = "Remove listo. Pulsa «Quitar fondo» para procesar la imagen."
_MSG_DONE = "Procesamiento completado. Pulsa OK para aplicar el resultado o Cancelar para descartarlo."
_MSG_DISCARDED = "Resultado descartado."
_MSG_ERROR = "Error durante el procesamiento. Puedes volver a intentarlo o pulsar Cancelar."
_MSG_CANCELLING = (
    "Cancelando: la IA no se puede interrumpir; el resultado se descartará cuando termine."
)
_MSG_CLOSE_REFUSED = "Usa «Cancelar» para descartar o «OK» para aplicar el resultado."
_MSG_COMMIT_ERROR = "No se pudo aplicar el resultado."

# Texto de estado por etapa de RMBG; el resto de etapas muestra el mensaje que ellas mismas informan.
_STAGE_MESSAGES = {"Imagen": "Preparando imagen…", "Inferencia": "Eliminando fondo…"}


class RemoveController:
    def __init__(self, design: DesignController) -> None:
        self._design = design
        self._state = RemoveState.READY
        self._view: RemoveView | None = None
        self._original: Image.Image | None = None
        self._result: PreviewResult | None = None
        self._opened = False
        self._cancel_requested = False
        self._last_progress_text: str | None = None

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
    def can_run(self) -> bool:
        return self._opened and self._state in (
            RemoveState.READY,
            RemoveState.CANCELLED,
            RemoveState.ERROR,
        )

    @property
    def can_ok(self) -> bool:
        """OK solo con un resultado terminado y sin tarea en curso."""
        return self._opened and self._state is RemoveState.COMPLETED and self._result is not None

    @property
    def can_cancel(self) -> bool:
        if not self._opened or self._state is RemoveState.CLOSED:
            return False
        if self._state is RemoveState.PROCESSING:
            return not self._cancel_requested  # ya pedida: no se repite
        return True

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
        self._last_progress_text = None
        self._set(RemoveState.PROCESSING)
        accepted = self._design.run_preview(
            TOOL_NAME, on_success=self._on_result, on_error=self._on_error, sink=self
        )
        if not accepted:  # ocupado o sin imagen: la sesión sigue como estaba
            self._set(previous)
        return accepted

    def ok(self) -> bool:
        """«OK»: confirma el resultado en el documento principal y cierra. ``False`` si no procede o falla."""
        if not self.can_ok:
            return False
        result = self._result
        assert result is not None
        try:
            snapshot = self._design.commit_preview(result, TOOL_NAME)
        except Exception as exc:  # noqa: BLE001 - se registra y se informa; el documento queda intacto
            logger.exception("No se pudo confirmar el resultado de Remove")
            self._commit_failed(exc)
            return False
        if snapshot is None:  # se estaba procesando algo: no se confirma
            return False
        self._close()
        return True

    def cancel(self) -> None:
        """«Cancelar»: descarta (ya, o al terminar la IA) y, sin tarea en curso, vuelve a Lumine."""
        if not self.can_cancel:
            return
        if self._state is RemoveState.PROCESSING:
            self._cancel_requested = True
            self._status(_MSG_CANCELLING, StatusLevel.WARNING)
            self._changed()
            return
        self._result = None
        self._close()

    def refuse_close(self) -> None:
        """Intento de cerrar la ventana sin OK ni Cancelar (X, Alt+F4, X de la ventana principal)."""
        if self._state is not RemoveState.CLOSED:
            self._status(_MSG_CLOSE_REFUSED, StatusLevel.WARNING)

    def close(self) -> None:
        """Cierre incondicional (aborto por un fallo al construir la ventana). Idempotente."""
        self._close()

    # ---- sink de la tarea (lo llama DesignController en el hilo principal) ----
    def show_status(self, message: str, level: StatusLevel) -> None:
        self._status(message, level)

    def show_progress(self, event: ProgressEvent) -> None:
        """Etapa de RMBG → texto de estado (sin repetir el mismo mensaje)."""
        text = _STAGE_MESSAGES.get(event.stage, event.message)
        if text != self._last_progress_text:
            self._last_progress_text = text
            self._status(text, StatusLevel.INFO)

    def set_busy(self, busy: bool) -> None:
        if self._view is not None:
            self._view.set_busy(busy)

    # ---- resultado de la tarea ----
    def _on_result(self, preview: Any) -> None:
        if self._state is RemoveState.CLOSED:
            return
        if self._cancel_requested:
            self._discard(_MSG_DISCARDED)
            return
        self._result = preview
        self._set(RemoveState.COMPLETED)
        if self._view is not None:
            self._view.show_image(preview.image, keep_view=True)
        self._status(_MSG_DONE, StatusLevel.SUCCESS)

    def _on_error(self, exc: Exception) -> None:
        # DesignController ya registró el error (log); aquí solo se refleja en la sesión.
        if self._state is RemoveState.CLOSED:
            return
        self._cancel_requested = False
        self._set(RemoveState.ERROR)
        self._status(_MSG_ERROR, StatusLevel.ERROR)

    # ---- internos ----
    def _commit_failed(self, exc: Exception) -> None:
        message = exc.display_message(_MSG_COMMIT_ERROR) if isinstance(exc, DesignToolError) else _MSG_COMMIT_ERROR
        self._result = None  # un resultado que no se pudo aplicar no se vuelve a ofrecer
        self._set(RemoveState.ERROR)
        if self._view is not None and self._original is not None:
            self._view.show_image(self._original, keep_view=True)
        self._status(message, StatusLevel.ERROR)

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
        except Exception:  # noqa: BLE001 - cerrar debe devolver SIEMPRE el control a Lumine
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
