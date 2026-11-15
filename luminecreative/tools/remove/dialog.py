"""tools/remove/dialog.py

Responsabilidad:
    - Ventana (modal) del espacio de trabajo de Remove: su PROPIO visor
      (una instancia nueva de ``ImagePanel``), su ``StatusPanel`` y tres
      botones: Quitar fondo, Cancelar y Salir.
    - Implementar ``RemoveView``: mostrar imágenes, estado y progreso que le
      entrega ``RemoveController``, y habilitar botones y navegación según lo
      que éste (y ``InteractionState``) permiten.

No conoce:
    - Cuándo procede cada acción ni qué pasa al pulsarla: cada botón solo
      llama al controlador. Tampoco rembg ni el motor.

Notas:
    - El visor es independiente del principal: otra instancia de la MISMA
      clase, con su zoom, encuadre y repintado propios. No se copia ni se
      duplica ninguna lógica del visor.
    - Navegación del visor: ``set_navigation_enabled`` recibe lo que dice
      ``InteractionState`` para el ámbito TOOL (libre en reposo; bloqueada
      mientras se procesa). Los botones los decide el estado de la sesión.
    - Seguridad al cerrar: ``close()`` da de baja la suscripción al estado y
      marca la ventana como muerta; cualquier evento posterior (progreso,
      cambio de estado, ``after`` pendiente) se ignora en vez de tocar
      widgets destruidos. La X de la ventana equivale a «Salir».
    - Modal (``transient`` + ``grab_set`` tras 150 ms, como "Tamaño y
      resolución"). No verificado con Tk real: si el menú nativo de la
      ventana principal sigue activo bajo el ``grab``, ``InteractionState``
      igualmente lo mantiene deshabilitado.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from app.controllers.design_controller import StatusLevel
from app.interaction import Action
from core.progress import ProgressEvent
from gui.components.buttons import PrimaryButton, SecondaryButton
from gui.panels.image_panel import ImagePanel
from gui.panels.status_panel import StatusPanel
from tools.remove.controller import RemoveController

_WINDOW_SIZE = "980x760"
_MIN_SIZE = (680, 560)


def ask_exit(processing: bool, parent: tk.Misc | None = None) -> bool:
    """Confirma salir cuando se perdería algo. ``True`` = salir. (Se sustituye en las pruebas.)"""
    if processing:
        message = (
            "La IA todavía está procesando la imagen y no se puede interrumpir.\n\n"
            "Si sales, Remove se cerrará cuando termine y el resultado se descartará.\n"
            "El documento principal no cambia.\n\n¿Salir de todos modos?"
        )
    else:
        message = (
            "Tienes un resultado de «Quitar fondo» sin aplicar.\n\n"
            "Si sales, se descartará. El documento principal no cambia.\n\n¿Salir de todos modos?"
        )
    return bool(messagebox.askyesno("Salir de Remove", message, parent=parent, icon="warning"))


class RemoveDialog(ctk.CTkToplevel):
    """Implementa ``RemoveView``. Crearlo tras ``RemoveController.open()``; se conecta solo."""

    def __init__(self, master, controller: RemoveController) -> None:
        super().__init__(master)
        self._controller = controller
        self._alive = True
        self._unsubscribe = lambda: None  # se reemplaza al final; destroy() debe poder correr antes

        try:
            self._build(controller)
        except Exception:
            self.destroy()  # sin ventana a medias: Lumine no debe quedar con un Toplevel huérfano
            raise

    def _build(self, controller: RemoveController) -> None:
        self.title("Quitar fondo")
        self.geometry(_WINDOW_SIZE)
        self.minsize(*_MIN_SIZE)
        self.transient(self.master)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._viewer = ImagePanel(self)  # visor propio, independiente del principal
        self._viewer.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="nsew")

        self._status = StatusPanel(self)
        self._status.grid(row=1, column=0, padx=16, pady=8, sticky="ew")

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=2, column=0, padx=16, pady=(8, 16), sticky="ew")
        buttons.columnconfigure(0, weight=1)
        self._run_button = PrimaryButton(buttons, "Quitar fondo", controller.run)
        self._run_button.grid(row=0, column=1, padx=(0, 8))
        self._cancel_button = SecondaryButton(buttons, "Cancelar", controller.cancel)
        self._cancel_button.grid(row=0, column=2, padx=(0, 8))
        self._exit_button = SecondaryButton(buttons, "Salir", controller.request_exit)
        self._exit_button.grid(row=0, column=3)

        self.protocol("WM_DELETE_WINDOW", controller.request_exit)  # la X es «Salir»
        self._unsubscribe = controller.interaction.subscribe(lambda _state: self.state_changed())
        self.after(150, self._focus_modal)  # evita fallos de grab_set en algunos SO
        controller.attach_view(self)

    # ---- RemoveView ----
    def show_image(self, image: Image.Image, *, keep_view: bool) -> None:
        if self._alive:
            self._viewer.show(image, keep_view=keep_view)

    def show_status(self, message: str, level: StatusLevel) -> None:
        if self._alive:
            self._status.set_message(message, level)

    def show_progress(self, event: ProgressEvent) -> None:
        if self._alive:
            self._status.set_progress(event)

    def set_busy(self, busy: bool) -> None:
        if self._alive:
            self._status.set_busy(busy)

    def state_changed(self) -> None:
        if not self._alive:
            return
        c = self._controller
        self._set_enabled(self._run_button, c.can_run)
        self._set_enabled(self._cancel_button, c.can_cancel)
        self._set_enabled(self._exit_button, c.can_exit)
        self._viewer.set_navigation_enabled(
            zoom=c.can_interact(Action.ZOOM), pan=c.can_interact(Action.PAN)
        )

    def confirm_exit(self, *, processing: bool) -> bool:
        return ask_exit(processing, parent=self) if self._alive else True

    def close(self) -> None:
        self.destroy()

    # ---- internos ----
    @staticmethod
    def _set_enabled(button: ctk.CTkButton, enabled: bool) -> None:
        button.configure(state="normal" if enabled else "disabled")

    def _focus_modal(self) -> None:
        if not self._alive:
            return
        try:
            self.grab_set()
            self.focus_set()
        except tk.TclError:
            pass  # la ventana aún no es visible en algunos SO; el estado ya bloquea lo principal

    def destroy(self) -> None:
        """Idempotente. Da de baja la suscripción y marca la ventana como muerta antes de destruirla."""
        if self._alive:
            self._alive = False
            self._unsubscribe()
            try:
                self.grab_release()
            except tk.TclError:
                pass  # nunca se llegó a tomar el grab
        super().destroy()
