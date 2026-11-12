"""Cubre los 10 escenarios obligatorios del encargo 'Tamaño y resolución'."""
import math

import numpy as np
import pytest
from PIL import Image

from core.exceptions import ValidationError
from tools.size_resolution import (
    DEFAULT_METHOD,
    RESAMPLE_METHODS,
    Axis,
    SizeResolutionAdjuster,
    cm_to_px,
    compute_target_px,
    effective_dpi,
    paired_dimension_cm,
    px_to_cm,
)


# --- TEST 1 y 2: conversión cm -> px ---------------------------------------

def test_29cm_at_300ppi_is_about_3425px():
    assert cm_to_px(29, 300) == 3425


def test_42cm_at_300ppi_is_about_4961px():
    assert cm_to_px(42, 300) == 4961  # round(4960.63) == 4961, no truncar


# --- TEST 3: remuestrear OFF no cambia los píxeles -------------------------

def test_resample_off_keeps_pixels_unchanged():
    src = Image.new("RGBA", (3000, 2000), (10, 20, 30, 255))
    op = SizeResolutionAdjuster(50, 33, dpi=150, resample=False)
    out = op.apply(src)
    assert out.size == (3000, 2000)
    assert out.info["dpi"] == (150, 150)


def test_resample_off_does_not_mutate_the_original():
    src = Image.new("RGBA", (10, 10), (1, 2, 3, 255))
    SizeResolutionAdjuster(5, 5, dpi=72, resample=False).apply(src)
    assert "dpi" not in src.info  # la copia lleva el nuevo dpi, el original no


# --- TEST 4: remuestrear ON sí cambia los píxeles --------------------------

def test_resample_on_changes_pixel_dimensions():
    src = Image.new("RGBA", (3000, 2000), (10, 20, 30, 255))
    op = SizeResolutionAdjuster(10, 10, dpi=300, resample=True)
    out = op.apply(src)
    assert out.size == compute_target_px(10, 10, 300)
    assert out.size != (3000, 2000)
    assert out.info["dpi"] == (300, 300)


# --- TEST 5: RGBA / transparencia se conserva ------------------------------

def test_rgba_and_transparency_survive_resample():
    src = Image.new("RGBA", (40, 40), (200, 50, 50, 77))
    out = SizeResolutionAdjuster(5, 5, dpi=150, resample=True).apply(src)
    assert out.mode == "RGBA"
    assert set(np.array(out)[..., 3].flatten().tolist()) == {77}


def test_rgba_and_transparency_survive_no_resample():
    src = Image.new("RGBA", (40, 40), (200, 50, 50, 77))
    out = SizeResolutionAdjuster(5, 5, dpi=150, resample=False).apply(src)
    assert out.mode == "RGBA"
    assert set(np.array(out)[..., 3].flatten().tolist()) == {77}


# --- TEST 6: mantener proporción -------------------------------------------

def test_paired_dimension_keeps_original_proportion():
    # Imagen 2:3 (736 x 1104, como en el encargo).
    height = paired_dimension_cm((736, 1104), 10, Axis.WIDTH)
    assert math.isclose(height, 15.0, rel_tol=1e-9)
    width = paired_dimension_cm((736, 1104), 15, Axis.HEIGHT)
    assert math.isclose(width, 10.0, rel_tol=1e-9)


# --- TEST 7: proporción desactivada = ancho/alto independientes -----------

def test_width_and_height_can_be_set_independently():
    # El Tool no fuerza ninguna relación entre width_cm y height_cm: la
    # operación acepta cualquier combinación (deformación intencional).
    src = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
    out = SizeResolutionAdjuster(20, 5, dpi=300, resample=True).apply(src)
    assert out.size == compute_target_px(20, 5, 300)
    assert out.size[0] != out.size[1]  # se deformó a propósito


# --- TEST 8: el DPI se guarda y se puede volver a leer ---------------------

