"""Tipos fundamentales del motor de máscaras."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

AlphaArray = NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class Matte:
    """Máscara de alfa: 0 = fondo, 255 = primer plano."""

    alpha: AlphaArray

    def __post_init__(self) -> None:
        alpha = np.asarray(self.alpha)

        if alpha.ndim != 2:
            raise ValueError("Matte.alpha debe ser una matriz 2D.")

        if alpha.dtype != np.uint8:
            raise ValueError("Matte.alpha debe usar valores uint8.")

        if alpha.shape[0] == 0 or alpha.shape[1] == 0:
            raise ValueError("Matte.alpha no puede estar vacío.")

        # Evita compartir memoria mutable con quien creó la máscara.
        owned = np.array(alpha, dtype=np.uint8, copy=True, order="C")
        owned.setflags(write=False)
        object.__setattr__(self, "alpha", owned)

    @property
    def size(self) -> tuple[int, int]:
        """Dimensiones en el formato Pillow: (ancho, alto)."""
        height, width = self.alpha.shape
        return width, height