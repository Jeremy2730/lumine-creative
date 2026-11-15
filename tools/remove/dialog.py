"""tools/remove/dialog.py

Responsabilidad:
    - Ventana (modal) del espacio de trabajo de Remove: su PROPIO visor
      (una instancia nueva de ``ImagePanel``, con tablero de transparencia y
      zoom mínimo del 70 %) y un contenedor inferior con la barra de progreso,
      el mensaje de estado y tres botones: Quitar fondo, Cancelar y OK.
    - Implementar ``RemoveView``: mostrar imágenes y mensajes que entrega
      ``RemoveController`` y habilitar botones y navegación según lo que éste
      (y ``InteractionState``) permiten.

No conoce:
    - Cuándo procede cada acción ni qué pasa al pulsarla: cada botón solo
      llama al controlador. Tampoco rembg ni el motor.

Notas:
    - El visor es independiente del principal: otra instancia de la MISMA
      clase, con su zoom, encuadre y repintado propios. No se duplica nada.
    - Sin «Salir» ni X: la ventana solo se cierra con OK (confirma) o Cancelar
      (descarta). El protocolo de cierre de la ventana llama a
      ``RemoveController.refuse_close`` (que avisa en el mensaje) y, en Windows,
      además se quita el menú del sistema para que no se dibuje el botón X
      (``_hide_close_button``). Eso último usa la API de Windows y no se ha
      verificado con Tk real; si fallara, la X se vería pero seguiría sin cerrar.
    - Contenedor inferior de tamaño estable: el mensaje tiene alto fijo (hasta
      tres líneas) y la barra está siempre visible; nada aparece ni desaparece al
      cambiar el estado. La barra es INDETERMINADA mientras se procesa (la
      inferencia no informa su avance, así que no se inventa un porcentaje), vacía
      en reposo y llena cuando el resultado está listo.
    - Navegación del visor: ``set_navigation_enabled`` recibe lo que dice
      ``InteractionState`` para el ámbito TOOL (libre en reposo; bloqueada
      mientras se procesa). Los botones los decide el estado de la sesión.
    - Seguridad al cerrar: ``destroy()`` da de baja la suscripción al estado y
      marca la ventana como muerta; cualquier evento posterior (cambio de estado,
      ``after`` pendiente) se ignora en vez de tocar widgets destruidos.
    - Modal (``transient`` + ``grab_set`` tras 150 ms, como "Tamaño y
      resolución"). No verificado con Tk real aquí.
"""
from __future__ import annotations

import logging
import sys
import tkinter as tk

import customtkinter as ctk
from PIL import Image

from app.controllers.design_controller import StatusLevel
from app.interaction import Action
from gui.components.buttons import PrimaryButton, SecondaryButton
from gui.panels.image_panel import ImagePanel
from gui.panels.status_panel import STATUS_COLORS
from tools.remove.controller import RemoveController, RemoveState

logger = logging.getLogger(__name__)

MIN_ZOOM = 0.70  # zoom mínimo del visor de Remove (70 %)

_WINDOW_SIZE = "980x760"
_MIN_SIZE = (680, 560)
_MESSAGE_HEIGHT = 58  # alto fijo del mensaje: hasta tres líneas, sin recortar ni mover el resto
_BUTTON_WIDTH, _BUTTON_HEIGHT = 96, 30  # algo menores que los botones habituales (36-38 px de alto)
_BUTTON_GAP = 8
_SETUP_DELAY_MS = 250  # tras el icono que CustomTkinter pone a los 200 ms en Windows

# Constantes de la API de Windows para quitar el menú del sistema (y con él la X).
_GWL_STYLE = -16
_WS_SYSMENU = 0x00080000
_SWP_NOSIZE, _SWP_NOMOVE, _SWP_NOZORDER, _SWP_FRAMECHANGED = 0x0001, 0x0002, 0x0004, 0x0020


