"""tests/test_viewport.py

Responsabilidad:
    - Pruebas unitarias de gui/viewport.py (ViewportModel): proporciones,
      centrado, límites del desplazamiento, zoom (incluido el anclado en un
      punto), paneo, cambio de tamaño del viewport o de la imagen,
      validación de valores y casos extremos.
    - Comprobar que el modelo es independiente de la interfaz: no importa
      tkinter, customtkinter, Pillow ni numpy.

No conoce:
    - Ventanas, widgets ni eventos; no requiere display.
"""
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

from gui.viewport import DEFAULT_MAX_ZOOM, DEFAULT_MIN_ZOOM, ViewportModel

REPO_ROOT = Path(__file__).resolve().parent.parent
LANDSCAPE, PORTRAIT, SQUARE = (1600, 900), (900, 1400), (1000, 1000)
VIEWPORTS = [(800, 600), (600, 800), (500, 500), (1920, 1080), (300, 2000), (1, 1), (37, 211)]
EPS = 1e-6


def check_invariants(model: ViewportModel, image: tuple[float, float]) -> None:
    """Reglas que deben cumplirse SIEMPRE, tras cualquier secuencia de operaciones."""
    iw, ih = image
    assert model.image_size == (iw, ih)  # el tamaño original no se toca nunca
    assert model.min_zoom - EPS <= model.zoom <= model.max_zoom + EPS
    rw, rh = model.rendered_size
    assert rw == pytest.approx(iw * model.zoom) and rh == pytest.approx(ih * model.zoom)
    assert rw / rh == pytest.approx(iw / ih, rel=1e-9)  # proporción conservada
    vw, vh = model.viewport_size
    x, y = model.position
    (min_x, max_x), (min_y, max_y) = model.position_bounds
    assert min_x - EPS <= x <= max_x + EPS and min_y - EPS <= y <= max_y + EPS
    for viewport_len, rendered_len, pos, fits in ((vw, rw, x, model.fits[0]), (vh, rh, y, model.fits[1])):
        if fits:
            assert pos == pytest.approx((viewport_len - rendered_len) / 2, abs=EPS)  # centrada
        else:
            assert pos <= EPS and pos + rendered_len >= viewport_len - EPS  # bordes sin hueco
    if vw > 0 and vh > 0:  # nunca se pierde de vista
        assert x < vw and x + rw > 0 and y < vh and y + rh > 0


# ---------------------------------------------------------------- independencia

