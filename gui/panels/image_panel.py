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

No conoce:
    - El motor, los controladores ni el estado de la aplicación: solo
      recibe la imagen a mostrar vía ``show()``.
    - Cómo se calcula la geometría ni cómo se producen los píxeles.

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
    - ``viewport`` y ``redraw()`` son los puntos de entrada previstos para
      las interacciones futuras (zoom, paneo, modo mano, barras de
      desplazamiento): modificarán el modelo y llamarán a ``redraw()``.
      Este panel no implementa ninguna de ellas.
    - Límite conocido: el texto de ayuda se dibuja con la fuente base de
      CustomTkinter sin su escalado por DPI (solo afecta a ese texto).
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence

import customtkinter as ctk
from PIL import Image, ImageTk

from gui.viewport import ViewportModel
from gui.viewport_renderer import RenderedView, ViewportRenderer

_PLACEHOLDER_TEXT = "Abre una imagen para comenzar\n(menú Archivos ▸ Abrir…  ·  Ctrl+O)"
_PLACEHOLDER_COLOR = ("gray40", "gray60")


def _color_for_mode(color: str | Sequence[str]) -> str:
    """Resuelve un color de CustomTkinter, ``(claro, oscuro)``, para el modo actual."""
    if isinstance(color, str):
        return color
    return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]


class ImagePanel(ctk.CTkFrame):
    """Muestra la imagen según un ``ViewportModel``; nunca modifica la imagen del motor."""

    _MARGIN = 16
    _RESIZE_QUIET_MS = 80

    def __init__(self, master) -> None:
        super().__init__(master, corner_radius=12, height=340)
        self.pack_propagate(False)  # el contenido no debe dictar el tamaño del panel
        self._model: ViewportModel | None = None
        self._renderer = ViewportRenderer()
        self._shown: RenderedView | None = None
        self._photo: ImageTk.PhotoImage | None = None  # referencia: Tk no la retiene
        self._resize_job: str | None = None

        self._canvas = tk.Canvas(
            self, bg=_color_for_mode(self.cget("fg_color")), highlightthickness=0, bd=0
        )
        self._canvas.pack(expand=True, fill="both", padx=self._MARGIN, pady=self._MARGIN)
        self._placeholder_font = ctk.CTkFont()
        self._canvas.bind("<Configure>", self._on_configure)
        self._draw_placeholder()

    # ------------------------------------------------------------ API pública
    @property
    def viewport(self) -> ViewportModel | None:
        """Modelo geométrico de la vista (``None`` mientras no haya imagen)."""
        return self._model

    def show(self, image: Image.Image, *, keep_view: bool = False) -> None:
        """Muestra ``image``. ``keep_view=False`` la ajusta al área; ``True`` conserva el encuadre."""
        self._cancel_pending_render()
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
        """Vuelve a pintar ahora el estado actual del modelo (lo usarán las interacciones futuras)."""
        self._cancel_pending_render()
        self._render()

    def destroy(self) -> None:
        self._cancel_pending_render()
        super().destroy()

    # ---------------------------------------------------------------- internos
    def _viewport_size(self) -> tuple[int, int]:
        return self._canvas.winfo_width(), self._canvas.winfo_height()

    def _cancel_pending_render(self) -> None:
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
            self._resize_job = None

    def _on_configure(self, _event) -> None:
        self._cancel_pending_render()
        self._resize_job = self.after(self._RESIZE_QUIET_MS, self._render)

    def _render(self) -> None:
        self._resize_job = None
        if self._model is None:
            self._draw_placeholder()
            return
        self._model.set_viewport_size(*self._viewport_size())
        view = self._renderer.render(self._model)
        if view is not None and view is self._shown:
            return  # el renderizador devolvió lo mismo: no hay nada que repintar
        self._shown = view
        self._canvas.delete("all")
        self._photo = None
        if view is None:
            return
        self._photo = ImageTk.PhotoImage(view.image, master=self._canvas)
        self._canvas.create_image(view.x, view.y, anchor="nw", image=self._photo)

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
