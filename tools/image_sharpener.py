"""tools/image_sharpener.py

Responsabilidad:
    - Aplicar nitidez (UnsharpMask) con los mismos valores del script
      original (radius=2, percent=150, threshold=3).

No conoce:
    - GUI; es una operación pura, sin estado.
"""
from __future__ import annotations

from PIL import Image, ImageFilter

from core.operation import ImageOperation


class ImageSharpener(ImageOperation):
    """UnsharpMask. Los valores por defecto son los del script original."""

    name = "sharpen"

    def __init__(self, radius: float = 2, percent: int = 150, threshold: int = 3) -> None:
        self.radius = radius
        self.percent = percent
        self.threshold = threshold

    @property
    def label(self) -> str:
        return "Nitidez"

    def apply(self, image: Image.Image) -> Image.Image:
        return image.filter(
            ImageFilter.UnsharpMask(
                radius=self.radius, percent=self.percent, threshold=self.threshold
            )
        )
