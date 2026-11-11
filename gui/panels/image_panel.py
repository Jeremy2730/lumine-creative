"""gui/panels/image_panel.py

Responsabilidad:
    - Mostrar la imagen actual dentro de un canvas, colocada y escalada
      según un ``ViewportModel``: el modelo es la única fuente de verdad de
      zoom, posición, centrado y tamaño renderizado.
    - Conectar tres piezas sin duplicar sus responsabilidades: el modelo
      (``gui/viewport.py``, geometría), el renderizador
      (``gui/viewport_renderer.py``, píxeles) y el canvas (pintar).
    - Redibujar cuando cambia el tamaño del área, agrupando las ráfagas de
      eventos de redimensionado en un único renderizado (80 ms de calma).
    - Mostrar el texto de ayuda cuando todavía no hay imagen.
    - Interacción: zoom con la rueda anclado al cursor, paneo (botón central
      o espacio + botón izquierdo), controles de zoom (acercar, alejar,
      ajustar, 100 %, porcentaje) y barras de desplazamiento. Todo se
      traduce a llamadas al modelo; el panel solo capta eventos y presenta.

No conoce:
    - El motor, los controladores ni el estado de la aplicación: solo
      recibe la imagen a mostrar vía ``show()``.
    - Cómo se calcula la geometría ni cómo se producen los píxeles.

Notas de interacción (fase 1 del visor):
    - Cada evento (rueda, arrastre, barra, botón) modifica el modelo AL
      INSTANTE (es aritmética, sin píxeles) y solo el repintado se agrupa:
      un único ``after`` de ``_FRAME_MS`` pendiente a la vez. Así el anclaje
      al cursor es exacto con cada evento, no se acumulan callbacks y una
      ráfaga produce un solo render. Si el evento no cambia el estado del
      modelo (zoom en el límite, paneo contra el borde) no se programa nada.
    - El paneo no suma deltas: coloca la imagen en "posición al pulsar +
      desplazamiento total del ratón", de modo que no hay deriva por
      redondeos acumulados, y se aplica con ``ViewportModel.pan_by``.
    - Las barras ocupan un hueco FIJO (se muestran u ocultan por dentro) para
      que ocultarlas no cambie el tamaño del canvas ni provoque un bucle
      "cambia el canvas → cambia si cabe → cambia la barra".
    - Todo el trabajo ocurre en el hilo de la interfaz: eventos, ``after``,
      ``ImageTk.PhotoImage`` (referenciado en ``_photo``) y destrucción.
      ``destroy()`` cancela los ``after`` pendientes y los callbacks que
      aún se disparen tras destruir se ignoran.
    - Tiempos: cada repintado real guarda un ``RenderTiming`` (renderizador,
      creación del ``PhotoImage`` y total) en ``render_timings``; los lentos
      (> ``_SLOW_RENDER_MS``) se registran en el log.
    - Escala de pantalla: ver ``gui/viewport_interaction.py``.

Notas:
    - ``show(image, keep_view=False)``: una imagen nueva se ajusta al área;
      con ``keep_view=True`` (resultado de una herramienta sobre el mismo
      documento) se conserva el modo y el encuadre del modelo. Quien llama
      decide cuál de los dos casos es.
    - Es solo visualización: ``show()`` guarda una REFERENCIA a la imagen
      (no una copia) y nunca la modifica; el renderizador solo la lee.
    - El viewport se mide en píxeles reales del canvas. Antes, con
      ``CTkLabel`` + ``CTkImage``, el espacio disponible (píxeles reales) se
      entregaba a CustomTkinter como tamaño lógico y este lo volvía a
      multiplicar por la escala de pantalla: con escala 1,5 la imagen se
      dibujaba 1,5 veces mayor que el espacio disponible.
    - El margen interior (16 px por lado) equivale al que se restaba antes
      (32 px por eje), así que a escala 1,0 la imagen ocupa el mismo sitio.
    - ``viewport`` y ``redraw()`` siguen siendo el punto de entrada para
      quien quiera modificar el modelo desde fuera y repintar.
    - Límite conocido: el texto de ayuda se dibuja con la fuente base de
      CustomTkinter sin su escalado por DPI (solo afecta a ese texto).
"""
from __future__ import annotations

import logging
import tkinter as tk
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import perf_counter

import customtkinter as ctk
from PIL import Image, ImageTk