def test_dpi_metadata_round_trips_through_png_save(tmp_path):
    src = Image.new("RGBA", (300, 300), (5, 5, 5, 255))
    out = SizeResolutionAdjuster(10, 10, dpi=300, resample=True).apply(src)
    path = tmp_path / "out.png"
    out.save(path, format="PNG", dpi=out.info["dpi"])
    reopened = Image.open(path)
    # PNG guarda el DPI como píxeles/metro y lo reconvierte: puede quedar un
    # resto de punto flotante (p. ej. 299.9994 en vez de 300 exacto).
    assert reopened.info["dpi"][0] == pytest.approx(300, abs=0.01)


# --- TEST 9: validación --------------------------------------------------

@pytest.mark.parametrize("bad_dpi", [0, -5, float("nan"), float("inf")])
def test_rejects_invalid_dpi(bad_dpi):
    with pytest.raises(ValidationError):
        SizeResolutionAdjuster(10, 10, dpi=bad_dpi, resample=True)


@pytest.mark.parametrize("bad_width", [0, -5, float("nan")])
def test_rejects_invalid_width(bad_width):
    with pytest.raises(ValidationError):
        SizeResolutionAdjuster(bad_width, 10, dpi=300, resample=True)


@pytest.mark.parametrize("bad_height", [0, -5, float("nan")])
def test_rejects_invalid_height(bad_height):
    with pytest.raises(ValidationError):
        SizeResolutionAdjuster(10, bad_height, dpi=300, resample=True)


def test_cm_to_px_and_px_to_cm_reject_non_positive():
    for fn, args in [(cm_to_px, (0, 300)), (cm_to_px, (10, 0)), (px_to_cm, (100, -1))]:
        with pytest.raises(ValidationError):
            fn(*args)


def test_effective_dpi_rejects_non_positive_cm():
    with pytest.raises(ValidationError):
        effective_dpi(1000, 0)


# --- TEST 10: LANCZOS es el método predeterminado --------------------------

def test_lanczos_is_the_default_method():
    assert DEFAULT_METHOD == "LANCZOS"
    op = SizeResolutionAdjuster(10, 10, dpi=300, resample=True)
    assert op.method == "LANCZOS"
    assert RESAMPLE_METHODS["LANCZOS"] is Image.Resampling.LANCZOS


def test_rejects_unknown_resample_method():
    with pytest.raises(ValidationError):
        SizeResolutionAdjuster(10, 10, dpi=300, resample=True, method="MAGIC")


# --- Extra: fórmulas básicas ------------------------------------------------

def test_px_to_cm_is_inverse_of_cm_to_px_within_rounding():
    px = cm_to_px(29, 300)
    assert math.isclose(px_to_cm(px, 300), 29, abs_tol=0.01)


def test_effective_dpi_matches_cm_to_px_formula():
    # Si 29cm @ 300ppi da `px`, entonces effective_dpi(px, 29) debe ser ~300.
    px = cm_to_px(29, 300)
    assert math.isclose(effective_dpi(px, 29), 300, rel_tol=0.001)


def test_label_differs_with_and_without_resample():
    with_resample = SizeResolutionAdjuster(10, 10, dpi=300, resample=True).label
    without_resample = SizeResolutionAdjuster(10, 10, dpi=300, resample=False).label
    assert "300" in with_resample and "300" in without_resample
    assert with_resample != without_resample


# --- Regresión: el diálogo debe precargarse con el DPI REAL de la imagen,
# no con el valor recomendado (300), salvo que la imagen no traiga DPI. ----

@pytest.mark.parametrize("real_dpi", [72, 150, 300])
def test_opening_an_image_exposes_its_real_dpi_not_the_recommended_default(tmp_path, real_dpi):
    from core.models import ProcessingState
    from tools.image_loader import ImageLoader

    path = tmp_path / f"img_{real_dpi}.png"
    Image.new("RGB", (100, 50), "gray").save(path, dpi=(real_dpi, real_dpi))

    state = ProcessingState()
    state.load(path, ImageLoader({".png"}).load(path))

    # Esto es exactamente lo que main_window._on_size_resolution usa para
    # precargar el campo "Resolución (PPI)" del diálogo.
    snapshot_dpi = state.snapshot().dpi
    assert snapshot_dpi == pytest.approx(real_dpi, abs=0.1)
    assert snapshot_dpi != 300 or real_dpi == 300  # nunca cae en 300 "por accidente"


