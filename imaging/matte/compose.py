"""Composición de imágenes RGBA a partir de una máscara."""
from __future__ import annotations

import numpy as np
from PIL import Image

from imaging.matte.types import Matte


def compose_rgba(image: Image.Image, matte: Matte) -> Image.Image:
    """Compone RGBA en un objeto nuevo, sin modificar la entrada."""
    if image.size != matte.size:
        raise ValueError(
            f"El tamaño de la máscara {matte.size} "
            f"no coincide con la imagen {image.size}."
        )

    original_rgba = image.convert("RGBA")
    rgb = original_rgba.convert("RGB")

    original_alpha = np.asarray(
        original_rgba.getchannel("A"),
        dtype=np.uint16,
    )
    matte_alpha = matte.alpha.astype(np.uint16)

    combined_alpha = (
        original_alpha * matte_alpha + 127
    ) // 255

    result = rgb.copy()
    result.putalpha(
        Image.fromarray(combined_alpha.astype(np.uint8), mode="L")
    )
    return result