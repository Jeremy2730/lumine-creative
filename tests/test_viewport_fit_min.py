"""Piso de zoom = zoom de ajuste (opt-in; lo usa Remove). Geometría pura, sin Tk."""
import pytest

from gui.viewport import ViewportModel
from gui.viewport_interaction import ZOOM_STEP_BUTTON

VIEW = (900, 600)


def fit_model(image, viewport=VIEW):
    return ViewportModel(image, viewport, fit_min_zoom=True)


def expected_fit(image, viewport=VIEW):
    return min(viewport[0] / image[0], viewport[1] / image[1])


IMAGES = {
    "horizontal": (6000, 4000),
    "vertical": (4000, 6000),
    "cuadrada": (5000, 5000),
    "pequeña": (100, 80),
    "enorme": (20000, 15000),
    "panorama": (8000, 300),
}


@pytest.mark.parametrize("name", IMAGES)
def test_opens_fitted_whole_image_visible_and_no_fixed_70_percent(name):
    image = IMAGES[name]
    m = fit_model(image)
    assert m.fit_mode and m.zoom == pytest.approx(expected_fit(image))
    assert m.min_zoom == pytest.approx(expected_fit(image))
    assert m.fits == (True, True)  # imagen completa dentro del visor
    assert m.scroll_fractions == (None, None)  # nada que panear aún


@pytest.mark.parametrize("name", IMAGES)
def test_zoom_in_is_progressive_and_zoom_out_never_goes_below_fit(name):
    image = IMAGES[name]
    m = fit_model(image)
    base = m.zoom
    previous = m.zoom
    for _ in range(4):
        m.zoom_by(ZOOM_STEP_BUTTON)
        assert m.zoom > previous
        previous = m.zoom
    for _ in range(60):
        m.zoom_by(1.0 / ZOOM_STEP_BUTTON)
        assert m.zoom >= base - 1e-12
    assert m.zoom == pytest.approx(base)
    assert m.fit_mode and m.fits == (True, True)


def test_zoom_out_goes_down_gradually_to_the_limit():
    m = fit_model((6000, 4000))
    base = m.zoom
    for _ in range(3):
        m.zoom_by(ZOOM_STEP_BUTTON)
    seen = []
    while m.zoom > base * (1 + 1e-9):
        before = m.zoom
        m.zoom_by(1.0 / ZOOM_STEP_BUTTON)
        assert m.zoom < before
        seen.append(m.zoom)
    assert len(seen) == 3 and m.zoom == pytest.approx(base)


@pytest.mark.parametrize("name", IMAGES)
def test_fit_button_restores_the_computed_zoom(name):
    image = IMAGES[name]
    m = fit_model(image)
    base = m.zoom
    for _ in range(5):
        m.zoom_by(ZOOM_STEP_BUTTON, anchor=(100, 100))
    m.pan_by(-50, -50)
    m.fit()
    assert m.zoom == pytest.approx(base) and m.fit_mode and m.fits == (True, True)


def test_pan_works_when_zoomed_image_exceeds_the_visible_area():
    m = fit_model((6000, 4000))
    for _ in range(3):
        m.zoom_by(ZOOM_STEP_BUTTON)
    assert m.fits == (False, False) and all(f is not None for f in m.scroll_fractions)
    before = m.position
    m.pan_by(-40, -30)
    assert m.position != before
    (min_x, max_x), (min_y, max_y) = m.position_bounds
    m.pan_by(-1e6, -1e6)
    assert m.position == pytest.approx((min_x, min_y))  # el paneo respeta los bordes
    m.pan_by(1e6, 1e6)
    assert m.position == pytest.approx((max_x, max_y))


def test_wide_image_pans_only_on_the_axis_that_overflows():
    m = fit_model((8000, 300))
    m.zoom_by(ZOOM_STEP_BUTTON ** 3)
    fits_x, fits_y = m.fits
    assert fits_x is False
    if fits_y:
        assert m.scroll_fractions[1] is None


@pytest.mark.parametrize("image", [(6000, 4000), (4000, 6000), (100, 80)])
def test_limit_is_recalculated_when_the_viewport_changes(image):
    m = fit_model(image)
    for new_view in [(500, 400), (1400, 900), (300, 900), (1200, 200)]:
        m.set_viewport_size(*new_view)
        assert m.min_zoom == pytest.approx(expected_fit(image, new_view))
        assert m.fit_mode and m.zoom == pytest.approx(expected_fit(image, new_view))
        assert m.fits == (True, True)


def test_manual_zoom_below_new_floor_is_raised_when_viewport_grows():
    image = (6000, 4000)
    m = fit_model(image)
    m.zoom_by(ZOOM_STEP_BUTTON ** 2)  # zoom manual por encima del ajuste
    m.set_viewport_size(4000, 2800)  # el visor crece mucho: el nuevo piso supera ese zoom
    assert m.zoom >= expected_fit(image, (4000, 2800)) - 1e-12
    assert m.min_zoom == pytest.approx(expected_fit(image, (4000, 2800)))
    m.zoom_by(0.01)
    assert m.zoom == pytest.approx(expected_fit(image, (4000, 2800)))


def test_viewport_shrink_after_reaching_the_limit_refits_instead_of_cropping():
    image = (6000, 4000)
    m = fit_model(image)
    m.zoom_by(ZOOM_STEP_BUTTON)
    m.zoom_by(1.0 / ZOOM_STEP_BUTTON)  # de vuelta en el límite
    assert m.fit_mode
    m.set_viewport_size(450, 300)
    assert m.zoom == pytest.approx(expected_fit(image, (450, 300))) and m.fits == (True, True)


def test_zoom_in_is_possible_after_the_viewport_changes():
    m = fit_model((6000, 4000))
    m.set_viewport_size(600, 500)
    base = m.zoom
    m.zoom_by(ZOOM_STEP_BUTTON)
    assert m.zoom > base


def test_tiny_image_floor_never_exceeds_max_zoom():
    m = fit_model((10, 10), (900, 600))  # el ajuste (60) supera el máximo (32)
    assert m.min_zoom <= m.max_zoom and m.zoom == pytest.approx(m.max_zoom)
    m.zoom_by(0.5)
    m.zoom_by(2.0)
    assert m.zoom <= m.max_zoom


def test_zero_viewport_is_valid_and_recovers():
    m = fit_model((6000, 4000), (0, 0))
    m.set_viewport_size(900, 600)
    assert m.zoom == pytest.approx(expected_fit((6000, 4000)))


def test_default_and_strict_behaviours_are_unchanged():
    default = ViewportModel((6000, 4000), VIEW)
    assert default.min_zoom == pytest.approx(0.05) or default.min_zoom <= expected_fit((6000, 4000))
    default.zoom_by(0.5)  # el modo por omisión sí puede bajar del ajuste (visor principal)
    assert default.zoom < expected_fit((6000, 4000))
    strict = ViewportModel((6000, 4000), VIEW, min_zoom=0.7, strict_min_zoom=True)
    assert strict.zoom == pytest.approx(0.7)


def test_fit_min_and_strict_are_mutually_exclusive():
    with pytest.raises(ValueError):
        ViewportModel((100, 100), VIEW, strict_min_zoom=True, fit_min_zoom=True)
