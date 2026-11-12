"""tests/test_file_service.py

Responsabilidad:
    - Pruebas de DocumentState y FileService: cambios pendientes por
      comparación de operaciones, sugerencia de destino/formato, apertura
      y escritura sin modificar el documento ni la imagen de trabajo.

No conoce:
    - Controladores ni GUI (no requiere display).
"""
from pathlib import Path

import pytest
from PIL import Image

from app.application import build_image_loader, build_processing_service
from app.services.document_state import DocumentState
from app.services.file_service import FileService
from config.settings import Settings
from core.exceptions import ImageLoadError, ImageSaveError, UnsupportedFormatError
from core.models import AppliedOperation
from tools.image_loader import has_transparency

A = AppliedOperation("sharpen", "Nitidez")
B = AppliedOperation("comic_effect", "Semitono")
C = AppliedOperation("remove_background", "Fondo")


# ---------------- DocumentState ----------------

def test_fresh_document_is_clean_and_untitled():
    doc = DocumentState("foto.png", Path("/x/foto.png"))
    assert doc.is_untitled and not doc.has_unsaved_changes(())
    assert doc.title_name == "foto.png"


def test_operations_make_it_dirty_and_saving_makes_it_clean_again():
    doc = DocumentState("foto.png", Path("/x/foto.png"))
    assert doc.has_unsaved_changes((A,))
    doc.mark_saved(Path("/y/salida.jpg"), "JPEG", (A,))
    assert not doc.has_unsaved_changes((A,))
    assert not doc.is_untitled and doc.title_name == "salida.jpg" and doc.save_format == "JPEG"
    assert doc.has_unsaved_changes((A, B))


def test_dirty_compares_the_operations_not_just_their_count():
    doc = DocumentState("f.png", Path("/x/f.png"), saved_operations=(A, B))
    assert doc.has_unsaved_changes((A,))          # menos operaciones
    assert doc.has_unsaved_changes((A, C))        # misma cantidad, distinto contenido
    assert not doc.has_unsaved_changes((A, B))    # idéntico


# ---------------- FileService ----------------

@pytest.fixture
def stack(tmp_path):
    settings = Settings(
        output_dir=tmp_path / "out",
        allowed_extensions=frozenset({".png", ".jpg", ".jpeg", ".webp"}),
    )
    loader = build_image_loader(settings)
    processing = build_processing_service(settings, loader)
    service = FileService(loader, processing)
    src = tmp_path / "src"
    src.mkdir()
    return service, processing, src


