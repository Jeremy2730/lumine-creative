"""Contratos independientes de los modelos concretos."""
from __future__ import annotations

from typing import Protocol

from PIL import Image

from imaging.matte.types import Matte


class MatteBackend(Protocol):
    """Transforma una imagen en una máscara, sin componer el resultado."""

    def generate(self, image: Image.Image) -> Matte:
        """Devuelve una máscara del mismo tamaño que la imagen."""
        ...