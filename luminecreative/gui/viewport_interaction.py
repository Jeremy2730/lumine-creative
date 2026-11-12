"""gui/viewport_interaction.py

Responsabilidad:
    - Funciones puras que traducen datos de entrada del visor (rueda del
      ratón, órdenes de las barras de desplazamiento, escala de pantalla) a
      números que entiende ``ViewportModel``: factor de zoom por muesca de
      rueda, órdenes ``moveto``/``scroll`` de una barra, zoom del "100 %" y
      texto del porcentaje.

No conoce:
    - tkinter, customtkinter, Pillow, widgets ni eventos reales (recibe
      números ya extraídos del evento), ni geometría: no calcula posiciones
      ni límites; eso es de ``ViewportModel``.

Notas (escala de pantalla, "100 %"):
    - El viewport se mide en píxeles del canvas de Tk, y ``zoom`` es píxeles
      de canvas por píxel de imagen. CustomTkinter declara el proceso
      "DPI-aware" en Windows, así que los píxeles del canvas son píxeles
      FÍSICOS aunque la interfaz esté al 125 %/150 % (esa escala solo agranda
      los widgets de CustomTkinter, no las coordenadas del canvas). En ese
      caso 100 % = zoom 1,0 = un píxel de imagen por píxel físico, que es lo
      que se espera de un visor de imágenes, y se copian los píxeles sin
      remuestrear.
    - Si el proceso NO fuera DPI-aware, Windows estira la ventana y el canvas
      mide píxeles lógicos: un píxel de canvas son ``escala`` píxeles
      físicos. ``physical_per_canvas_pixel`` lo detecta (solo Windows) y el
      100 % pasa a ser ``1 / escala`` para seguir siendo 1:1 físico. Ante
      cualquier duda o error devuelve 1,0.
    - Pendiente de comprobar en un Windows real con varias escalas: este
      módulo se probó con valores simulados.
"""
from __future__ import annotations

import sys
from collections.abc import Sequence

__all__ = [
    "WHEEL_NOTCH",
    "ZOOM_STEP_WHEEL",
    "ZOOM_STEP_BUTTON",
    "SCROLL_UNIT_PX",
    "SCROLL_PAGE_FRACTION",
    "wheel_notches",
    "wheel_zoom_factor",
    "parse_scroll_command",
    "physical_per_canvas_pixel",
    "actual_size_zoom",
    "format_zoom_percent",
]

WHEEL_NOTCH = 120  # delta que Windows envía por muesca de rueda
ZOOM_STEP_WHEEL = 1.1  # factor de zoom por muesca de rueda
ZOOM_STEP_BUTTON = 1.25  # factor de zoom de los botones acercar / alejar
SCROLL_UNIT_PX = 40  # píxeles de una "unidad" de desplazamiento (flecha / rueda de la barra)
SCROLL_PAGE_FRACTION = 0.9  # fracción del viewport que avanza una "página"


def wheel_notches(*, delta: float = 0, num: int = 0) -> float:
    """Muescas de rueda de un evento (positivas = acercar).

    Windows: ``delta`` (múltiplos de 120; los ratones de alta resolución dan
    fracciones y producen fracciones de muesca). Linux/X11: ``num`` 4 (arriba)
    y 5 (abajo), sin ``delta``.
    """
    if num == 4:
        return 1.0
    if num == 5:
        return -1.0
    return float(delta) / WHEEL_NOTCH


def wheel_zoom_factor(notches: float, step: float = ZOOM_STEP_WHEEL) -> float:
    """Factor multiplicativo para ``notches`` muescas: acercar y alejar se compensan exactamente."""
    return step**notches


def parse_scroll_command(args: Sequence[object]) -> tuple[str, float] | None:
    """Interpreta una orden de barra de desplazamiento (protocolo de Tk).

    ``("moveto", "0.25")`` → ``("moveto", 0.25)``;
    ``("scroll", "1", "units")`` → ``("units", 1.0)``; ``"pages"`` → ``("pages", n)``.
    Devuelve ``None`` si la orden no se entiende (se ignora).
    """
    try:
        if len(args) == 2 and args[0] == "moveto":
            return "moveto", float(args[1])  # type: ignore[arg-type]
        if len(args) == 3 and args[0] == "scroll" and args[2] in ("units", "pages"):
            return str(args[2]), float(args[1])  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None


def physical_per_canvas_pixel() -> float:
    """Píxeles físicos por cada píxel de canvas (1,0 salvo proceso Windows sin DPI-awareness)."""
    if sys.platform != "win32":
        return 1.0
    try:
        import ctypes

        awareness = ctypes.c_int()
        if ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness)) != 0:  # type: ignore[attr-defined]
            return 1.0
        if awareness.value != 0:  # 0 = sin DPI-awareness; cualquier otro valor: el canvas es físico
            return 1.0
        percent = ctypes.windll.shcore.GetScaleFactorForDevice(0)  # type: ignore[attr-defined]
        return percent / 100.0 if percent and percent > 0 else 1.0
    except Exception:  # noqa: BLE001 - detección opcional: ante cualquier fallo, 1:1
        return 1.0


def actual_size_zoom(physical_per_pixel: float = 1.0) -> float:
    """Zoom (píxeles de canvas por píxel de imagen) que equivale a 1 píxel de imagen por píxel físico."""
    if not physical_per_pixel or physical_per_pixel <= 0:
        return 1.0
    return 1.0 / physical_per_pixel


def format_zoom_percent(zoom: float, physical_per_pixel: float = 1.0) -> str:
    """Texto del indicador (``"100 %"``): relativo a píxeles físicos, para que coincida con el botón 100 %."""
    percent = zoom * physical_per_pixel * 100.0
    if percent < 9.95:  # por debajo, un decimal (y 9,96 → "10 %", no "10.0 %")
        return f"{percent:.1f} %"
    return f"{percent:.0f} %"
