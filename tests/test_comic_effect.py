"""ComicEffect no usa rembg: se prueba directamente, sin sustitutos."""
import numpy as np
from PIL import Image

from tools.comic_effect import ComicEffect


def _image_with_black_and_gray() -> Image.Image:
    img = Image.new("RGBA", (20, 10), (10, 10, 10, 255))  # negro puro
    for x in range(10, 20):
        for y in range(10):
            img.putpixel((x, y), (120, 120, 120, 255))  # gris, no debe volverse transparente
    return img


def test_makes_pure_black_transparent_but_keeps_gray():
    out = ComicEffect().apply(_image_with_black_and_gray())
    arr = np.array(out)
    assert arr[5, 5, 3] == 0  # zona negra -> transparente
    assert arr[5, 15, 3] == 255  # zona gris -> se conserva


def test_applies_pattern_blend_on_visible_pixels():
    src = Image.new("RGBA", (16, 16), (200, 50, 50, 255))
    out = ComicEffect().apply(src)
    # El área visible cambia de color por la mezcla con la trama, pero no desaparece.
    assert out.getpixel((8, 8))[:3] != src.getpixel((8, 8))[:3]
    assert out.getpixel((8, 8))[3] == 255


def test_accepts_non_rgba_input():
    src = Image.new("RGB", (10, 10), (200, 200, 200))
    out = ComicEffect().apply(src)
    assert out.mode == "RGBA" and out.size == src.size


def test_default_label_and_params():
    op = ComicEffect()
    assert op.label == "Semitono"
    assert (op.black_threshold, op.pattern_contrast, op.blend_alpha) == (22, 3.0, 0.18)


def test_respects_custom_threshold():
    src = _image_with_black_and_gray()
    # Con un umbral muy bajo, ni siquiera el negro puro (brillo ~10) se vuelve transparente.
    out = ComicEffect(black_threshold=1).apply(src)
    assert np.array(out)[5, 5, 3] == 255
