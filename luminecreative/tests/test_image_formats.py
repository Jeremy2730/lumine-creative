"""tests/test_image_formats.py

Responsabilidad:
    - Pruebas de ImageLoader para PNG/JPG: apertura (incluida la orientación
      EXIF), guardado por formato real, transparencia, aplanado sobre
      blanco, calidad JPG, DPI, perfil ICC y escritura atómica.

No conoce:
    - Documentos, controladores ni GUI (no requiere display).
"""
from pathlib import Path

import pytest
from PIL import Image, ImageCms

from core.exceptions import ImageLoadError, ImageSaveError, UnsupportedFormatError
from tools.image_loader import (
    ImageLoader,
    flatten_on_white,
    has_transparency,
)


@pytest.fixture
def loader():
    return ImageLoader({".jpg", ".jpeg", ".png"})


def _srgb() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def _transparent_image() -> Image.Image:
    img = Image.new("RGBA", (20, 20), (255, 0, 0, 0))  # rojo totalmente transparente
    for x in range(10, 20):
        for y in range(20):
            img.putpixel((x, y), (0, 0, 255, 255))  # mitad azul opaca
    return img


# ---------------- apertura ----------------

@pytest.mark.parametrize("name,fmt", [("a.png", "PNG"), ("a.jpg", "JPEG"), ("a.jpeg", "JPEG")])
def test_opens_png_jpg_and_jpeg_as_rgba(loader, tmp_path, name, fmt):
    path = tmp_path / name
    Image.new("RGB", (30, 20), "green").save(path, fmt)
    img = loader.load(path)
    assert img.mode == "RGBA" and img.size == (30, 20)


def test_exif_orientation_is_applied_before_converting(loader, tmp_path):
    exif = Image.Exif()
    exif[0x0112] = 6  # 6 = hay que girar 90° para verla bien
    path = tmp_path / "foto.jpg"
    Image.new("RGB", (200, 100), "red").save(path, "JPEG", exif=exif, dpi=(300, 300))
    img = loader.load(path)
    assert img.size == (100, 200)  # ancho y alto intercambiados
    assert img.mode == "RGBA"
    assert img.info.get("dpi") == (300, 300)  # el DPI sobrevive a la corrección
    assert img.getexif().get(0x0112) in (None, 1)  # sin orientación residual


def test_image_without_exif_keeps_its_size(loader, tmp_path):
    path = tmp_path / "plain.png"
    Image.new("RGB", (30, 20)).save(path)
    assert loader.load(path).size == (30, 20)


def test_corrupt_file_raises_controlled_error(loader, tmp_path):
    path = tmp_path / "rota.png"
    path.write_bytes(b"esto no es una imagen")
    with pytest.raises(ImageLoadError):
        loader.load(path)


def test_decompression_bomb_is_mapped_to_controlled_error(loader, tmp_path, monkeypatch):
    path = tmp_path / "grande.png"
    Image.new("RGB", (20, 20)).save(path)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)  # 400 px > 2 × 10 → error de Pillow
    with pytest.raises(ImageLoadError):
        loader.load(path)


# ---------------- formato real = extensión ----------------

@pytest.mark.parametrize(
    "name,expected", [("a.png", "PNG"), ("a.jpg", "JPEG"), ("a.jpeg", "JPEG"), ("A.JPG", "JPEG")]
)
def test_extension_decides_the_real_format(loader, tmp_path, name, expected):
    path = loader.save(Image.new("RGBA", (8, 8), (1, 2, 3, 255)), tmp_path / name)
    with Image.open(path) as saved:
        assert saved.format == expected


def test_jpg_file_is_not_png_data_anymore(loader, tmp_path):
    """Regresión: antes se escribía PNG aunque la ruta terminara en .jpg."""
    path = loader.save(Image.new("RGB", (8, 8)), tmp_path / "x.jpg")
    assert not path.read_bytes().startswith(b"\x89PNG")


@pytest.mark.parametrize("name", ["a.bmp", "a.gif", "a.webp", "a.pdf", "a"])
def test_unsupported_save_extension_is_rejected_and_writes_nothing(loader, tmp_path, name):
    with pytest.raises(UnsupportedFormatError):
        loader.save(Image.new("RGB", (8, 8)), tmp_path / name)
    assert list(tmp_path.iterdir()) == []


# ---------------- transparencia ----------------

def test_png_keeps_the_alpha_channel(loader, tmp_path):
    path = loader.save(_transparent_image(), tmp_path / "t.png")
    with Image.open(path) as saved:
        assert saved.mode == "RGBA"
        assert saved.getchannel("A").getextrema() == (0, 255)


def test_has_transparency_checks_the_alpha_not_just_the_mode():
    assert has_transparency(_transparent_image())
    assert not has_transparency(Image.new("RGBA", (4, 4), (1, 2, 3, 255)))  # RGBA 100 % opaco
    assert not has_transparency(Image.new("RGB", (4, 4)))
    assert has_transparency(Image.new("LA", (4, 4), (10, 0)))
    palette = Image.new("P", (4, 4), 0)
    palette.info["transparency"] = 0
    assert has_transparency(palette)


def test_jpg_with_transparency_requires_explicit_flatten(loader, tmp_path):
    target = tmp_path / "t.jpg"
    with pytest.raises(ImageSaveError):
        loader.save(_transparent_image(), target)
    assert not target.exists()  # no se escribió nada


