"""gui/viewport_renderer.py

Responsabilidad:
    - Producir los PÍXELES que muestra el visor para un estado de
      ``ViewportModel``: recorta y escala solo la parte visible de la
      imagen y devuelve el resultado junto con el punto del viewport donde
      debe pintarse.
    - Evitar trabajo repetido: conserva niveles reducidos de la imagen
      (construidos solo cuando hacen falta y reutilizados) y recuerda el
      último resultado, de modo que cambiar el tamaño de la ventana o
      redibujar sin cambios no vuelve a reducir la imagen original.

No conoce:
    - tkinter ni customtkinter, eventos, controladores, el motor de
      procesamiento ni la ventana.
    - Geometría propia: qué parte se ve y dónde se pinta se lo pregunta
      siempre a ``ViewportModel.visible_area()``; aquí no se calcula zoom,
      posición, centrado ni límites.

Notas:
    - Nunca modifica la imagen que recibe: solo la lee. Todo lo que
      devuelve es una imagen NUEVA; el zoom, el paneo y el redimensionado
      son transformaciones de visualización.
    - Niveles reducidos: con zoom < 1 se dibuja desde un nivel
      ``Image.reduce(2**k)`` elegido para que la escala restante quede en
      (0,5; 1]. Cada nivel se construye una sola vez por imagen (a partir
      del nivel ya construido más cercano, si lo hay) y se descarta al
      cambiar de imagen. Con zoom ≥ 1 se dibuja desde la imagen original,
      recortando primero la zona visible, así el coste no depende del
      tamaño de la imagen.
    - Los niveles y los remuestreos de Pillow componen con el alfa
      premultiplicado: reducir no inventa halos en los bordes
      semitransparentes.
    - Política de remuestreo (aislada en ``_resample_for`` para revisarla
      cuando exista zoom interactivo): LANCZOS al reducir, BICUBIC al
      ampliar (suave, como se veía hasta ahora) y copia exacta de píxeles
      al 100 % sobre coordenadas enteras.
    - Un solo hilo: el renderizado ocurre en el hilo de la interfaz y no
      introduce concurrencia. Las optimizaciones de render más agresivas
      (baja calidad durante la interacción, niveles en segundo plano) se
      dejan para una fase posterior.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from PIL import Image

from gui.viewport import ViewportModel

__all__ = ["RenderedView", "ViewportRenderer"]

_INTEGER_TOLERANCE = 1e-6  # para decidir si un recorte cae en coordenadas enteras


@dataclass(frozen=True)
class RenderedView:
    """Píxeles listos para mostrar y su esquina superior izquierda en el viewport."""

    image: Image.Image
    x: int
    y: int


def _resample_for(zoom: float) -> Image.Resampling:
    return Image.Resampling.LANCZOS if zoom < 1.0 else Image.Resampling.BICUBIC


class ViewportRenderer:
    """Convierte (imagen + ``ViewportModel``) en píxeles. No guarda geometría."""

    def __init__(self) -> None:
        self._source: Image.Image | None = None
        self._levels: dict[int, Image.Image] = {}
        self._last_key: tuple | None = None
        self._last_view: RenderedView | None = None

    @property
    def source(self) -> Image.Image | None:
        return self._source

    @property
    def level_factors(self) -> tuple[int, ...]:
        """Factores de reducción construidos hasta ahora (1 = la imagen original)."""
        return tuple(sorted(self._levels))

    def set_image(self, image: Image.Image) -> None:
        """Establece la imagen a dibujar. La misma imagen no invalida nada; otra, sí."""
        if image is self._source:
            return
        self._source = image
        self._levels = {1: image}
        self._last_key = None
        self._last_view = None

    def render(self, model: ViewportModel) -> RenderedView | None:
        """Píxeles del estado actual del modelo; ``None`` si no hay imagen o nada que pintar."""
        source = self._source
        if source is None:
            return None
        if model.image_size != (float(source.width), float(source.height)):
            raise ValueError(
                f"El modelo describe una imagen de {model.image_size} y el renderizador "
                f"tiene una de {source.size}."
            )
        area = model.visible_area()
        if area is None:
            return None
        key = (area, model.zoom)
        if key == self._last_key and self._last_view is not None:
            return self._last_view  # nada cambió: no se vuelve a renderizar

        x0, y0, x1, y1 = area.destination
        size = (x1 - x0, y1 - y0)
        level = self._level(self._level_factor(model.zoom))
        scale_x, scale_y = level.width / source.width, level.height / source.height
        box = self._clamped_box(
            (
                area.source[0] * scale_x,
                area.source[1] * scale_y,
                area.source[2] * scale_x,
                area.source[3] * scale_y,
            ),
            level.size,
        )
        pixels = self._pixels(level, box, size, model.zoom)
        view = RenderedView(image=pixels, x=x0, y=y0)
        self._last_key, self._last_view = key, view
        return view

    # ------------------------------------------------------------ internos
    def _level_factor(self, zoom: float) -> int:
        """Mayor potencia de 2 con zoom·factor ≤ 1 (1 si zoom ≥ 1), sin bajar de 1 px."""
        if zoom >= 1.0 or self._source is None:
            return 1
        factor = 2 ** int(math.floor(math.log2(1.0 / zoom)))
        smallest = min(self._source.size)
        while factor > 1 and smallest // factor < 1:
            factor //= 2
        return max(1, factor)

    def _level(self, factor: int) -> Image.Image:
        level = self._levels.get(factor)
        if level is not None:
            return level
        base_factor = max(f for f in self._levels if f < factor)  # el 1 siempre existe
        level = self._levels[base_factor].reduce(factor // base_factor)
        self._levels[factor] = level
        return level

    @staticmethod
    def _clamped_box(
        box: tuple[float, float, float, float], size: tuple[int, int]
    ) -> tuple[float, float, float, float]:
        """Acota el recorte a la imagen (por errores de coma flotante) y evita áreas vacías."""
        width, height = size
        x0 = min(max(box[0], 0.0), width - 1e-6)
        y0 = min(max(box[1], 0.0), height - 1e-6)
        x1 = min(max(box[2], x0 + 1e-6), float(width))
        y1 = min(max(box[3], y0 + 1e-6), float(height))
        return x0, y0, x1, y1

    @staticmethod
    def _pixels(
        level: Image.Image,
        box: tuple[float, float, float, float],
        size: tuple[int, int],
        zoom: float,
    ) -> Image.Image:
        rounded = tuple(round(v) for v in box)
        exact = (
            math.isclose(zoom, 1.0, rel_tol=1e-12)
            and all(abs(v - r) <= _INTEGER_TOLERANCE for v, r in zip(box, rounded))
            and (rounded[2] - rounded[0], rounded[3] - rounded[1]) == size
        )
        if exact:  # 100 % sobre coordenadas enteras: copia exacta de píxeles
            return level.crop(rounded)
        return level.resize(size, _resample_for(zoom), box=box)