def test_module_does_not_import_gui_or_imaging_libraries():
    code = (
        "import sys, gui.viewport; "
        "bad = [m for m in ('tkinter', 'customtkinter', 'PIL', 'numpy') if m in sys.modules]; "
        "print(','.join(bad))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


# ------------------------------------------------------- ajuste y proporciones

@pytest.mark.parametrize("image", [LANDSCAPE, PORTRAIT, SQUARE, (4000, 10), (10, 4000)])
@pytest.mark.parametrize("viewport", VIEWPORTS)
def test_fit_keeps_proportions_fits_touches_one_edge_and_is_centred(image, viewport):
    model = ViewportModel(image, viewport)
    (iw, ih), (vw, vh) = image, viewport
    rw, rh = model.rendered_size
    assert model.fit_mode and model.fits == (True, True)
    assert rw / rh == pytest.approx(iw / ih)
    assert rw <= vw + EPS and rh <= vh + EPS
    assert min(vw - rw, vh - rh) == pytest.approx(0, abs=EPS)  # llena la dimensión limitante
    assert model.position == pytest.approx(((vw - rw) / 2, (vh - rh) / 2))
    check_invariants(model, image)


@pytest.mark.parametrize("image", [LANDSCAPE, PORTRAIT, SQUARE, (7, 3), (3, 7)])
def test_aspect_ratio_is_preserved_at_every_zoom(image):
    model = ViewportModel(image, (800, 600))
    for zoom in (0.001, 0.05, 0.3, 1, 2.5, 17, 32, 1000):
        model.set_zoom(zoom)
        rw, rh = model.rendered_size
        assert rw / rh == pytest.approx(image[0] / image[1], rel=1e-12)


def test_fit_matches_the_formula_of_the_current_image_panel():
    """Misma geometría de ajuste que ImagePanel._render, para poder integrarlo después."""
    for image in (LANDSCAPE, PORTRAIT, SQUARE, (2048, 1365)):
        for avail in ((936, 466), (600, 800), (1200, 300)):
            (pw, ph), (aw, ah) = image, avail
            scale = min(aw / pw, ah / ph)
            expected = (max(1, int(pw * scale)), max(1, int(ph * scale)))
            rw, rh = ViewportModel(image, avail).rendered_size_px
            assert abs(rw - expected[0]) <= 1 and abs(rh - expected[1]) <= 1


def test_fit_mode_always_fits_despite_floating_point_rounding():
    rng = random.Random(7)
    for _ in range(500):
        image = (rng.randint(1, 20000), rng.randint(1, 20000))
        viewport = (rng.randint(1, 4000), rng.randint(1, 4000))
        model = ViewportModel(image, viewport)
        assert model.fits == (True, True)
        (min_x, max_x), (min_y, max_y) = model.position_bounds
        assert min_x == max_x and min_y == max_y


# -------------------------------------------------- imagen menor / mayor / mixta

@pytest.mark.parametrize("image", [(200, 100), (100, 200), (150, 150)])
def test_image_smaller_than_viewport_is_centred_on_both_axes_and_cannot_be_panned(image):
    model = ViewportModel(image, (800, 600))
    model.set_zoom(1.0)
    assert model.rendered_size == image
    expected = ((800 - image[0]) / 2, (600 - image[1]) / 2)
    assert model.position == expected and model.fits == (True, True)
    (min_x, max_x), (min_y, max_y) = model.position_bounds
    assert (min_x, min_y) == (max_x, max_y) == expected
    for dx, dy in ((500, -500), (-9999, 9999)):
        model.pan_by(dx, dy)
        assert model.position == expected
    model.pan_to(0, 0)
    assert model.position == expected


def test_image_larger_than_viewport_is_limited_by_its_edges_on_each_axis():
    model = ViewportModel((2000, 1500), (800, 600))
    model.set_zoom(1.0)
    assert model.fits == (False, False)
    assert model.position == (-600.0, -450.0)  # empieza centrada sobre el centro de la imagen
    assert model.position_bounds == ((-1200.0, 0.0), (-900.0, 0.0))
    model.pan_to(10**6, 10**6)
    assert model.position == (0.0, 0.0)  # borde izquierdo y superior pegados al viewport
    model.pan_to(-(10**6), -(10**6))
    assert model.position == (-1200.0, -900.0)  # borde derecho e inferior pegados
    model.pan_by(50, 25)
    assert model.position == (-1150.0, -875.0)
    model.pan_by(-(10**9), 0)
    assert model.position == (-1200.0, -875.0)  # un eje limitado, el otro libre
    check_invariants(model, (2000, 1500))


def test_wide_image_scrolls_horizontally_and_stays_centred_vertically():
    model = ViewportModel((4000, 200), (800, 600))
    model.set_zoom(1.0)
    assert model.fits == (False, True)
    assert model.position_bounds == ((-3200.0, 0.0), (200.0, 200.0))
    model.pan_to(-500, 0)
    assert model.position == (-500.0, 200.0)


def test_tall_image_scrolls_vertically_and_stays_centred_horizontally():
    model = ViewportModel((200, 4000), (800, 600))
    model.set_zoom(1.0)
    assert model.fits == (True, False)
    assert model.position_bounds == ((300.0, 300.0), (-3400.0, 0.0))
    model.pan_to(0, -1000)
    assert model.position == (300.0, -1000.0)


def test_image_can_never_be_lost_from_view_under_random_operations():
    rng = random.Random(20241031)
    for _ in range(40):
        image = (rng.uniform(1, 9000), rng.uniform(1, 9000))
        model = ViewportModel(image, (rng.uniform(0, 2500), rng.uniform(0, 2500)))
        for _ in range(80):
            vw, vh = model.viewport_size
            anchor = (rng.uniform(-100, vw + 100), rng.uniform(-100, vh + 100))
            op = rng.choice(("pan_by", "pan_to", "zoom_by", "set_zoom", "viewport", "image", "fit"))
            if op == "pan_by":
                model.pan_by(rng.uniform(-4000, 4000), rng.uniform(-4000, 4000))
            elif op == "pan_to":
                model.pan_to(rng.uniform(-20000, 20000), rng.uniform(-20000, 20000))
            elif op == "zoom_by":
                model.zoom_by(rng.uniform(0.2, 5), anchor)
            elif op == "set_zoom":
                model.set_zoom(rng.uniform(0.001, 100), anchor)
            elif op == "viewport":
                model.set_viewport_size(rng.uniform(0, 2500), rng.uniform(0, 2500))
            elif op == "image":
                image = (rng.uniform(1, 9000), rng.uniform(1, 9000))
                model.set_image_size(*image, keep_view=rng.random() < 0.5)
            else:
                model.fit()
            check_invariants(model, image)


# ------------------------------------------------- cambio de tamaño del viewport

def test_resizing_viewport_in_fit_mode_refits_without_touching_the_image_size():
    model = ViewportModel(LANDSCAPE, (800, 600))
    assert model.zoom == pytest.approx(0.5)
    model.set_viewport_size(1600, 450)
    assert model.zoom == pytest.approx(0.5)
    model.set_viewport_size(400, 1000)
    assert model.zoom == pytest.approx(0.25)
    assert model.image_size == LANDSCAPE
    fresh = ViewportModel(LANDSCAPE, (400, 1000))
    assert model.zoom == pytest.approx(fresh.zoom) and model.position == pytest.approx(fresh.position)


def test_resizing_viewport_in_manual_zoom_keeps_the_image_point_at_the_centre():
    model = ViewportModel((4000, 3000), (800, 600))
    model.set_zoom(1.0)
    model.pan_to(-1000, -700)
    centre = model.viewport_to_image(400, 300)
    model.set_viewport_size(1000, 700)
    assert model.zoom == 1.0 and not model.fit_mode
    assert model.viewport_to_image(500, 350) == pytest.approx(centre)
    model.set_viewport_size(5000, 4000)  # ahora la imagen cabe: queda centrada
    assert model.fits == (True, True)
    assert model.position == pytest.approx((500, 500))
    assert model.image_size == (4000, 3000)


def test_same_viewport_size_changes_nothing():
    model = ViewportModel((4000, 3000), (800, 600))
    model.set_zoom(1.0)
    model.pan_to(-1000, -700)
    before = (model.zoom, model.position)
    model.set_viewport_size(800, 600)
    assert (model.zoom, model.position) == before


def test_zero_sized_viewport_is_valid_and_recovers_when_resized():
    model = ViewportModel((1000, 800), (0, 0))
    assert model.viewport_size == (0.0, 0.0)
    assert model.zoom == DEFAULT_MIN_ZOOM and model.fits == (False, False)
    model.pan_by(10, 10)
    check_invariants(model, (1000, 800))
    model.set_viewport_size(500, 500)
    assert model.fit_mode and model.zoom == pytest.approx(0.5)
    assert model.position == pytest.approx((0, 50))


def test_default_viewport_is_zero_sized():
    assert ViewportModel((10, 10)).viewport_size == (0.0, 0.0)


# ----------------------------------------------------------------------- zoom

def test_zoom_is_limited_to_the_configured_range():
    model = ViewportModel((1000, 800), (800, 600))
    model.zoom_by(1e9)
    assert model.zoom == DEFAULT_MAX_ZOOM and not model.fit_mode
    model.zoom_by(1.25)
    assert model.zoom == DEFAULT_MAX_ZOOM
    model.zoom_by(1e-9)
    assert model.zoom == DEFAULT_MIN_ZOOM
    model.set_zoom(0.0001)
    assert model.zoom == DEFAULT_MIN_ZOOM
    model.set_zoom(10**6)
    assert model.zoom == DEFAULT_MAX_ZOOM
    check_invariants(model, (1000, 800))


def test_zoom_factor_that_overflows_or_underflows_is_still_clamped():
    model = ViewportModel((1000, 800), (800, 600))
    model.set_zoom(32)
    model.zoom_by(1.7e308)  # 32 · 1.7e308 desborda a infinito
    assert model.zoom == DEFAULT_MAX_ZOOM
    model.set_zoom(0.05)
    model.zoom_by(5e-324)  # 0.05 · 5e-324 desborda por abajo a 0
    assert model.zoom == DEFAULT_MIN_ZOOM


def test_custom_zoom_limits_are_respected():
    model = ViewportModel((1000, 800), (800, 600), min_zoom=0.5, max_zoom=2.0)
    model.set_zoom(10)
    assert model.zoom == 2.0
    model.set_zoom(0.01)
    assert model.zoom == 0.5


def test_fit_is_always_reachable_for_huge_images():
    model = ViewportModel((100000, 50000), (800, 600))
    assert model.fit_zoom == pytest.approx(0.008) and model.min_zoom == pytest.approx(0.008)
    assert model.fit_mode and model.fits == (True, True)
    model.zoom_by(0.1)  # no baja del mínimo efectivo
    assert model.zoom == pytest.approx(0.008)
    check_invariants(model, (100000, 50000))


def test_tiny_image_fit_is_capped_at_max_zoom_and_stays_centred():
    model = ViewportModel((1, 1), (800, 600))
    assert model.zoom == DEFAULT_MAX_ZOOM and model.fit_mode
    assert model.rendered_size == (32.0, 32.0)
    assert model.position == (384.0, 284.0)
    assert model.fits == (True, True)


@pytest.mark.parametrize("factor", [1.25, 0.8, 2.0, 0.5])
@pytest.mark.parametrize("anchor", [(300, 200), (0, 0), (799, 599), (400, 300), (123.5, 456.25)])
def test_zoom_keeps_the_point_under_the_cursor_fixed(factor, anchor):
    model = ViewportModel((6000, 4000), (800, 600))
    model.set_zoom(1.0)
    model.pan_to(-2000, -1500)
    point = model.viewport_to_image(*anchor)
    model.zoom_by(factor, anchor)
    assert model.viewport_to_image(*anchor) == pytest.approx(point)
    assert model.image_to_viewport(*point) == pytest.approx(anchor)
    check_invariants(model, (6000, 4000))


def test_zoom_without_anchor_uses_the_viewport_centre():
    model = ViewportModel((6000, 4000), (800, 600))
    model.set_zoom(1.0)
    model.pan_to(-2000, -1500)
    point = model.viewport_to_image(400, 300)
    model.zoom_by(2.0)
    assert model.viewport_to_image(400, 300) == pytest.approx(point)


def test_zoom_out_near_an_edge_is_clamped_instead_of_leaving_gaps():
    model = ViewportModel((3000, 2000), (800, 600))
    model.set_zoom(1.0)
    model.pan_to(0, 0)
    model.zoom_by(0.5, (700, 500))
    assert model.position == (0.0, 0.0)
    check_invariants(model, (3000, 2000))


def test_zooming_out_until_the_image_fits_centres_it():
    model = ViewportModel((2000, 1500), (800, 600))
    model.set_zoom(1.0)
    model.zoom_by(0.1, (10, 10))  # zoom 0.1 → 200×150, cabe de sobra
    assert model.fits == (True, True)
    assert model.position == pytest.approx((300, 225))


def test_explicit_zoom_leaves_fit_mode_and_fit_returns_to_it():
    model = ViewportModel(LANDSCAPE, (800, 600))
    assert model.fit_mode
    model.zoom_by(1.0)  # sin cambio real
    model.set_zoom(model.fit_zoom)
    assert model.fit_mode
    model.zoom_by(3.0)
    model.pan_by(-40, -40)
    assert not model.fit_mode
    model.fit()
    assert model.fit_mode and model.zoom == pytest.approx(model.fit_zoom)
    assert model.position == pytest.approx(((800 - model.rendered_size[0]) / 2, (600 - model.rendered_size[1]) / 2))


def test_panning_never_changes_zoom_or_mode():
    model = ViewportModel((4000, 3000), (800, 600))
    model.set_zoom(1.0)
    before = (model.zoom, model.fit_mode, model.image_size)
    model.pan_by(-300, -200)
    model.pan_to(-10, -10)
    assert (model.zoom, model.fit_mode, model.image_size) == before


# ------------------------------------------------------------ imagen cambiada

def test_new_image_size_resets_to_fit_by_default():
    model = ViewportModel((1000, 800), (800, 600))
    model.set_zoom(3.0)
    model.set_image_size(2000, 1000)
    assert model.fit_mode and model.image_size == (2000.0, 1000.0)
    assert model.zoom == pytest.approx(0.4)


def test_keep_view_preserves_manual_zoom_and_relative_centre():
    model = ViewportModel((1000, 800), (800, 600))
    model.set_zoom(2.0)
    model.pan_to(-700, -500)
    cx, cy = model.viewport_to_image(400, 300)
    model.set_image_size(2000, 1600, keep_view=True)
    assert model.zoom == 2.0 and not model.fit_mode
    ncx, ncy = model.viewport_to_image(400, 300)
    assert ncx / 2000 == pytest.approx(cx / 1000) and ncy / 1600 == pytest.approx(cy / 800)


def test_keep_view_in_fit_mode_stays_in_fit_mode():
    model = ViewportModel((1000, 800), (800, 600))
    model.set_image_size(500, 500, keep_view=True)
    assert model.fit_mode and model.zoom == pytest.approx(1.2)


# ---------------------------------------------------------------- conversiones

def test_coordinate_conversions_round_trip():
    rng = random.Random(3)
    model = ViewportModel((3000, 2000), (800, 600))
    model.set_zoom(1.7)
    model.pan_to(-500, -300)
    for _ in range(100):
        point = (rng.uniform(-500, 1500), rng.uniform(-500, 1500))
        assert model.image_to_viewport(*model.viewport_to_image(*point)) == pytest.approx(point)


def test_rendered_size_px_is_a_positive_integer_close_to_the_float_size():
    for image, zoom in (((1, 1), 0.05), ((1000, 333), 0.7), ((3, 2000), 1.0)):
        model = ViewportModel(image, (500, 500))
        model.set_zoom(zoom)
        px = model.rendered_size_px
        assert all(isinstance(v, int) and v >= 1 for v in px)
        assert all(abs(p - r) < 1 or p == 1 for p, r in zip(px, model.rendered_size))


# ------------------------------------------------------------------ validación

@pytest.mark.parametrize(
    "bad,error",
    [
        ((0, 10), ValueError), ((10, 0), ValueError), ((-1, 5), ValueError), ((5, -1), ValueError),
        ((math.nan, 5), ValueError), ((5, math.inf), ValueError), ((-math.inf, 5), ValueError),
        ((10**400, 5), ValueError),
        (("a", 5), TypeError), ((None, 5), TypeError), ((True, 5), TypeError),
        (10, TypeError), ((1, 2, 3), TypeError), (None, TypeError), ("12", TypeError),
    ],
)
def test_invalid_image_size_is_rejected(bad, error):
    with pytest.raises(error):
        ViewportModel(bad, (100, 100))


@pytest.mark.parametrize(
    "width,height,error",
    [
        (0, 10, ValueError), (10, 0, ValueError), (-1, 5, ValueError),
        (math.nan, 5, ValueError), (5, math.inf, ValueError),
        ("a", 5, TypeError), (None, 5, TypeError), (True, 5, TypeError),
    ],
)
def test_set_image_size_rejects_invalid_values(width, height, error):
    model = ViewportModel((10, 10), (100, 100))
    with pytest.raises(error):
        model.set_image_size(width, height)
    assert model.image_size == (10.0, 10.0)


@pytest.mark.parametrize(
    "bad,error",
    [
        ((-1, 5), ValueError), ((5, -0.001), ValueError), ((math.nan, 5), ValueError),
        ((5, math.inf), ValueError), (("a", 5), TypeError), ((5, None), TypeError),
        ((100,), TypeError), (100, TypeError),
    ],
)
def test_invalid_viewport_size_is_rejected_but_zero_is_valid(bad, error):
    with pytest.raises(error):
        ViewportModel((10, 10), bad)
    ViewportModel((10, 10), (0, 0))
    ViewportModel((10, 10), (0, 300))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_zoom": 0}, {"min_zoom": -1}, {"max_zoom": 0}, {"max_zoom": math.nan},
        {"min_zoom": math.inf}, {"min_zoom": 2.0, "max_zoom": 1.0},
    ],
)
def test_invalid_zoom_limits_are_rejected(kwargs):
    with pytest.raises(ValueError):
        ViewportModel((10, 10), (100, 100), **kwargs)


