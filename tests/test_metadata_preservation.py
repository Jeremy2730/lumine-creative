"""Conservación de tamaño en píxeles, PPI y perfil de color a través de TODAS las herramientas.

Regla: una imagen conserva sus dimensiones y su resolución al entrar y salir de una herramienta,
salvo que la herramienta esté declarada para cambiarlas (Tamaño y resolución). Las pruebas comparan
valores ANTES y DESPUÉS (no se limitan a comprobar que el proceso terminó). Sin Tk ni rembg: Remove
se prueba con un sustituto que, como rembg, devuelve un PNG recién creado SIN metadatos.
"""
import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageCms

from app.services.processing_service import ProcessingService
from app.services.tool_registry import ToolRegistry
from core.design_engine import DesignEngine
from core.exceptions import ProcessingError
from core.image_metadata import PRESERVED_INFO_KEYS, capture_metadata, restore_metadata
from core.image_pipeline import ImagePipeline
from core.operation import ImageOperation
from tools.background_remover import BackgroundRemover
from tools.comic_effect import ComicEffect
from tools.image_loader import ImageLoader
from tools.image_sharpener import ImageSharpener
from tools.size_resolution import SizeResolutionAdjuster

CM = 2.54


def rembg_like(data: bytes) -> bytes:
    """Como rembg: decodifica, vuelve transparente la mitad izquierda y devuelve un PNG NUEVO (sin metadatos)."""
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    arr = np.array(image)
    arr[:, : arr.shape[1] // 2, 3] = 0
    out = io.BytesIO()
    Image.fromarray(arr, "RGBA").save(out, format="PNG")
    return out.getvalue()


def physical_cm(image: Image.Image) -> tuple[float, float]:
    """Tamaño físico derivado: píxeles / PPI (nunca se guarda, así que no puede quedar incoherente)."""
    dpi_x, dpi_y = image.info["dpi"]
    return image.width / dpi_x * CM, image.height / dpi_y * CM


def srgb_profile() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


@pytest.fixture
def service(tmp_path):
    registry = ToolRegistry()
    registry.register("remove_background", lambda: BackgroundRemover(remove_fn=rembg_like))
    registry.register("sharpen", ImageSharpener)
    registry.register("comic_effect", ComicEffect)
    registry.register(
        "size_resolution",
        lambda width_cm, height_cm, dpi, resample, method="LANCZOS": SizeResolutionAdjuster(
            width_cm, height_cm, dpi, resample=resample, method=method
        ),
    )
    return ProcessingService(DesignEngine(ImageLoader({".png", ".jpg", ".jpeg"})), registry, tmp_path / "out")


def make_file(folder: Path, *, size=(120, 80), dpi=(300, 300), alpha=False, icc=False, name="foto.png") -> Path:
    mode = "RGBA" if alpha else "RGB"
    color = (200, 30, 30, 255) if alpha else (200, 30, 30)
    image = Image.new(mode, size, color)
    if alpha:
        arr = np.array(image)
        arr[: size[1] // 2, :, 3] = 90  # transparencia previa
        image = Image.fromarray(arr, "RGBA")
    kwargs = {"dpi": dpi}
    if icc:
        kwargs["icc_profile"] = srgb_profile()
    path = folder / name
    image.save(path, **kwargs)
    return path


def remove_and_commit(service):
    return service.commit_preview(service.preview_tool("remove_background"))


def same_properties(before: Image.Image, after: Image.Image) -> None:
    assert after.size == before.size  # ancho y alto en píxeles
    assert after.info["dpi"] == before.info["dpi"]  # PPI horizontal y vertical, valor por valor
    assert physical_cm(after) == pytest.approx(physical_cm(before))  # tamaño físico


# ---- 1-5: Remove, con distintos PPI, proporciones y transparencia ----
@pytest.mark.parametrize("dpi", [300, 150])
def test_remove_keeps_size_and_resolution(service, tmp_path, dpi):
    service.open_image(make_file(tmp_path, dpi=(dpi, dpi)))
    before = service.snapshot().image
    after = remove_and_commit(service).image
    same_properties(before, after)
    # un PNG guarda el PPI como píxeles por metro (entero): al CARGAR sale 299.9994 / 150.0124; nada de 72/96
    assert after.info["dpi"][0] == pytest.approx(dpi, abs=0.02)


def test_remove_keeps_different_horizontal_and_vertical_ppi(service, tmp_path):
    service.open_image(make_file(tmp_path, dpi=(300, 150)))
    before = service.snapshot().image
    assert before.info["dpi"][0] != before.info["dpi"][1]
    same_properties(before, remove_and_commit(service).image)


def test_remove_on_an_image_that_already_had_transparency(service, tmp_path):
    service.open_image(make_file(tmp_path, alpha=True, dpi=(240, 240)))
    before = service.snapshot().image
    after = remove_and_commit(service).image
    same_properties(before, after)
    assert after.getchannel("A").getextrema()[0] == 0  # la transparencia se incorporó sin tocar el lienzo


@pytest.mark.parametrize("size", [(1, 1), (7, 300), (500, 13), (3543, 4724), (4000, 3000)])
def test_remove_keeps_any_dimensions_and_proportions(service, tmp_path, size):
    service.open_image(make_file(tmp_path, size=size, dpi=(300, 300)))
    before = service.snapshot().image
    after = remove_and_commit(service).image
    same_properties(before, after)
    assert after.width / after.height == pytest.approx(before.width / before.height)


def test_the_documented_case_30_by_40_cm_at_300_ppi(service, tmp_path):
    service.open_image(make_file(tmp_path, size=(800, 600), dpi=(150, 150)))
    service.apply_tool("size_resolution", width_cm=30, height_cm=40, dpi=300, resample=True)
    before = service.snapshot().image
    assert before.size == (3543, 4724) and before.info["dpi"] == (300, 300)
    after = remove_and_commit(service).image
    same_properties(before, after)
    assert physical_cm(after) == pytest.approx((30.0, 40.0), abs=0.01)


# ---- 6: Pillow y NumPy crean imágenes nuevas sin metadatos; el pipeline las restituye ----
class Fresh(ImageOperation):
    """Herramienta rutinaria que construye una imagen NUEVA (como hace ``Image.fromarray``)."""

    name = "fresh"

    def __init__(self, make):
        self._make = make

    def apply(self, image):
        return self._make(image)


NEW_IMAGE_MAKERS = {
    "numpy": lambda im: Image.fromarray(np.array(im), "RGBA"),
    "pillow_new": lambda im: Image.new("RGBA", im.size, (1, 2, 3, 255)),
    "bytes_roundtrip": lambda im: Image.open(io.BytesIO(_png_bytes(im))).convert("RGBA"),
    "default_72": lambda im: _with(Image.fromarray(np.array(im), "RGBA"), dpi=(72, 72)),
    "default_96": lambda im: _with(im.copy(), dpi=(96, 96)),
}


def _png_bytes(im):
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


def _with(image, **info):
    image.info.update(info)
    return image


@pytest.mark.parametrize("maker", NEW_IMAGE_MAKERS)
def test_a_tool_that_drops_or_resets_metadata_cannot_lose_it(service, tmp_path, maker):
    service.open_image(make_file(tmp_path, dpi=(237, 411), icc=True))
    before = service.snapshot().image
    result = ImagePipeline([Fresh(NEW_IMAGE_MAKERS[maker])]).run(before).image
    same_properties(before, result)
    assert result.info["icc_profile"] == before.info["icc_profile"]


def test_metadata_is_never_invented(service, tmp_path):
    bare = Image.new("RGBA", (10, 10))
    assert "dpi" not in bare.info
    result = ImagePipeline([Fresh(NEW_IMAGE_MAKERS["default_72"])]).run(bare).image
    assert "dpi" not in result.info  # no hay PPI que conservar: no se deja el 72 que puso la herramienta


def test_restore_helpers_do_not_touch_the_source_or_other_keys():
    source = Image.new("RGBA", (4, 4))
    source.info.update(dpi=(300, 300), comment="a")
    result = Image.new("RGBA", (4, 4))
    result.info.update(dpi=(72, 72), other="b")
    restore_metadata(source, result)
    assert result.info == {"dpi": (300, 300), "other": "b"} and source.info == {"dpi": (300, 300), "comment": "a"}
    assert capture_metadata(source) == {"dpi": (300, 300)} and PRESERVED_INFO_KEYS == ("dpi", "icc_profile")


# ---- 8: ninguna herramienta rutinaria restablece el PPI ----
@pytest.mark.parametrize("tool", ["remove_background", "sharpen", "comic_effect"])
def test_no_routine_tool_resets_the_ppi(service, tmp_path, tool):
    service.open_image(make_file(tmp_path, dpi=(237, 237), icc=True))
    before = service.snapshot().image
    after = service.commit_preview(service.preview_tool(tool)).image
    same_properties(before, after)
    assert after.info["dpi"] not in ((72, 72), (96, 96)) and after.info["icc_profile"] == before.info["icc_profile"]


def test_a_chain_of_tools_keeps_the_properties(service, tmp_path):
    service.open_image(make_file(tmp_path, size=(333, 111), dpi=(180, 90)))
    before = service.snapshot().image
    for tool in ("sharpen", "remove_background", "comic_effect", "sharpen"):
        service.apply_tool(tool)
    same_properties(before, service.snapshot().image)


# ---- 7: guardar y volver a cargar ----
@pytest.mark.parametrize("extension", [".png", ".jpg"])
def test_properties_survive_saving_and_reloading(service, tmp_path, extension):
    service.open_image(make_file(tmp_path, size=(200, 100), dpi=(300, 300), icc=True))
    edited = service.apply_tool("sharpen").image
    if extension == ".png":
        edited = remove_and_commit(service).image  # con transparencia: solo PNG
    loader = ImageLoader({".png", ".jpg", ".jpeg"})
    target = tmp_path / f"salida{extension}"
    loader.save(edited, target, flatten_alpha=True)
    reloaded = loader.load(target)
    assert reloaded.size == edited.size
    # el formato guarda el PPI como entero por metro/pulgada: se admite ese redondeo, nada más
    assert reloaded.info["dpi"][0] == pytest.approx(edited.info["dpi"][0], abs=0.01)
    assert reloaded.info["dpi"][1] == pytest.approx(edited.info["dpi"][1], abs=0.01)
    assert reloaded.info["icc_profile"] == edited.info["icc_profile"]


# ---- 9: Tamaño y resolución sí puede cambiarlas, a propósito ----
def test_size_resolution_can_still_change_pixels_and_ppi(service, tmp_path):
    service.open_image(make_file(tmp_path, size=(400, 200), dpi=(150, 150)))
    after = service.apply_tool("size_resolution", width_cm=10, height_cm=5, dpi=300, resample=True).image
    assert after.size == (1181, 591) and after.info["dpi"] == (300, 300)
    assert physical_cm(after) == pytest.approx((10, 5), abs=0.01)


def test_size_resolution_without_resampling_changes_only_the_ppi(service, tmp_path):
    service.open_image(make_file(tmp_path, size=(400, 200), dpi=(150, 150)))
    before = service.snapshot().image
    after = service.apply_tool("size_resolution", width_cm=20, height_cm=10, dpi=508, resample=False).image
    assert after.size == before.size and after.info["dpi"] == (508, 508)


def test_size_resolution_keeps_the_icc_profile(service, tmp_path):
    service.open_image(make_file(tmp_path, dpi=(150, 150), icc=True))
    after = service.apply_tool("size_resolution", width_cm=10, height_cm=5, dpi=300, resample=True).image
    assert after.info["icc_profile"] == srgb_profile()


# ---- contrato de tamaño en píxeles ----
class Shrinks(ImageOperation):
    name = "shrinks"

    def apply(self, image):
        return image.resize((image.width // 2, image.height // 2))


class ShrinksOnPurpose(Shrinks):
    name = "crops"
    changes_geometry = True


def test_a_tool_cannot_change_the_pixel_size_without_declaring_it(service, tmp_path):
    service.open_image(make_file(tmp_path))
    with pytest.raises(ProcessingError, match="sin declarar"):
        ImagePipeline([Shrinks()]).run(service.snapshot().image)


def test_a_declared_geometry_change_keeps_the_ppi_so_the_physical_size_follows(service, tmp_path):
    service.open_image(make_file(tmp_path, size=(120, 80), dpi=(300, 300)))
    before = service.snapshot().image
    after = ImagePipeline([ShrinksOnPurpose()]).run(before).image
    assert after.size == (60, 40) and after.info["dpi"] == before.info["dpi"]
    assert physical_cm(after) == pytest.approx((physical_cm(before)[0] / 2, physical_cm(before)[1] / 2))


def test_the_failed_tool_leaves_the_document_untouched(service, tmp_path):
    service.open_image(make_file(tmp_path))
    before = service.snapshot().image
    with pytest.raises(ProcessingError):
        ImagePipeline([Shrinks()]).run(before)
    assert service.snapshot().image is before and before.info["dpi"][0] == pytest.approx(300, abs=0.01)


def test_a_tool_that_loses_metadata_is_logged_for_diagnosis(service, tmp_path, caplog):
    service.open_image(make_file(tmp_path, dpi=(300, 300)))
    with caplog.at_level("INFO", logger="core.image_pipeline"):
        ImagePipeline([Fresh(NEW_IMAGE_MAKERS["numpy"])]).run(service.snapshot().image)
        ImagePipeline([ImageSharpener()]).run(service.snapshot().image)
    assert caplog.text.count("no conservó dpi") == 1 and "'fresh'" in caplog.text  # solo la que lo perdió