def _png(path: Path, transparent=False, size=(40, 20)):
    if transparent:
        img = Image.new("RGBA", size, (255, 0, 0, 0))
        for x in range(size[0] // 2, size[0]):
            for y in range(size[1]):
                img.putpixel((x, y), (0, 0, 255, 255))
    else:
        img = Image.new("RGB", size, "teal")
    img.save(path)
    return path


def test_open_returns_snapshot_and_a_clean_untitled_document(stack):
    service, _, src = stack
    path = _png(src / "foto.png")
    result = service.open(path)
    assert result.snapshot.size == (40, 20)
    doc = result.document
    assert doc.origin_path == path and doc.display_name == "foto.png"
    assert doc.is_untitled and not doc.has_unsaved_changes(result.snapshot.operations)


def test_failed_open_keeps_the_current_image(stack):
    service, processing, src = stack
    service.open(_png(src / "a.png", size=(40, 20)))
    bad = src / "rota.png"
    bad.write_bytes(b"no es una imagen")
    with pytest.raises(ImageLoadError):
        service.open(bad)
    assert processing.snapshot().size == (40, 20)


def test_suggestion_for_a_png_origin_is_png_next_to_the_original(stack):
    service, processing, src = stack
    result = service.open(_png(src / "foto.png"))
    s = service.suggest_save_target(result.document, processing.snapshot())
    assert (s.directory, s.filename, s.format) == (src, "foto_editada.png", "PNG")


@pytest.mark.parametrize("name", ["foto.jpg", "foto.jpeg"])
def test_suggestion_for_an_opaque_jpg_origin_is_jpg(stack, name):
    service, processing, src = stack
    path = src / name
    Image.new("RGB", (40, 20), "teal").save(path, "JPEG")
    result = service.open(path)
    s = service.suggest_save_target(result.document, processing.snapshot())
    assert (s.format, s.filename) == ("JPEG", "foto_editada.jpg")


def test_suggestion_is_png_when_the_image_has_real_transparency_even_for_jpg_origin(stack):
    service, processing, src = stack
    # Un documento con transparencia real (sin depender de rembg) cuyo último guardado fue JPG:
    result = service.open(_png(src / "t.png", transparent=True))
    result.document.save_format = "JPEG"
    s = service.suggest_save_target(result.document, processing.snapshot())
    assert s.format == "PNG" and s.filename.endswith(".png")


def test_suggestion_for_other_origin_formats_is_png(stack):
    service, processing, src = stack
    path = src / "foto.webp"
    Image.new("RGB", (40, 20), "teal").save(path, "WEBP")
    result = service.open(path)
    assert service.suggest_save_target(result.document, processing.snapshot()).format == "PNG"


def test_suggested_name_never_collides_with_existing_files(stack):
    service, processing, src = stack
    result = service.open(_png(src / "foto.png"))
    (src / "foto_editada.png").write_bytes(b"")
    s = service.suggest_save_target(result.document, processing.snapshot())
    assert s.filename == "foto_editada_2.png"


def test_after_saving_the_suggestion_reuses_the_destination(stack, tmp_path):
    service, processing, src = stack
    result = service.open(_png(src / "foto.png"))
    result.document.mark_saved(tmp_path / "salidas" / "final.png", "PNG", ())
    s = service.suggest_save_target(result.document, processing.snapshot())
    assert (s.directory, s.filename) == (tmp_path / "salidas", "final.png")


def test_write_png_keeps_alpha_and_does_not_touch_document_or_original(stack, tmp_path):
    service, processing, src = stack
    path = _png(src / "t.png", transparent=True)
    original_bytes = path.read_bytes()
    result = service.open(path)
    out = service.write(tmp_path / "salida.png")
    with Image.open(out.path) as saved:
        assert saved.mode == "RGBA" and saved.getchannel("A").getextrema() == (0, 255)
    assert out.format == "PNG" and out.operations == ()
    assert result.document.is_untitled  # write NO modifica el documento
    assert path.read_bytes() == original_bytes  # el original no se tocó


def test_write_jpg_with_transparency_needs_flatten_and_leaves_work_image_intact(stack, tmp_path):
    service, processing, src = stack
    service.open(_png(src / "t.png", transparent=True))
    snapshot = processing.snapshot()
    assert service.needs_flatten(snapshot, "JPEG") and not service.needs_flatten(snapshot, "PNG")
    with pytest.raises(ImageSaveError):
        service.write(tmp_path / "x.jpg")
    assert not (tmp_path / "x.jpg").exists()
    out = service.write(tmp_path / "x.jpg", flatten=True)
    with Image.open(out.path) as saved:
        assert saved.format == "JPEG" and min(saved.getpixel((2, 10))) >= 250  # blanco
    assert has_transparency(processing.snapshot().image)  # la imagen de trabajo sigue transparente


def test_needs_flatten_is_false_for_opaque_images(stack):
    service, processing, src = stack
    service.open(_png(src / "o.png"))
    assert not service.needs_flatten(processing.snapshot(), "JPEG")


def test_write_rejects_an_extension_that_does_not_match_a_supported_format(stack, tmp_path):
    service, _, src = stack
    service.open(_png(src / "o.png"))
    with pytest.raises(UnsupportedFormatError):
        service.write(tmp_path / "x.bmp")
    assert list(tmp_path.glob("x.*")) == []