def test_a_rejected_call_leaves_the_state_unchanged():
    model = ViewportModel(LANDSCAPE, (800, 600))
    model.set_zoom(1.0)
    model.pan_to(-100, -50)

    def state():
        return (model.image_size, model.viewport_size, model.zoom, model.position, model.fit_mode)

    before = state()
    bad_calls = [
        lambda: model.set_viewport_size(math.nan, 5),
        lambda: model.set_viewport_size(-1, 5),
        lambda: model.set_image_size(0, 5),
        lambda: model.set_image_size(5, math.inf),
        lambda: model.set_zoom(0),
        lambda: model.set_zoom(math.nan),
        lambda: model.set_zoom("2"),
        lambda: model.zoom_by(-2),
        lambda: model.zoom_by(math.inf),
        lambda: model.zoom_by(2, anchor=(math.nan, 0)),
        lambda: model.zoom_by(2, anchor="ab"),
        lambda: model.zoom_by(2, anchor=(1, 2, 3)),
        lambda: model.pan_by(math.inf, 0),
        lambda: model.pan_by(0, None),
        lambda: model.pan_to(0, math.nan),
        lambda: model.viewport_to_image(math.nan, 0),
        lambda: model.image_to_viewport(0, "x"),
    ]
    for call in bad_calls:
        with pytest.raises((TypeError, ValueError)):
            call()
        assert state() == before