def test_jpg_flatten_composes_on_white_and_does_not_touch_the_work_image(loader, tmp_path):
    work = _transparent_image()
    before = work.tobytes()
    path = loader.save(work, tmp_path / "t.jpg", flatten_alpha=True)
    with Image.open(path) as saved:
        assert saved.mode == "RGB"
        r, g, b = saved.getpixel((2, 10))  # zona transparente (era rojo residual)
        assert min(r, g, b) >= 250  # blanco, no rojo
        assert saved.getpixel((17, 10))[2] > 200  # zona azul opaca intacta
    assert work.mode == "RGBA" and work.tobytes() == before  # imagen de trabajo intacta


def test_flatten_on_white_is_not_a_plain_rgb_convert():
    img = _transparent_image()
    assert img.convert("RGB").getpixel((2, 10)) == (255, 0, 0)  # convert a secas: rojo residual
    assert flatten_on_white(img).getpixel((2, 10)) == (255, 255, 255)


def test_opaque_rgba_saves_as_jpg_without_asking_for_flatten(loader, tmp_path):
    path = loader.save(Image.new("RGBA", (8, 8), (10, 20, 30, 255)), tmp_path / "o.jpg")
    with Image.open(path) as saved:
        assert saved.format == "JPEG" and saved.mode == "RGB"


# ---------------- calidad, DPI, ICC ----------------

def _luma_q0(path: Path) -> int:
    with Image.open(path) as saved:
        return saved.quantization[0][0]


def test_jpg_quality_is_explicit_95_not_pillows_default_75(tmp_path):
    img = Image.effect_noise((64, 64), 40).convert("RGB")
    q95 = ImageLoader({".jpg"}).save(img, tmp_path / "a.jpg")
    q50 = ImageLoader({".jpg"}, jpeg_quality=50).save(img, tmp_path / "b.jpg")
    assert _luma_q0(q95) == 2  # tabla de cuantización de calidad 95
    assert _luma_q0(q50) > _luma_q0(q95)  # una calidad configurada distinta se respeta


def test_dpi_is_kept_in_jpg_and_png(loader, tmp_path):
    img = Image.new("RGB", (10, 10), "gray")
    img.info["dpi"] = (300, 300)
    jpg = loader.save(img, tmp_path / "d.jpg")
    png = loader.save(img, tmp_path / "d.png")
    with Image.open(jpg) as a, Image.open(png) as b:
        assert a.info["dpi"] == (300, 300)
        assert b.info["dpi"][0] == pytest.approx(300, abs=0.01)  # PNG: deriva mínima


def test_rgb_icc_profile_is_kept_on_save(loader, tmp_path):
    icc = _srgb()
    img = Image.new("RGB", (10, 10), "gray")
    img.info["icc_profile"] = icc
    for name in ("p.png", "p.jpg"):
        path = loader.save(img, tmp_path / name)
        with Image.open(path) as saved:
            assert saved.info.get("icc_profile") == icc


def test_rgb_icc_profile_survives_loading(loader, tmp_path):
    icc = _srgb()
    path = tmp_path / "icc.jpg"
    Image.new("RGB", (10, 10), "gray").save(path, "JPEG", icc_profile=icc)
    assert loader.load(path).info.get("icc_profile") == icc


def test_non_rgb_or_corrupt_icc_profile_is_dropped_on_load(loader, tmp_path):
    lab = ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes()
    for name, profile in (("lab.png", lab), ("basura.png", b"no soy un perfil icc")):
        path = tmp_path / name
        Image.new("RGB", (10, 10), "gray").save(path, "PNG", icc_profile=profile)
        assert "icc_profile" not in loader.load(path).info


# ---------------- escritura atómica ----------------

def _break_pillow_save(monkeypatch):
    def broken(self, fp, *args, **kwargs):
        Path(fp).write_bytes(b"PARCIAL")  # simula un archivo escrito a medias
        raise OSError("disco lleno")

    monkeypatch.setattr(Image.Image, "save", broken)


def test_failed_write_keeps_the_existing_file_intact(loader, tmp_path, monkeypatch):
    target = tmp_path / "doc.png"
    target.write_bytes(b"CONTENIDO ORIGINAL")
    _break_pillow_save(monkeypatch)
    with pytest.raises(ImageSaveError):
        loader.save(Image.new("RGBA", (8, 8)), target)
    assert target.read_bytes() == b"CONTENIDO ORIGINAL"
    assert list(tmp_path.iterdir()) == [target]  # ni temporales sobrantes


def test_failed_write_does_not_create_a_partial_final_file(loader, tmp_path, monkeypatch):
    target = tmp_path / "nuevo.jpg"
    _break_pillow_save(monkeypatch)
    with pytest.raises(ImageSaveError):
        loader.save(Image.new("RGB", (8, 8)), target)
    assert not target.exists() and list(tmp_path.iterdir()) == []


def test_successful_write_replaces_the_target_and_leaves_no_temporaries(loader, tmp_path):
    target = tmp_path / "doc.png"
    target.write_bytes(b"viejo")
    loader.save(Image.new("RGBA", (8, 8), (9, 9, 9, 255)), target)
    with Image.open(target) as saved:
        assert saved.format == "PNG"
    assert list(tmp_path.iterdir()) == [target]


def test_save_creates_missing_folders(loader, tmp_path):
    path = loader.save(Image.new("RGB", (4, 4)), tmp_path / "sub" / "dir" / "a.png")
    assert path.exists()


# ---------------- nombres sugeridos ----------------

def test_unique_output_path_supports_other_extensions_and_keeps_default(loader, tmp_path):
    assert loader.unique_output_path(tmp_path, "foto").name == "foto_editada.png"
    assert loader.unique_output_path(tmp_path, "foto", ".jpg").name == "foto_editada.jpg"
    (tmp_path / "foto_editada.jpg").write_bytes(b"")
    assert loader.unique_output_path(tmp_path, "foto", ".jpg").name == "foto_editada_2.jpg"
