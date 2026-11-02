from pathlib import Path

import pytest
from PIL import Image

from core.exceptions import ImageLoadError, UnsupportedFormatError
from tools.image_loader import ImageLoader

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


@pytest.fixture
def loader():
    return ImageLoader(EXTS)


@pytest.mark.parametrize("name", ["a.jpg", "a.JPEG", "a.png", "a.webp", "a.bmp", "a.tiff"])
def test_supported_extensions(loader, name):
    assert loader.is_supported(Path(name))


@pytest.mark.parametrize("name", ["a.gif", "a.txt", "a"])
def test_unsupported_extensions(loader, name):
    assert not loader.is_supported(Path(name))


def test_load_converts_to_rgba(loader, tmp_path):
    path = tmp_path / "x.jpg"
    Image.new("RGB", (10, 10), "red").save(path)
    assert loader.load(path).mode == "RGBA"


def test_load_rejects_bad_extension_and_corrupt_file(loader, tmp_path):
    with pytest.raises(UnsupportedFormatError):
        loader.load(tmp_path / "x.gif")
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"no soy una imagen")
    with pytest.raises(ImageLoadError):
        loader.load(bad)


def test_list_images_is_sorted_and_filtered(loader, tmp_path):
    for name in ["b.png", "A.jpg", "notes.txt"]:
        (tmp_path / name).write_bytes(b"")
    assert [p.name for p in loader.list_images(tmp_path)] == ["A.jpg", "b.png"]


def test_unique_output_path_never_overwrites(loader, tmp_path):
    first = loader.unique_output_path(tmp_path, "foto")
    assert first.name == "foto_editada.png"
    first.write_bytes(b"")
    assert loader.unique_output_path(tmp_path, "foto").name == "foto_editada_2.png"
