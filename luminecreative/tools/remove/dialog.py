"""tools/remove/dialog.py

Responsabilidad:
    - Ventana (modal) del espacio de trabajo de Remove: su PROPIO visor
      (una instancia nueva de ``ImagePanel``, con tablero de transparencia y
      zoom mínimo = zoom de ajuste de la imagen completa) y un contenedor inferior con la barra de progreso,
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
    - Barra de carga: UNA instancia de ``CTkProgressBar`` por ventana, creada en
      ``_build_progress_bar`` y reutilizada en cada ejecución (no se destruye ni
      se recrea; la barra principal de Lumine es otra instancia). Es solo la barra,
      sin tarjeta ni fondo, hermana del visor y creada después, anclada al canvas
      de la imagen con ``place(in_=..., relx=.5, rely=.5)``: queda centrada sobre
      el área visible, Tk la recentra sola al redimensionar, no entra en el
      ``grid`` (no cambia las medidas del visor al mostrarla/ocultarla), no es un
      elemento del canvas ni pasa por el renderizador (la imagen no se toca) y solo
      intercepta el ratón en su propio rectángulo. Mide ~5 cm (189 px a 96 DPI) y
      tiene extremos rectos para no dejar fondo alrededor (sin transparencia real).
    - Sin textos de carga: mientras RMBG trabaja, ``show_status`` vacía los mensajes
      INFO (inicio, etapas); la barra es el único indicador. Los errores y los avisos
      (p. ej. «se descartará al terminar») se siguen mostrando.
    - Estados de la barra: OCULTA y sin animación al abrir y tras terminar. Con
      ``set_busy(True)`` aparece y avanza SIEMPRE hacia la derecha con una curva de
      espera (``wait_value``) que frena y nunca llega al final: sin reinicios, sin
      rebote. Es solo movimiento: no es un avance real ni se muestra ningún
      porcentaje. Si la sesión termina en COMPLETED, completa el recorrido hasta el
      100 % (``finish_value``, 0,3 s), se queda llena 0,15 s y desaparece; en
      error, descarte o cierre se oculta de inmediato SIN completar. Ni el zoom, ni
      el paneo ni los cambios de estado la vuelven a mostrar.
    - Animación: un único ``after`` (``_bar_job``) que se reprograma a sí mismo cada
      20 ms solo mientras la barra es visible; ``_hide_bar`` y ``destroy`` lo cancelan.
      Distinguir éxito de error no necesita el controlador: ``set_busy(False)`` llega
      justo antes del estado final (misma llamada de ``DesignController``) y
      ``state_changed`` lo resuelve (``_resolve_bar``).
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
import math
import sys
import tkinter as tk
from time import perf_counter

import customtkinter as ctk
from PIL import Image

from app.controllers.design_controller import StatusLevel
from app.interaction import Action
from gui.components.buttons import PrimaryButton, SecondaryButton
from gui.panels.image_panel import ImagePanel
from gui.panels.status_panel import STATUS_COLORS
from tools.remove.controller import RemoveController, RemoveState

logger = logging.getLogger(__name__)

# Barra de carga: ~5 cm (189 px a 96 DPI; CustomTkinter escala el ancho lógico con el DPI de la pantalla).
# Es solo la barra (sin tarjeta ni fondo), centrada sobre el área de la imagen.
_BAR_WIDTH, _BAR_HEIGHT = 189, 8
_FRAME_MS = 20  # paso del repintado; la posición sale del reloj, no del número de pasos (sin tirones)
_WAIT_TAU_S = 2.5  # ritmo de la curva de espera: ~50 % a los 2,5 s; frena sin llegar nunca al final
_WAIT_CEILING = 0.95  # la espera nunca pasa de aquí: el 100 % solo lo pone la finalización real
_FINISH_S = 0.30  # al terminar bien: completa el recorrido hasta el 100 %
_HOLD_S = 0.15  # y se queda llena este instante antes de desaparecer

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


def wait_value(elapsed: float) -> float:
    """Posición (0-1) de la barra a los ``elapsed`` s de espera. Solo avanza hacia la derecha: no
    reinicia, no rebota y frena de forma suave (nunca llega a ``_WAIT_CEILING``). Es SOLO movimiento
    para indicar que RMBG trabaja: NO es un avance real de la inferencia ni se muestra como %."""
    elapsed = max(elapsed, 0.0)
    return _WAIT_CEILING * elapsed / (elapsed + _WAIT_TAU_S)


def finish_value(start: float, elapsed: float) -> float:
    """Llenado final: de ``start`` a 1,0 en ``_FINISH_S`` s (frenando al llegar)."""
    k = min(max(elapsed / _FINISH_S, 0.0), 1.0)
    return start + (1.0 - start) * (1.0 - (1.0 - k) ** 2)


class RemoveDialog(ctk.CTkToplevel):
    """Implementa ``RemoveView``. Crearlo tras ``RemoveController.open()``; se conecta solo."""

    def __init__(self, master, controller: RemoveController) -> None:
        super().__init__(master)
        self._controller = controller
        self._alive = True
        self._busy = False
        self._bar_job: str | None = None  # el ÚNICO ``after`` de la animación de la barra
        self._bar_t0 = 0.0  # inicio de la espera en curso
        self._bar_finish_t0: float | None = None  # inicio del llenado final (None = aún barriendo)
        self._bar_finish_from = 0.0
        self._bar_pending = False  # RMBG terminó; falta saber si bien (COMPLETED) o no
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
        self._viewer = ImagePanel(self, fit_min_zoom=True, transparency_checkerboard=True)
        self._viewer.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="nsew")

        # Contenedor inferior: mensaje y barra a la izquierda, botones a la derecha.
        bottom = ctk.CTkFrame(self, corner_radius=12)
        bottom.grid(row=1, column=0, padx=16, pady=(8, 16), sticky="ew")
        bottom.columnconfigure(0, weight=1)

        self._message = ctk.CTkLabel(
            bottom, text="", anchor="nw", justify="left", height=_MESSAGE_HEIGHT
        )
        self._message.grid(row=0, column=0, padx=(16, 8), pady=12, sticky="ew")
        # La barra NO va aquí abajo: vive en una capa propia sobre el visor (ver más abajo).
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

        self._build_progress_bar()
        self.protocol("WM_DELETE_WINDOW", controller.refuse_close)  # sin X: solo OK o Cancelar
        self._unsubscribe = controller.interaction.subscribe(lambda _state: self.state_changed())
        self.after(_SETUP_DELAY_MS, self._finish_window_setup)
        controller.attach_view(self)

    # ---- RemoveView ----
    def show_image(self, image: Image.Image, *, keep_view: bool) -> None:
        if self._alive:
            self._viewer.show(image, keep_view=keep_view)

    def show_status(self, message: str, level: StatusLevel) -> None:
        if not self._alive:
            return
        if self._busy and level is StatusLevel.INFO:
            message = ""  # la barra es el único indicador de carga: sin textos de etapa ni estados
        self._message.configure(text=message, text_color=STATUS_COLORS[level])

    def set_busy(self, busy: bool) -> None:
        if not self._alive:
            return
        self._busy = busy
        if busy:
            self._start_bar()
        else:
            # RMBG terminó, pero aún no se sabe si bien: el estado final llega justo después (misma
            # llamada de DesignController) y ``state_changed`` lo resuelve.
            self._bar_pending = True
            self._resolve_bar()

    def state_changed(self) -> None:
        if not self._alive:
            return
        c = self._controller
        self._set_enabled(self._run_button, c.can_run)
        self._set_enabled(self._cancel_button, c.can_cancel)
        self._set_enabled(self._ok_button, c.can_ok)
        self._viewer.set_navigation_enabled(
            zoom=c.can_interact(Action.ZOOM), pan=c.can_interact(Action.PAN)
        )
        self._resolve_bar()

    def close(self) -> None:
        self.destroy()

    # ---- internos ----
    @staticmethod
    def _set_enabled(button: ctk.CTkButton, enabled: bool) -> None:
        button.configure(state="normal" if enabled else "disabled")

    # ---- barra de carga: mostrar, animar, completar y ocultar (una instancia, un ``after``) ----
    def _build_progress_bar(self) -> None:
        """Crea, UNA vez, la barra. Pertenece al diálogo (no al visor ni al renderizador): es un widget
        hermano del visor creado DESPUÉS, así que Tk lo apila por encima de él. Se ancla al canvas de la
        imagen con ``place(in_=...)``: Tk la mantiene centrada al cambiar el tamaño del visor sin
        callbacks, y como ``place`` no entra en el ``grid`` nunca cambia sus medidas.

        Sin tarjeta: Tk/CustomTkinter no tienen transparencia por píxel (``"transparent"`` solo copia
        el color del contenedor). Una pista redondeada dejaría en las esquinas píxeles del color del
        diálogo sobre la imagen; con extremos rectos (``corner_radius=0``) la pista llena todo el
        widget y no queda ningún fondo alrededor.

        Determinada: se mueve con ``set`` (el modo indeterminado de la librería rebota y no permite
        «completar»)."""
        self._progress = ctk.CTkProgressBar(
            self, mode="determinate", width=_BAR_WIDTH, height=_BAR_HEIGHT, corner_radius=0
        )
        self._progress.set(0)

    def _show_bar(self) -> None:
        self._progress.place(in_=self._viewer.view_area, relx=0.5, rely=0.5, anchor="center")

    def _start_bar(self) -> None:
        self._cancel_bar_job()
        self._bar_pending = False
        self._bar_finish_t0 = None
        self._bar_t0 = perf_counter()
        self._progress.set(0)
        self._show_bar()
        self._bar_tick()

    def _resolve_bar(self) -> None:
        """Tras ``set_busy(False)``: éxito → completa el recorrido y desaparece; cualquier otro
        final (error, descartado, cerrado) → se oculta sin completar. Espera mientras la sesión
        siga PROCESANDO (el estado final llega enseguida)."""
        if not self._bar_pending or self._busy:
            return
        state = self._controller.state
        if state is RemoveState.PROCESSING:
            return
        self._bar_pending = False
        if state is RemoveState.COMPLETED:
            self._bar_finish_from = wait_value(perf_counter() - self._bar_t0)
            self._bar_finish_t0 = perf_counter()
            if self._bar_job is None:
                self._bar_tick()
        else:
            self._hide_bar()

    def _bar_tick(self) -> None:
        self._bar_job = None
        if not self._alive:
            return
        now = perf_counter()
        if self._bar_finish_t0 is None:
            value = wait_value(now - self._bar_t0)
        else:
            elapsed = now - self._bar_finish_t0
            if elapsed >= _FINISH_S + _HOLD_S:
                self._hide_bar()
                return
            value = finish_value(self._bar_finish_from, elapsed)
        self._progress.set(value)
        self._bar_job = self.after(_FRAME_MS, self._bar_tick)

    def _hide_bar(self) -> None:
        self._cancel_bar_job()
        self._bar_pending = False
        self._bar_finish_t0 = None
        self._progress.place_forget()
        self._progress.set(0)

    def _cancel_bar_job(self) -> None:
        job, self._bar_job = self._bar_job, None
        if job is not None:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass

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
            self._cancel_bar_job()  # sin animación ni callback de carga tras cerrar
            try:
                self.grab_release()
            except tk.TclError:
                pass  # nunca se llegó a tomar el grab
        super().destroy()