# ------------------------------------------------------------- área visible

def test_visible_area_of_a_fitted_image_is_the_whole_image_centred():
    model = ViewportModel(LANDSCAPE, (936, 466))
    area = model.visible_area()
    x0, y0, x1, y1 = area.destination
    assert area.source == (0.0, 0.0, 1600.0, 900.0)
    assert (x1 - x0, y1 - y0) == model.rendered_size_px
    assert abs(x0 - (936 - x1)) <= 1 and abs(y0 - (466 - y1)) <= 1  # mismo margen a ambos lados


@pytest.mark.parametrize("image", [LANDSCAPE, PORTRAIT, SQUARE, (1, 1), (4000, 10), (10, 4000)])
@pytest.mark.parametrize("viewport", VIEWPORTS)
def test_visible_area_destination_stays_inside_the_viewport_and_close_to_the_rendered_size(image, viewport):
    model = ViewportModel(image, viewport)
    area = model.visible_area()
    (vw, vh), (rw, rh) = viewport, model.rendered_size
    x0, y0, x1, y1 = area.destination
    assert 0 <= x0 < x1 <= vw and 0 <= y0 < y1 <= vh
    assert abs((x1 - x0) - rw) <= 1 and abs((y1 - y0) - rh) <= 1
    assert area.source == (0.0, 0.0, float(image[0]), float(image[1]))