def test_opening_the_dialog_does_not_mutate_the_image(tmp_path):
    from core.models import ProcessingState
    from tools.image_loader import ImageLoader

    path = tmp_path / "img.png"
    Image.new("RGB", (100, 50), "gray").save(path, dpi=(72, 72))
    image = ImageLoader({".png"}).load(path)
    before_bytes = image.tobytes()
    before_size, before_mode = image.size, image.mode

    state = ProcessingState()
    state.load(path, image)
    # Leer el DPI (lo que hace el diálogo al abrirse) no debe tocar la imagen.
    _ = state.snapshot().dpi
    _ = state.snapshot().dpi

    assert image.tobytes() == before_bytes
    assert image.size == before_size and image.mode == before_mode


# --- Selectores de unidad del diálogo: core/units.py + los 4 wrappers del
# controller (length_to_cm/length_from_cm/resolution_to_ppi/resolution_from_ppi).
# La referencia interna sigue siendo cm/PPI; esto solo cubre la capa de
# conversión agregada para mm/px y px/cm. -------------------------------

from core import units  # noqa: E402
from tools.size_resolution import SizeResolutionController  # noqa: E402


def _fake_design_controller():
    class _FakeDesignController:
        def check_positive(self, value, label):
            return value

        def parse_positive(self, text, label):
            return float(text)

        def run_tool(self, *args, **kwargs):
            raise AssertionError("no debería despachar nada en estos tests")

        def warn(self, message):
            raise AssertionError("no debería advertir en estos tests")

    return _FakeDesignController()


def test_units_mm_cm_round_trip():
    assert units.cm_to_mm(10) == 100
    assert units.mm_to_cm(100) == 10


def test_units_cm_px_round_trip_matches_size_resolution_formula():
    px = units.cm_to_px(29, 300)
    assert math.isclose(px, 3425.19, rel_tol=1e-3)
    assert math.isclose(units.px_to_cm(px, 300), 29, rel_tol=1e-9)


def test_units_ppi_px_per_cm_round_trip_matches_encargo_example():
    # "300 PPI → 118.11 px/cm" y "118.11 px/cm → aproximadamente 300 PPI"
    px_per_cm = units.dpi_to_px_per_cm(300)
    assert math.isclose(px_per_cm, 118.11, abs_tol=0.01)
    assert math.isclose(units.px_per_cm_to_dpi(px_per_cm), 300, abs_tol=0.01)


def test_controller_length_conversions_default_to_cm_unchanged():
    controller = SizeResolutionController(_fake_design_controller())
    assert controller.length_to_cm(10, "cm", dpi=300) == 10
    assert controller.length_from_cm(10, "cm", dpi=300) == 10


def test_controller_length_conversions_mm_and_px():
    controller = SizeResolutionController(_fake_design_controller())
    assert controller.length_to_cm(100, "mm", dpi=300) == 10
    assert controller.length_from_cm(10, "mm", dpi=300) == 100
    px = controller.length_from_cm(10, "px", dpi=300)
    assert math.isclose(controller.length_to_cm(px, "px", dpi=300), 10, rel_tol=1e-9)


def test_controller_resolution_conversions_default_to_ppi_unchanged():
    controller = SizeResolutionController(_fake_design_controller())
    assert controller.resolution_to_ppi(300, "PPI") == 300
    assert controller.resolution_from_ppi(300, "PPI") == 300


def test_controller_resolution_conversions_px_per_cm():
    controller = SizeResolutionController(_fake_design_controller())
    px_per_cm = controller.resolution_from_ppi(300, "px/cm")
    assert math.isclose(px_per_cm, 118.11, abs_tol=0.01)
    assert math.isclose(controller.resolution_to_ppi(px_per_cm, "px/cm"), 300, abs_tol=0.01)
