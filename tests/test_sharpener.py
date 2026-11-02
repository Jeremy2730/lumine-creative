from PIL import Image, ImageChops

from tools.image_sharpener import ImageSharpener


def _differs(a: Image.Image, b: Image.Image) -> bool:
    # getbbox() sobre RGBA mira solo el alfa; comparamos los canales de color.
    return ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox() is not None


def _edge_image() -> Image.Image:
    img = Image.new("RGBA", (32, 32), (100, 100, 100, 255))
    img.paste((150, 150, 150, 255), (16, 0, 32, 32))
    return img


def test_defaults_match_original_script():
    s = ImageSharpener()
    assert (s.radius, s.percent, s.threshold) == (2, 150, 3)


def test_sharpen_changes_edges_and_keeps_size_and_mode():
    src = _edge_image()
    out = ImageSharpener().apply(src)
    assert out.size == src.size and out.mode == "RGBA"
    assert _differs(src, out)


def test_sharpen_leaves_flat_image_untouched():
    flat = Image.new("RGBA", (16, 16), (120, 120, 120, 255))
    assert not _differs(flat, ImageSharpener().apply(flat))


def test_input_is_not_mutated():
    src = _edge_image()
    before = src.copy()
    ImageSharpener().apply(src)
    assert not _differs(src, before)
