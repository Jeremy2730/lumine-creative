"""tools/comic_effect.py

Responsabilidad:
    - Aplicar el efecto semitono/cómic: volver transparente el negro puro
      y mezclar la imagen a color con una trama en relieve.

No conoce:
    - rembg ni "quitar fondo". Es un efecto puro de Pillow/numpy que se
      puede aplicar a cualquier imagen RGBA, se haya quitado el fondo o no.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from core.operation import ImageOperation


class ComicEffect(ImageOperation):
    """Réplica del efecto de ``fondo.py``: negros transparentes + trama en relieve."""

    name = "comic_effect"

    def __init__(
        self,
        *,
        black_threshold: int = 22,
        pattern_contrast: float = 3.0,
        blend_alpha: float = 0.18,
    ) -> None:
        self.black_threshold = black_threshold
        self.pattern_contrast = pattern_contrast
        self.blend_alpha = blend_alpha

    @property
    def label(self) -> str:
        return "Semitono"

    def apply(self, image: Image.Image) -> Image.Image:
        base = image.convert("RGBA")

        # Volver transparentes los negros puros (no los grises).
        arr = np.array(base)
        brightness = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
        arr[..., 3][brightness < self.black_threshold] = 0
        base = Image.fromarray(arr, "RGBA")

        # Trama en relieve mezclada sobre el color (efecto cómic).
        color = base.copy()
        gray = ImageEnhance.Contrast(base.convert("L")).enhance(self.pattern_contrast)
        pattern = gray.filter(ImageFilter.EMBOSS).filter(ImageFilter.SMOOTH_MORE)

        result = Image.blend(color, pattern.convert("RGBA"), alpha=self.blend_alpha)
        result.putalpha(base.split()[3])
        return result