from gui.components.buttons import SecondaryButton
from gui.viewport import ViewportModel
from gui.viewport_interaction import (
    SCROLL_PAGE_FRACTION,
    SCROLL_UNIT_PX,
    ZOOM_STEP_BUTTON,
    actual_size_zoom,
    format_zoom_percent,
    parse_scroll_command,
    physical_per_canvas_pixel,
    wheel_notches,
    wheel_zoom_factor,
)
from gui.viewport_renderer import RenderedView, ViewportRenderer

logger = logging.getLogger(__name__)

_PLACEHOLDER_TEXT = "Abre una imagen para comenzar\n(menú Archivos ▸ Abrir…  ·  Ctrl+O)"
_PLACEHOLDER_COLOR = ("gray40", "gray60")


def _color_for_mode(color: str | Sequence[str]) -> str:
    """Resuelve un color de CustomTkinter, ``(claro, oscuro)``, para el modo actual."""
    if isinstance(color, str):
        return color
    return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]




@dataclass(frozen=True)
class RenderTiming:
    """Medición de un repintado real (milisegundos)."""

    render_ms: float  # ViewportRenderer.render: recorte + remuestreo
    photo_ms: float  # ImageTk.PhotoImage + canvas
    total_ms: float
    zoom: float
    source_size: tuple[int, int]  # imagen original
    drawn_size: tuple[int, int]  # píxeles generados para el canvas


@dataclass
class _PanDrag:
    button: int
    mouse_x: int
    mouse_y: int
    origin_x: float
    origin_y: float