class RemoveDialog(ctk.CTkToplevel):
    """Implementa ``RemoveView``. Crearlo tras ``RemoveController.open()``; se conecta solo."""

    def __init__(self, master, controller: RemoveController) -> None:
        super().__init__(master)
        self._controller = controller
        self._alive = True
        self._busy = False
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

        # Visor propio, independiente del principal.
        self._viewer = ImagePanel(self, min_zoom=MIN_ZOOM, transparency_checkerboard=True)
        self._viewer.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="nsew")

        # Contenedor inferior: mensaje y barra a la izquierda, botones a la derecha.
        bottom = ctk.CTkFrame(self, corner_radius=12)
        bottom.grid(row=1, column=0, padx=16, pady=(8, 16), sticky="ew")
        bottom.columnconfigure(0, weight=1)

        self._message = ctk.CTkLabel(
            bottom, text="", anchor="nw", justify="left", height=_MESSAGE_HEIGHT
        )
        self._message.grid(row=0, column=0, padx=(16, 8), pady=(12, 4), sticky="ew")
        self._progress = ctk.CTkProgressBar(bottom, mode="determinate", height=8)
        self._progress.set(0)
        self._progress.grid(row=1, column=0, padx=(16, 8), pady=(0, 14), sticky="ew")
        text_reserved = 3 * _BUTTON_WIDTH + 2 * _BUTTON_GAP + 16 + 16 + 8 + 16
        bottom.bind(
            "<Configure>",
            lambda e: self._message.configure(wraplength=max(e.width - text_reserved, 120)),
        )

        buttons = ctk.CTkFrame(bottom, fg_color="transparent")
        buttons.grid(row=0, column=1, rowspan=2, padx=(0, 16), pady=12, sticky="e")
        self._run_button = SecondaryButton(buttons, "Quitar fondo", controller.run)
        self._cancel_button = SecondaryButton(buttons, "Cancelar", controller.cancel)
        self._ok_button = PrimaryButton(buttons, "OK", controller.ok)
        for column, button in enumerate((self._run_button, self._cancel_button, self._ok_button)):
            button.configure(width=_BUTTON_WIDTH, height=_BUTTON_HEIGHT)
            button.grid(row=0, column=column, padx=(0 if column == 0 else _BUTTON_GAP, 0))

        self.protocol("WM_DELETE_WINDOW", controller.refuse_close)  # sin X: solo OK o Cancelar
        self._unsubscribe = controller.interaction.subscribe(lambda _state: self.state_changed())
        self.after(_SETUP_DELAY_MS, self._finish_window_setup)
        controller.attach_view(self)

    # ---- RemoveView ----
    def show_image(self, image: Image.Image, *, keep_view: bool) -> None:
        if self._alive:
            self._viewer.show(image, keep_view=keep_view)

    def show_status(self, message: str, level: StatusLevel) -> None:
        if self._alive:
            self._message.configure(text=message, text_color=STATUS_COLORS[level])

    def set_busy(self, busy: bool) -> None:
        if not self._alive:
            return
        self._busy = busy
        self._progress.stop()
        if busy:
            self._progress.configure(mode="indeterminate")  # sin porcentaje inventado
            self._progress.start()
        else:
            self._progress.configure(mode="determinate")
            self._progress.set(0)

    def state_changed(self) -> None:
        if not self._alive:
            return
        c = self._controller
        self._set_enabled(self._run_button, c.can_run)
        self._set_enabled(self._cancel_button, c.can_cancel)
        self._set_enabled(self._ok_button, c.can_ok)
        if not self._busy:  # barra llena solo cuando el resultado está listo
            self._progress.set(1 if c.state is RemoveState.COMPLETED else 0)
        self._viewer.set_navigation_enabled(
            zoom=c.can_interact(Action.ZOOM), pan=c.can_interact(Action.PAN)
        )

    def close(self) -> None:
        self.destroy()

    # ---- internos ----
    @staticmethod
    def _set_enabled(button: ctk.CTkButton, enabled: bool) -> None:
        button.configure(state="normal" if enabled else "disabled")

    def _finish_window_setup(self) -> None:
        """Modal y sin botón X. Se difiere para que la ventana ya exista en pantalla."""
        if not self._alive:
            return
        try:
            self.grab_set()
            self.focus_set()
        except tk.TclError:
            pass  # la ventana aún no es visible en algunos SO; el estado ya bloquea lo principal
        self._hide_close_button()

    def _hide_close_button(self) -> None:
        """Windows: quita el menú del sistema, con lo que desaparece la X. Cualquier fallo se ignora."""
        if sys.platform != "win32":
            return
        try:
            import ctypes

            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            hwnd = user32.GetParent(self.winfo_id()) or self.winfo_id()
            style = user32.GetWindowLongW(hwnd, _GWL_STYLE)
            user32.SetWindowLongW(hwnd, _GWL_STYLE, style & ~_WS_SYSMENU)
            user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER | _SWP_FRAMECHANGED,
            )
        except Exception:  # noqa: BLE001 - es cosmético: refuse_close sigue impidiendo el cierre
            logger.debug("No se pudo quitar el botón de cierre de la ventana de Remove", exc_info=True)

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
