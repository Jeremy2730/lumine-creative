from PIL import Image

from tools.background_remover import BackgroundRemover


def _passthrough(data: bytes) -> bytes:
    """Sustituto de rembg: no quita nada, solo re-codifica a PNG."""
    return data


def test_background_remover_returns_rgba():
    src = Image.new("RGB", (8, 8), "red")
    out = BackgroundRemover(remove_fn=_passthrough).apply(src)
    assert out.mode == "RGBA" and out.size == src.size


def test_background_remover_default_label():
    assert BackgroundRemover().label == "Fondo"