class ImagePanel(ctk.CTkFrame):
    """Muestra la imagen según un ``ViewportModel``; nunca modifica la imagen del motor."""

    _MARGIN = 16
    _RESIZE_QUIET_MS = 80
    _FRAME_MS = 16  # agrupa la rueda / el arrastre en como mucho ~60 repintados por segundo
    _BAR_PX = 14  # grosor de las barras de desplazamiento
    _BAR_GAP = 4
    _SLOW_RENDER_MS = 100.0
    _TIMING_HISTORY = 200

    def __init__(self, master, *, pixel_ratio: Callable[[], float] | None = None) -> None:
        super().__init__(master, corner_radius=12, height=340)
        self.grid_propagate(False)  # el contenido no debe dictar el tamaño del panel
        self._pixel_ratio = pixel_ratio or physical_per_canvas_pixel
        self._model: ViewportModel | None = None
        self._renderer = ViewportRenderer()
        self._shown: RenderedView | None = None
        self._photo: ImageTk.PhotoImage | None = None  # referencia: Tk no la retiene
        self._resize_job: str | None = None
        self._frame_job: str | None = None
        self._destroyed = False
        self._space_down = False
        self._pan: _PanDrag | None = None
        self._zoom_enabled = True  # los decide quien manda (MainWindow según InteractionState);
        self._pan_enabled = True  # el panel no conoce políticas, solo estos dos permisos
        self._timings: deque[RenderTiming] = deque(maxlen=self._TIMING_HISTORY)
        self._chrome: dict[str, object] = {}  # último estado aplicado a los controles

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._canvas = tk.Canvas(
            self, bg=_color_for_mode(self.cget("fg_color")), highlightthickness=0, bd=0, takefocus=1
        )
        self._canvas.grid(
            row=0, column=0, sticky="nsew", padx=(self._MARGIN, 0), pady=(self._MARGIN, 0)
        )
        self._build_scrollbars()
        self._build_toolbar()
        self._placeholder_font = ctk.CTkFont()
        self._bind_events()
        self._draw_placeholder()
        self._sync_chrome()

    # ------------------------------------------------------------ API pública
    @property
    def viewport(self) -> ViewportModel | None:
        """Modelo geométrico de la vista (``None`` mientras no haya imagen)."""
        return self._model

    @property
    def render_timings(self) -> tuple[RenderTiming, ...]:
        """Mediciones de los últimos repintados reales (los más recientes al final)."""
        return tuple(self._timings)

    def render_stats(self) -> dict[str, float]:
        """Resumen (n, media, p95 y máximo del total en ms) de ``render_timings``."""
        totals = sorted(t.total_ms for t in self._timings)
        if not totals:
            return {"count": 0}
        p95 = totals[min(len(totals) - 1, int(len(totals) * 0.95))]
        return {
            "count": len(totals),
            "mean_ms": sum(totals) / len(totals),
            "p95_ms": p95,
            "max_ms": totals[-1],
        }

    def show(self, image: Image.Image, *, keep_view: bool = False) -> None:
        """Muestra ``image``. ``keep_view=False`` la ajusta al área; ``True`` conserva el encuadre."""
        self._cancel_pending_render()
        self._end_pan()
        width, height = image.size
        viewport = self._viewport_size()
        if self._model is None:
            self._model = ViewportModel((width, height), viewport)
        else:
            self._model.set_viewport_size(*viewport)
            self._model.set_image_size(width, height, keep_view=keep_view)
        self._renderer.set_image(image)
        self._render()

    def redraw(self) -> None:
        """Vuelve a pintar ahora el estado actual del modelo."""
        self._cancel_pending_render()
        self._render()

    # Acciones de los controles (también útiles desde fuera). Solo cambian el modelo.
    def zoom_in(self) -> None:
        self._interact(lambda m: m.zoom_by(ZOOM_STEP_BUTTON), needs="zoom")

    def zoom_out(self) -> None:
        self._interact(lambda m: m.zoom_by(1.0 / ZOOM_STEP_BUTTON), needs="zoom")

    def fit_to_window(self) -> None:
        self._interact(lambda m: m.fit(), needs="zoom")

    def actual_size(self) -> None:
        """100 %: un píxel de imagen por píxel físico de pantalla (ver ``viewport_interaction``)."""
        self._interact(lambda m: m.set_zoom(actual_size_zoom(self._pixel_ratio())), needs="zoom")

    def set_navigation_enabled(self, *, zoom: bool, pan: bool) -> None:
        """Permite o impide zoom y paneo del usuario (rueda, arrastre, barras, botones).

        No cambia la vista ni el modelo; la imagen sigue mostrándose igual y el redimensionado
        de la ventana sigue funcionando. Un arrastre en curso se cancela al bloquear el paneo.
        """
        if self._destroyed:
            return
        self._zoom_enabled, self._pan_enabled = zoom, pan
        if not pan:
            self._end_pan()
        self._sync_chrome()

    def destroy(self) -> None:
        self._destroyed = True
        self._cancel_pending_render()
        self._pan = None
        self._shown = None
        self._photo = None
        super().destroy()

    # ------------------------------------------------------------ construcción
    def _build_scrollbars(self) -> None:
        """Barras dentro de contenedores de tamaño fijo: ocultarlas no mueve nada."""
        self._vbar_box = ctk.CTkFrame(self, width=self._BAR_PX, fg_color="transparent")
        self._vbar_box.grid(
            row=0, column=1, sticky="ns", padx=(self._BAR_GAP, self._MARGIN), pady=(self._MARGIN, 0)
        )
        self._vbar_box.pack_propagate(False)
        self._vbar = ctk.CTkScrollbar(
            self._vbar_box, orientation="vertical", command=lambda *a: self._on_scrollbar(1, *a)
        )
        self._hbar_box = ctk.CTkFrame(self, height=self._BAR_PX, fg_color="transparent")
        self._hbar_box.grid(
            row=1, column=0, sticky="ew", padx=(self._MARGIN, 0), pady=(self._BAR_GAP, 0)
        )
        self._hbar_box.pack_propagate(False)
        self._hbar = ctk.CTkScrollbar(
            self._hbar_box, orientation="horizontal", command=lambda *a: self._on_scrollbar(0, *a)
        )
        self._bars = (self._hbar, self._vbar)  # índice = eje del modelo (0 horizontal, 1 vertical)
        self._bar_visible = [False, False]

    def _build_toolbar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=2, column=0, columnspan=2, pady=(8, 10))

        def button(text: str, command: Callable[[], None], width: int) -> SecondaryButton:
            widget = SecondaryButton(bar, text, command)
            widget.configure(height=28, width=width)
            widget.pack(side="left", padx=3)
            return widget

        self._zoom_out_button = button("−", self.zoom_out, 36)
        self._zoom_label = ctk.CTkLabel(bar, text="— %", width=64)
        self._zoom_label.pack(side="left", padx=3)
        self._zoom_in_button = button("+", self.zoom_in, 36)
        self._fit_button = button("Ajustar", self.fit_to_window, 72)
        self._actual_button = button("100 %", self.actual_size, 64)
        self._buttons = (
            self._zoom_out_button,
            self._zoom_in_button,
            self._fit_button,
            self._actual_button,
        )

    def _bind_events(self) -> None:
        canvas = self._canvas
        canvas.bind("<Configure>", self._on_configure)
        canvas.bind("<MouseWheel>", self._on_wheel)  # Windows (y macOS)
        canvas.bind("<Button-4>", self._on_wheel)  # Linux / X11
        canvas.bind("<Button-5>", self._on_wheel)
        canvas.bind("<ButtonPress-2>", lambda e: self._begin_pan(e, 2))
        canvas.bind("<B2-Motion>", lambda e: self._move_pan(e, 2))
        canvas.bind("<ButtonRelease-2>", lambda e: self._finish_pan(2))
        canvas.bind("<ButtonPress-1>", self._on_left_press)
        canvas.bind("<B1-Motion>", lambda e: self._move_pan(e, 1))
        canvas.bind("<ButtonRelease-1>", lambda e: self._finish_pan(1))
        canvas.bind("<Enter>", lambda e: canvas.focus_set())  # para recibir la barra espaciadora
        canvas.bind("<KeyPress-space>", self._on_space_press)
        canvas.bind("<KeyRelease-space>", self._on_space_release)
        canvas.bind("<FocusOut>", self._on_focus_out)

    # ---------------------------------------------------------------- internos
    def _viewport_size(self) -> tuple[int, int]:
        return self._canvas.winfo_width(), self._canvas.winfo_height()

    def _cancel_pending_render(self) -> None:
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
            self._resize_job = None
        self._cancel_frame_job()

    def _cancel_frame_job(self) -> None:
        if self._frame_job is not None:
            self.after_cancel(self._frame_job)
            self._frame_job = None

    def _on_configure(self, _event) -> None:
        if self._destroyed:
            return
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(self._RESIZE_QUIET_MS, self._render)

    # --- cambios del modelo + repintado agrupado
    @staticmethod
    def _state(model: ViewportModel) -> tuple:
        return model.zoom, model.position, model.viewport_size, model.fit_mode

    def _interact(self, action: Callable[[ViewportModel], None], *, needs: str) -> bool:
        """Aplica ``action`` al modelo y, si cambió algo, pide UN repintado. Devuelve si cambió.

        ``needs`` ("zoom" o "pan") es el permiso que exige; sin él no se hace nada.
        """
        model = self._model
        if model is None or self._destroyed:
            return False
        if not (self._zoom_enabled if needs == "zoom" else self._pan_enabled):
            return False
        before = self._state(model)
        model.set_viewport_size(*self._viewport_size())  # no hace nada si no cambió
        action(model)
        if self._state(model) == before:
            return False
        self._request_render()
        return True

    def _request_render(self) -> None:
        if self._frame_job is None and not self._destroyed:
            self._frame_job = self.after(self._FRAME_MS, self._render)

    # --- rueda
    def _on_wheel(self, event) -> None:
        notches = wheel_notches(delta=getattr(event, "delta", 0), num=getattr(event, "num", 0))
        if notches == 0:
            return
        factor = wheel_zoom_factor(notches)
        anchor = (event.x, event.y)
        self._interact(lambda m: m.zoom_by(factor, anchor), needs="zoom")

    # --- paneo
    def _on_left_press(self, event) -> None:
        self._canvas.focus_set()
        if self._space_down:
            self._begin_pan(event, 1)

    def _begin_pan(self, event, button: int) -> None:
        model = self._model
        if model is None or self._pan is not None or not self._pan_enabled:
            return
        model.set_viewport_size(*self._viewport_size())
        x, y = model.position
        self._pan = _PanDrag(button, event.x, event.y, x, y)
        self._canvas.configure(cursor="fleur")

    def _move_pan(self, event, button: int) -> None:
        drag = self._pan
        if drag is None or drag.button != button:
            return
        target_x = drag.origin_x + (event.x - drag.mouse_x)
        target_y = drag.origin_y + (event.y - drag.mouse_y)
        self._interact(
            lambda m: m.pan_by(target_x - m.position[0], target_y - m.position[1]), needs="pan"
        )

    def _finish_pan(self, button: int) -> None:
        if self._pan is not None and self._pan.button == button:
            self._end_pan()

    def _end_pan(self) -> None:
        self._pan = None
        self._update_cursor()

    def _on_space_press(self, _event) -> None:
        self._space_down = True
        self._update_cursor()

    def _on_space_release(self, _event) -> None:
        self._space_down = False
        self._update_cursor()

    def _on_focus_out(self, _event) -> None:
        self._space_down = False  # no dejar "espacio pulsado" si la ventana pierde el foco
        self._end_pan()

    def _update_cursor(self) -> None:
        if self._destroyed:
            return
        if self._pan is not None:
            cursor = "fleur"
        elif self._space_down:
            cursor = "hand2"
        else:
            cursor = ""
        self._canvas.configure(cursor=cursor)

    # --- barras de desplazamiento
    def _on_scrollbar(self, axis: int, *args) -> None:
        command = parse_scroll_command(args)
        if command is None:
            return
        kind, value = command

        def action(model: ViewportModel) -> None:
            if kind == "moveto":
                model.scroll_to_fraction(axis, value)
                return
            step = SCROLL_UNIT_PX if kind == "units" else SCROLL_PAGE_FRACTION * model.viewport_size[axis]
            delta = -value * step  # avanzar hacia delante mueve la imagen hacia atrás
            model.pan_by(delta if axis == 0 else 0.0, delta if axis == 1 else 0.0)

        if not self._pan_enabled:  # la barra movió su indicador al arrastrarla: se devuelve a donde está la vista
            last = self._chrome.get(f"bar{axis}")
            if last is not None:
                self._bars[axis].set(*last)
            return
        self._interact(action, needs="pan")

    # --- repintado
    def _render(self) -> None:
        self._resize_job = None
        self._cancel_frame_job()  # este repintado ya refleja el último estado
        if self._destroyed:
            return
        if self._model is None:
            self._draw_placeholder()
            self._sync_chrome()
            return
        started = perf_counter()
        self._model.set_viewport_size(*self._viewport_size())
        view = self._renderer.render(self._model)
        rendered = perf_counter()
        if view is None or view is not self._shown:
            self._shown = view
            self._canvas.delete("all")
            self._photo = None
            if view is not None:
                self._photo = ImageTk.PhotoImage(view.image, master=self._canvas)
                self._canvas.create_image(view.x, view.y, anchor="nw", image=self._photo)
                self._record_timing(started, rendered, perf_counter(), view)
        self._sync_chrome()

    def _record_timing(self, started: float, rendered: float, finished: float, view: RenderedView) -> None:
        source = self._renderer.source
        timing = RenderTiming(
            render_ms=(rendered - started) * 1000.0,
            photo_ms=(finished - rendered) * 1000.0,
            total_ms=(finished - started) * 1000.0,
            zoom=self._model.zoom if self._model else 0.0,
            source_size=source.size if source is not None else (0, 0),
            drawn_size=view.image.size,
        )
        self._timings.append(timing)
        level = logging.INFO if timing.total_ms > self._SLOW_RENDER_MS else logging.DEBUG
        logger.log(
            level,
            "render %.1f ms (renderer %.1f + PhotoImage %.1f) zoom=%.4g imagen=%s dibujado=%s",
            timing.total_ms, timing.render_ms, timing.photo_ms, timing.zoom,
            timing.source_size, timing.drawn_size,
        )

    def _sync_chrome(self) -> None:
        """Lleva a los controles (barras, porcentaje, botones) lo que dice el modelo."""
        model = self._model
        fractions = model.scroll_fractions if model is not None else (None, None)
        for axis, bar in enumerate(self._bars):
            fraction = fractions[axis]
            if fraction is None:
                self._show_bar(axis, False)
                continue
            self._show_bar(axis, True)
            if self._chrome.get(f"bar{axis}") != fraction:
                bar.set(*fraction)
                self._chrome[f"bar{axis}"] = fraction
        text = "— %" if model is None else format_zoom_percent(model.zoom, self._pixel_ratio())
        self._set_chrome("label", text, lambda: self._zoom_label.configure(text=text))
        enabled = {
            self._zoom_in_button: model is not None and self._zoom_enabled and model.zoom < model.max_zoom * (1 - 1e-9),
            self._zoom_out_button: model is not None and self._zoom_enabled and model.zoom > model.min_zoom * (1 + 1e-9),
            self._fit_button: model is not None and self._zoom_enabled,
            self._actual_button: model is not None and self._zoom_enabled,
        }
        for widget, on in enabled.items():
            state = "normal" if on else "disabled"
            self._set_chrome(id(widget), state, lambda w=widget, s=state: w.configure(state=s))

    def _show_bar(self, axis: int, visible: bool) -> None:
        if self._bar_visible[axis] == visible:
            return
        self._bar_visible[axis] = visible
        bar = self._bars[axis]
        if visible:
            bar.pack(fill="both", expand=True)
        else:
            bar.pack_forget()
            self._chrome.pop(f"bar{axis}", None)

    def _set_chrome(self, key: object, value: object, apply: Callable[[], None]) -> None:
        if self._chrome.get(key) != value:
            self._chrome[key] = value
            apply()

    def _draw_placeholder(self) -> None:
        self._canvas.delete("all")
        width, height = self._viewport_size()
        self._canvas.create_text(
            width / 2,
            height / 2,
            text=_PLACEHOLDER_TEXT,
            fill=_color_for_mode(_PLACEHOLDER_COLOR),
            font=self._placeholder_font,
            justify="center",
        )