def test_visible_area_of_a_cropped_image_maps_the_viewport_to_the_right_source_region():
    model = ViewportModel((2000, 1500), (800, 600))
    model.set_zoom(1.0)
    assert model.visible_area().destination == (0, 0, 800, 600)
    assert model.visible_area().source == (600.0, 450.0, 1400.0, 1050.0)  # centro de la imagen
    model.pan_to(0, 0)
    assert model.visible_area().source == (0.0, 0.0, 800.0, 600.0)
    model.pan_to(-10**6, -10**6)
    assert model.visible_area().source == (1200.0, 900.0, 2000.0, 1500.0)


def test_visible_area_with_one_axis_cropped_and_the_other_whole():
    model = ViewportModel((4000, 200), (800, 600))
    model.set_zoom(1.0)
    model.pan_to(-500, 0)
    area = model.visible_area()
    assert area.destination == (0, 200, 800, 400)  # y: entera y centrada
    assert area.source == (500.0, 0.0, 1300.0, 200.0)


def test_visible_area_is_none_without_viewport_area():
    assert ViewportModel((10, 10)).visible_area() is None
    assert ViewportModel((10, 10), (0, 300)).visible_area() is None
    assert ViewportModel((10, 10), (300, 0)).visible_area() is None


def test_visible_area_is_consistent_with_zoom_under_random_operations():
    rng = random.Random(99)
    for _ in range(40):
        image = (rng.uniform(1, 9000), rng.uniform(1, 9000))
        model = ViewportModel(image, (rng.uniform(1, 2500), rng.uniform(1, 2500)))
        for _ in range(60):
            vw, vh = model.viewport_size
            op = rng.choice(("pan", "zoom", "viewport", "fit", "image"))
            if op == "pan":
                model.pan_by(rng.uniform(-4000, 4000), rng.uniform(-4000, 4000))
            elif op == "zoom":
                model.zoom_by(rng.uniform(0.2, 5), (rng.uniform(0, vw), rng.uniform(0, vh)))
            elif op == "viewport":
                model.set_viewport_size(rng.uniform(1, 2500), rng.uniform(1, 2500))
            elif op == "fit":
                model.fit()
            else:
                image = (rng.uniform(1, 9000), rng.uniform(1, 9000))
                model.set_image_size(*image, keep_view=rng.random() < 0.5)
            area = model.visible_area()
            vw, vh = model.viewport_size
            x0, y0, x1, y1 = area.destination
            sx0, sy0, sx1, sy1 = area.source
            assert 0 <= x0 < x1 <= math.floor(vw + 1e-9) or vw < 1
            assert 0 <= y0 < y1 <= math.floor(vh + 1e-9) or vh < 1
            assert 0 <= sx0 <= sx1 <= image[0] + 1e-6 and 0 <= sy0 <= sy1 <= image[1] + 1e-6
            for dest, src, length, rendered in (((x0, x1), (sx0, sx1), image[0], model.rendered_size[0]),
                                                ((y0, y1), (sy0, sy1), image[1], model.rendered_size[1])):
                if src[1] - src[0] < length - 1e-6:  # eje recortado: la escala del recorte es el zoom
                    assert (src[1] - src[0]) * model.zoom == pytest.approx(dest[1] - dest[0], abs=1e-6)
                else:  # eje entero: el destino es el tamaño renderizado redondeado
                    assert abs((dest[1] - dest[0]) - rendered) <= 1
