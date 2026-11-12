"""gui/viewport.py

Responsabilidad:
    - Modelo geométrico de cómo se coloca una imagen dentro de un área
      visible (viewport): factor de zoom, tamaño renderizado, posición,
      centrado, límites del desplazamiento y posición válida tras cada
      cambio de zoom, de paneo o de tamaño.
    - Aritmética para zoom enfocado en un punto (el cursor) y para paneo
      por desplazamiento, expresada en coordenadas de viewport, de modo que
      un futuro visor solo traduzca eventos del ratón a llamadas de este
      modelo.
    - Validar todas las dimensiones y números que entran (sin negativos,
      sin ceros donde no son válidos, sin valores no finitos).

No conoce:
    - tkinter, customtkinter, Pillow ni numpy: no importa ninguna librería
      gráfica ni de imágenes, y no recibe ni guarda píxeles, solo tamaños.
    - Eventos, widgets, controladores ni el motor de procesamiento: ni lee
      ni modifica la imagen de trabajo.

Notas (decisiones geométricas):
    - Coordenadas: el viewport tiene su origen (0, 0) en su esquina
      superior izquierda, en píxeles de pantalla. ``position`` es donde
      cae la esquina superior izquierda de la imagen ya escalada, y puede
      ser negativa. ``zoom`` es píxeles de pantalla por píxel de imagen
      (1.0 = 100 %), igual en ambos ejes, por lo que la proporción original
      se conserva siempre: ``rendered_size = image_size · zoom``.
    - Cada eje se trata por separado. Si la imagen escalada cabe en el
      viewport en ese eje, queda CENTRADA y no admite desplazamiento (los
      límites mínimo y máximo coinciden). Si no cabe, la posición queda
      limitada por sus bordes, ``[viewport − renderizado, 0]``: un borde de
      la imagen nunca entra en el viewport dejando hueco, y por tanto la
      imagen jamás puede perderse de vista.
    - Tolerancia: "cabe" admite una holgura de 1e-9 px. Sin ella, en el
      modo ajustar, el redondeo de coma flotante haría que ``zoom · tamaño``
      superara el viewport por una millonésima y el eje pareciera
      desplazable (parpadeo de las futuras barras de desplazamiento).
    - Modo ajustar (``fit_mode``): el zoom es el que hace caber la imagen
      entera (``min(vw/iw, vh/ih)``, la misma fórmula que usa hoy
      ``ImagePanel._render``) y se recalcula solo al cambiar el viewport o
      la imagen. Cualquier cambio explícito de zoom lo desactiva; ``fit()``
      lo reactiva. El paneo no lo altera.
    - Límites de zoom: ``min_zoom``/``max_zoom`` son parámetros (valores
      provisionales 5 %–3200 %, pendientes de aprobación). El mínimo
      efectivo baja si hace falta para que el ajuste siempre sea
      alcanzable (una imagen enorme en un viewport pequeño), y el ajuste se
      limita por arriba al máximo (una imagen diminuta no se amplía más de
      ``max_zoom``; hoy ``ImagePanel`` no tiene tope).
    - Cambio de tamaño del viewport: en modo ajustar se reajusta; en zoom
      manual se conserva el punto de la imagen que estaba en el centro del
      viewport. Cambiar el viewport nunca altera ``image_size``.
    - Barras de desplazamiento: ``scroll_fractions`` y ``scroll_to_fraction``
      traducen la posición a/desde las fracciones que usan las barras; las
      barras no guardan geometría propia, la consultan aquí cada vez.
    - Viewport 0×0 es válido (ventana minimizada o aún sin dibujar):
      no hay nada visible, pero no falla; al recibir un tamaño real se
      recalcula. La imagen siempre exige tamaño > 0.
    - Errores: un tipo que no es número o no es un par → ``TypeError``;
      un número negativo, cero donde no vale, NaN o infinito →
      ``ValueError``. Una llamada que falla no cambia el estado.
    - ``rendered_size`` es flotante; ``rendered_size_px`` da el tamaño
      entero (≥ 1) que necesitará quien dibuje (difiere como mucho 1 px del
      truncado ``int()`` que usa hoy ``ImagePanel``).
    - ``visible_area()`` es la ÚNICA fuente de qué parte de la imagen se ve
      y en qué rectángulo entero del viewport se pinta; quien dibuje (ver
      ``gui/viewport_renderer.py``) solo convierte esos rectángulos en
      píxeles y no calcula geometría. Un eje que se ve entero se pinta
      completo con tamaño ``round(renderizado)``; un eje recortado se pinta
      de borde a borde del viewport con el trozo de imagen que corresponde.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from numbers import Real

__all__ = ["ViewportModel", "VisibleArea", "DEFAULT_MIN_ZOOM", "DEFAULT_MAX_ZOOM"]

DEFAULT_MIN_ZOOM = 0.05  # 5 %  (provisional)
DEFAULT_MAX_ZOOM = 32.0  # 3200 %  (provisional)

_FIT_TOLERANCE = 1e-9  # px de holgura al decidir si la imagen "cabe" en un eje
_ZOOM_FLOOR = 1e-12  # suelo absoluto: evita divisiones por cero en casos absurdos


# ---------------------------------------------------------------- validación

def _number(value: object, name: str) -> float:
    """Número real finito. ``TypeError`` si no es número; ``ValueError`` si no es finito."""
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} debe ser un número, no {type(value).__name__}.")
    try:
        number = float(value)
    except OverflowError:
        raise ValueError(f"{name} es demasiado grande para representarse ({value!r}).") from None
    if not math.isfinite(number):
        raise ValueError(f"{name} debe ser un número finito (recibido {value!r}).")
    return number


def _positive(value: object, name: str) -> float:
    number = _number(value, name)
    if number <= 0:
        raise ValueError(f"{name} debe ser mayor que 0 (recibido {value!r}).")
    return number


def _pair(value: object, name: str) -> tuple[object, object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
        raise TypeError(f"{name} debe ser un par (x, y), recibido {value!r}.")
    return value[0], value[1]


def _size(value: object, name: str, *, allow_zero: bool) -> tuple[float, float]:
    """Par (ancho, alto): finito y > 0 (o >= 0 si ``allow_zero``)."""
    first, second = _pair(value, name)
    out = []
    for label, item in (("ancho", first), ("alto", second)):
        number = _number(item, f"{name} ({label})")
        if number < 0 or (number == 0 and not allow_zero):
            limit = "0 o más" if allow_zero else "mayor que 0"
            raise ValueError(f"{name} ({label}) debe ser {limit} (recibido {item!r}).")
        out.append(number)
    return out[0], out[1]


def _point(value: object, name: str) -> tuple[float, float]:
    """Par de coordenadas finitas de cualquier signo."""
    first, second = _pair(value, name)
    return _number(first, f"{name} (x)"), _number(second, f"{name} (y)")


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


# -------------------------------------------------------------------- modelo

@dataclass(frozen=True)
class VisibleArea:
    """Qué parte de la imagen se ve y en qué rectángulo del viewport se pinta."""

    destination: tuple[int, int, int, int]  # (x0, y0, x1, y1) enteros, coordenadas del viewport
    source: tuple[float, float, float, float]  # (x0, y0, x1, y1) en píxeles de la imagen original


class ViewportModel:
    """Geometría de una imagen dentro de un viewport. Solo números, ningún píxel."""

    def __init__(
        self,
        image_size: Sequence[float],
        viewport_size: Sequence[float] = (0, 0),
        *,
        min_zoom: float = DEFAULT_MIN_ZOOM,
        max_zoom: float = DEFAULT_MAX_ZOOM,
    ) -> None:
        low = _positive(min_zoom, "min_zoom")
        high = _positive(max_zoom, "max_zoom")
        if low > high:
            raise ValueError(f"min_zoom ({low}) no puede ser mayor que max_zoom ({high}).")
        image = _size(image_size, "image_size", allow_zero=False)
        viewport = _size(viewport_size, "viewport_size", allow_zero=True)
        self._min_limit = low
        self._max_zoom = high
        self._image = image
        self._viewport = viewport
        self._fit_mode = True
        self._zoom = 1.0
        self._x = 0.0
        self._y = 0.0
        self._revalidate()

    def __repr__(self) -> str:
        return (
            f"ViewportModel(image={self._image}, viewport={self._viewport}, "
            f"zoom={self._zoom:.6g}, position=({self._x:.6g}, {self._y:.6g}), fit={self._fit_mode})"
        )

    # ------------------------------------------------------------- consulta
    @property
    def image_size(self) -> tuple[float, float]:
        """Tamaño original de la imagen en píxeles (nunca cambia salvo ``set_image_size``)."""
        return self._image

    @property
    def viewport_size(self) -> tuple[float, float]:
        return self._viewport

    @property
    def zoom(self) -> float:
        return self._zoom

    @property
    def fit_mode(self) -> bool:
        return self._fit_mode

    @property
    def max_zoom(self) -> float:
        return self._max_zoom

    @property
    def min_zoom(self) -> float:
        """Mínimo efectivo: baja del mínimo configurado si hace falta para poder ajustar."""
        return max(_ZOOM_FLOOR, min(self._min_limit, self._raw_fit_zoom))

    @property
    def fit_zoom(self) -> float:
        """Zoom que hace caber la imagen entera, dentro de los límites de zoom."""
        return _clamp(self._raw_fit_zoom, self.min_zoom, self._max_zoom)

    @property
    def rendered_size(self) -> tuple[float, float]:
        return self._image[0] * self._zoom, self._image[1] * self._zoom

    @property
    def rendered_size_px(self) -> tuple[int, int]:
        """Tamaño entero (≥ 1) para quien dibuje; difiere < 1 px de ``rendered_size``."""
        width, height = self.rendered_size
        return max(1, round(width)), max(1, round(height))

    @property
    def position(self) -> tuple[float, float]:
        """Esquina superior izquierda de la imagen escalada, en coordenadas de viewport."""
        return self._x, self._y

    @property
    def fits(self) -> tuple[bool, bool]:
        """Por eje: True si la imagen escalada cabe (queda centrada y sin desplazamiento)."""
        rw, rh = self.rendered_size
        return self._axis_fits(self._viewport[0], rw), self._axis_fits(self._viewport[1], rh)

    @property
    def position_bounds(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """((min_x, max_x), (min_y, max_y)). Si el eje cabe, mínimo y máximo coinciden (centrado)."""
        rw, rh = self.rendered_size
        return (
            self._axis_bounds(self._viewport[0], rw),
            self._axis_bounds(self._viewport[1], rh),
        )

    @property
    def scroll_fractions(self) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
        """Por eje, la parte visible de la imagen escalada como ``(inicio, fin)`` en ``[0, 1]``
        (el protocolo de las barras de desplazamiento), o ``None`` si ese eje cabe entero
        (no hay nada que desplazar). Se deriva siempre de la posición actual: no guarda estado."""
        out: list[tuple[float, float] | None] = []
        for axis, (low, high) in enumerate(self.position_bounds):
            viewport_len, rendered_len = self._viewport[axis], self.rendered_size[axis]
            if viewport_len <= 0 or low == high:
                out.append(None)
                continue
            start = _clamp(-self.position[axis] / rendered_len, 0.0, 1.0)
            end = _clamp((viewport_len - self.position[axis]) / rendered_len, 0.0, 1.0)
            out.append((start, end))
        return out[0], out[1]

    def visible_area(self) -> VisibleArea | None:
        """Zona visible de la imagen y su rectángulo de destino; ``None`` si no hay nada que pintar
        (viewport sin área)."""
        vw, vh = self._viewport
        if vw <= 0 or vh <= 0:
            return None
        rw, rh = self.rendered_size
        x0, x1, sx0, sx1 = self._axis_visible(self._x, rw, vw, self._image[0])
        y0, y1, sy0, sy1 = self._axis_visible(self._y, rh, vh, self._image[1])
        return VisibleArea(destination=(x0, y0, x1, y1), source=(sx0, sy0, sx1, sy1))

    def viewport_to_image(self, x: float, y: float) -> tuple[float, float]:
        """Punto del viewport → coordenadas de la imagen original (flotantes)."""
        px, py = _number(x, "x"), _number(y, "y")
        return (px - self._x) / self._zoom, (py - self._y) / self._zoom

    def image_to_viewport(self, x: float, y: float) -> tuple[float, float]:
        """Punto de la imagen original → coordenadas del viewport."""
        ix, iy = _number(x, "x"), _number(y, "y")
        return self._x + ix * self._zoom, self._y + iy * self._zoom

    # ------------------------------------------------------------- cambios
    def set_viewport_size(self, width: float, height: float) -> None:
        """El viewport cambió de tamaño. Reajusta (modo ajustar) o conserva el centro (zoom manual)."""
        new = _size((width, height), "viewport_size", allow_zero=True)
        if new == self._viewport:
            return
        centre = self.viewport_to_image(self._viewport[0] / 2, self._viewport[1] / 2)
        self._viewport = new
        self._revalidate()
        if not self._fit_mode:
            self._place(centre, (new[0] / 2, new[1] / 2))

    def set_image_size(self, width: float, height: float, *, keep_view: bool = False) -> None:
        """La imagen mostrada cambió de tamaño en píxeles.

        Por defecto vuelve al modo ajustar. Con ``keep_view=True`` conserva el
        modo actual: si estaba en zoom manual, mantiene el zoom y el punto
        relativo de la imagen que estaba en el centro del viewport.
        """
        new = _size((width, height), "image_size", allow_zero=False)
        preserve = keep_view and not self._fit_mode
        fraction = None
        if preserve:
            cx, cy = self.viewport_to_image(self._viewport[0] / 2, self._viewport[1] / 2)
            fraction = (cx / self._image[0], cy / self._image[1])
        self._image = new
        if not keep_view:
            self._fit_mode = True
        self._revalidate()
        if preserve and fraction is not None:
            self._place(
                (fraction[0] * new[0], fraction[1] * new[1]),
                (self._viewport[0] / 2, self._viewport[1] / 2),
            )

    def fit(self) -> None:
        """Ajusta la imagen entera al viewport y vuelve al modo ajustar."""
        self._fit_mode = True
        self._revalidate()

    def set_zoom(self, zoom: float, anchor: Sequence[float] | None = None) -> None:
        """Fija el zoom (acotado a los límites). ``anchor`` es un punto del viewport que
        permanece sobre el mismo punto de la imagen (el cursor); por defecto, el centro."""
        target = _positive(zoom, "zoom")
        self._zoom_to(target, self._anchor(anchor))

    def zoom_by(self, factor: float, anchor: Sequence[float] | None = None) -> None:
        """Multiplica el zoom por ``factor`` (> 0), con el mismo criterio de ``anchor``."""
        step = _positive(factor, "factor")
        point = self._anchor(anchor)  # valida antes de tocar nada
        target = self._zoom * step
        if math.isinf(target):
            target = self._max_zoom
        elif target == 0.0:
            target = self.min_zoom
        self._zoom_to(target, point)

    def pan_by(self, dx: float, dy: float) -> None:
        """Desplaza la imagen ``(dx, dy)`` píxeles de pantalla, sin salirse de los límites."""
        mx, my = _number(dx, "dx"), _number(dy, "dy")
        self._x, self._y = self._clamp_position(self._x + mx, self._y + my)

    def pan_to(self, x: float, y: float) -> None:
        """Coloca la esquina superior izquierda de la imagen en ``(x, y)``, acotada a los límites."""
        px, py = _number(x, "x"), _number(y, "y")
        self._x, self._y = self._clamp_position(px, py)

    def scroll_to_fraction(self, axis: int, fraction: float) -> None:
        """Coloca el borde inicial de la parte visible en ``fraction`` (0-1) de la imagen escalada,
        en el eje ``axis`` (0 = horizontal, 1 = vertical), sin tocar el otro. Es el ``moveto`` de
        una barra de desplazamiento; queda acotado a los límites como cualquier paneo."""
        if axis not in (0, 1) or isinstance(axis, bool):
            raise ValueError(f"axis debe ser 0 (horizontal) o 1 (vertical), recibido {axis!r}.")
        target = -_number(fraction, "fraction") * self.rendered_size[axis]
        if axis == 0:
            self.pan_to(target, self._y)
        else:
            self.pan_to(self._x, target)

    # ------------------------------------------------------------ internos
    @property
    def _raw_fit_zoom(self) -> float:
        vw, vh = self._viewport
        if vw <= 0 or vh <= 0:
            return self._min_limit  # no hay nada visible: valor neutro
        return min(vw / self._image[0], vh / self._image[1])

    @staticmethod
    def _axis_fits(viewport_len: float, rendered_len: float) -> bool:
        return rendered_len <= viewport_len + _FIT_TOLERANCE

    @classmethod
    def _axis_bounds(cls, viewport_len: float, rendered_len: float) -> tuple[float, float]:
        if cls._axis_fits(viewport_len, rendered_len):
            centred = (viewport_len - rendered_len) / 2
            return centred, centred
        return viewport_len - rendered_len, 0.0

    def _axis_visible(
        self, position: float, rendered: float, viewport: float, image_len: float
    ) -> tuple[int, int, float, float]:
        """(destino_ini, destino_fin, origen_ini, origen_fin) de un eje, destino entero y dentro del viewport."""
        limit = max(1, math.floor(viewport + _FIT_TOLERANCE))  # último píxel pintable + 1
        if position >= -_FIT_TOLERANCE and position + rendered <= viewport + _FIT_TOLERANCE:
            # el eje se ve entero: se pinta la imagen completa con su tamaño redondeado
            size = min(max(1, round(rendered)), limit)
            start = min(max(0, round(position)), limit - size)
            return start, start + size, 0.0, image_len
        # eje recortado: de borde a borde del viewport con el trozo de imagen que corresponde
        left = max(0.0, position)
        right = min(viewport, position + rendered)
        start = min(max(0, round(left)), limit - 1)
        end = min(max(round(right), start + 1), limit)
        src_start = _clamp((start - position) / self._zoom, 0.0, image_len)
        src_end = _clamp((end - position) / self._zoom, 0.0, image_len)
        return start, end, src_start, src_end

    def _clamp_position(self, x: float, y: float) -> tuple[float, float]:
        (min_x, max_x), (min_y, max_y) = self.position_bounds
        return _clamp(x, min_x, max_x), _clamp(y, min_y, max_y)

    def _revalidate(self) -> None:
        """Recalcula zoom y posición tras un cambio, dejando el estado siempre válido."""
        if self._fit_mode:
            self._zoom = self.fit_zoom
        else:
            self._zoom = _clamp(self._zoom, self.min_zoom, self._max_zoom)
        self._x, self._y = self._clamp_position(self._x, self._y)

    def _place(self, image_point: tuple[float, float], viewport_point: tuple[float, float]) -> None:
        """Coloca ``image_point`` (coords de imagen) sobre ``viewport_point`` y acota."""
        x = viewport_point[0] - image_point[0] * self._zoom
        y = viewport_point[1] - image_point[1] * self._zoom
        self._x, self._y = self._clamp_position(x, y)

    def _anchor(self, anchor: Sequence[float] | None) -> tuple[float, float]:
        if anchor is None:
            return self._viewport[0] / 2, self._viewport[1] / 2
        return _point(anchor, "anchor")

    def _zoom_to(self, target: float, anchor: tuple[float, float]) -> None:
        target = _clamp(target, self.min_zoom, self._max_zoom)
        if math.isclose(target, self._zoom, rel_tol=1e-12, abs_tol=0.0):
            return  # sin cambio real: no sale del modo ajustar ni mueve nada
        image_point = self.viewport_to_image(*anchor)
        self._fit_mode = False
        self._zoom = target
        self._place(image_point, anchor)
