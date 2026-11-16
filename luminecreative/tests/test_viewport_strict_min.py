"""Zoom mínimo estricto del visor (opt-in; lo usa Remove con 70 %). Geometría pura, sin Tk."""
import pytest

from gui.viewport import ViewportModel
from gui.viewport_interaction import format_zoom_percent

VIEW = (900, 600)
MIN = 0.70


def strict(image, viewport=VIEW, **kw):
    return ViewportModel(image, viewport, min_zoom=MIN, strict_min_zoom=True, **kw)


@pytest.mark.parametrize(
    "image",
    [(4000, 3000), (3000, 200), (200, 3000), (5000, 5000), (1285, 977), (901, 601), (100000, 10)],
)
def test_fit_never_goes_below_the_minimum_even_when_the_image_does_not_fit(image):
    m = strict(image)
    assert m.fit_zoom >= MIN - 1e-12 and m.zoom >= MIN - 1e-12
    assert m.min_zoom == pytest.approx(MIN)


def test_big_image_fits_at_the_minimum_and_can_be_panned():
    m = strict((4000, 3000))
    assert m.zoom == pytest.approx(MIN) and m.fit_mode
    assert m.fits == (False, False)  # no cabe al 70 %: hay paneo en los dos ejes
    (min_x, max_x), (min_y, max_y) = m.position_bounds
    assert min_x < max_x and min_y < max_y
    assert all(f is not None for f in m.scroll_fractions)  # las barras de desplazamiento aparecen
    before = m.position
    m.pan_by(-120, -80)
    assert m.position != before and m.zoom == pytest.approx(MIN)


def test_in_fit_mode_a_non_fitting_image_starts_centred():
    m = strict((4000, 3000))
    assert m.position == pytest.approx(((900 - 2800) / 2, (600 - 2100) / 2))


def test_wide_image_only_pans_on_the_axis_that_does_not_fit():
    m = strict((3000, 200))  # al 70 %: 2100 × 140 en 900 × 600
    assert m.fits == (False, True)
    assert m.scroll_fractions[0] is not None and m.scroll_fractions[1] is None
    m.pan_by(0, 500)
    assert m.position[1] == pytest.approx((600 - 140) / 2)  # el eje que cabe sigue centrado
    m.pan_by(-300, 0)
    assert m.position[0] == pytest.approx(-300 + (900 - 2100) / 2)


def test_image_that_fits_above_the_minimum_keeps_the_normal_fit():
    m = strict((1000, 300))  # ajuste normal = 0,9 > 0,7
    assert m.zoom == pytest.approx(0.9) and m.fits == (True, True)


def test_small_image_is_not_made_smaller_than_the_fit_and_keeps_the_current_max():
    m = strict((200, 100))
    assert m.zoom == pytest.approx(m.fit_zoom) and m.zoom > 1.0
    assert m.max_zoom == 32.0  # el máximo no cambia


def test_exactly_70_percent_fit_has_no_scroll_and_no_jitter():
    m = strict((1000, 800), (700, 560))  # 700/1000 = 0,7 = 560/800
    assert m.zoom == pytest.approx(0.7) and m.fits == (True, True)
    assert m.scroll_fractions == (None, None)


def test_zoom_out_never_goes_below_the_minimum():
    m = strict((4000, 3000))
    m.set_zoom(2.0)
    for _ in range(40):
        m.zoom_by(0.5)
    assert m.zoom == pytest.approx(MIN)
    m.set_zoom(0.01)
    assert m.zoom == pytest.approx(MIN)
    m.zoom_by(0.0001, anchor=(450, 300))
    assert m.zoom == pytest.approx(MIN)


def test_zoom_in_still_works_up_to_the_unchanged_maximum():
    m = strict((4000, 3000))
    m.zoom_by(2.0)
    assert m.zoom == pytest.approx(1.4) and not m.fit_mode
    m.set_zoom(1000)
    assert m.zoom == m.max_zoom == 32.0


def test_fit_after_manual_zoom_returns_to_max_of_fit_and_minimum():
    m = strict((4000, 3000))
    m.set_zoom(3.0)
    m.fit()
    assert m.fit_mode and m.zoom == pytest.approx(MIN)
    big = strict((4000, 3000), (4000, 3000))
    big.set_zoom(5.0)
    big.fit()
    assert big.zoom == pytest.approx(1.0)  # cabe entera a 100 %: se ajusta a eso, no al mínimo


def test_resizing_the_viewport_in_fit_mode_keeps_the_rule():
    m = strict((4000, 3000))
    m.set_viewport_size(300, 200)
    assert m.zoom == pytest.approx(MIN) and m.fits == (False, False)
    m.set_viewport_size(8000, 6000)
    assert m.zoom == pytest.approx(2.0)


def test_manual_zoom_survives_a_viewport_resize_without_dropping_below_the_minimum():
    m = strict((4000, 3000))
    m.set_zoom(1.0)
    m.set_viewport_size(200, 150)
    assert m.zoom == pytest.approx(1.0)
    m.set_zoom(MIN)
    m.set_viewport_size(5000, 4000)
    assert m.zoom >= MIN - 1e-12


def test_keep_view_with_a_new_image_clamps_to_the_minimum():
    m = strict((4000, 3000))
    m.set_zoom(0.8)
    m.set_image_size(8000, 6000, keep_view=True)
    assert m.zoom >= MIN - 1e-12


def test_the_indicator_reads_70_percent_at_the_minimum():
    m = strict((4000, 3000))
    assert format_zoom_percent(m.zoom, 1.0) == "70 %"


def test_default_model_is_unchanged_by_the_new_option():
    m = ViewportModel((4000, 3000), VIEW)  # visor principal: sin mínimo estricto
    assert m.fit_zoom == pytest.approx(0.2) and m.zoom == pytest.approx(0.2)
    assert m.min_zoom <= 0.2 and m.fits == (True, True)
    m.set_zoom(0.01)
    assert m.zoom == pytest.approx(m.min_zoom) and m.zoom < MIN


@pytest.mark.parametrize("bad", [0, -0.5, float("nan"), float("inf")])
def test_invalid_minimum_is_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        ViewportModel((100, 100), VIEW, min_zoom=bad, strict_min_zoom=True)


@pytest.mark.parametrize("viewport", [(0, 0), (10, 10), (1, 5000), (5000, 1)])
def test_degenerate_viewports_do_not_break_the_rule(viewport):
    m = strict((4000, 3000), viewport)
    assert m.zoom >= MIN - 1e-12
    m.pan_by(50, 50)
    m.zoom_by(0.1)
    assert m.zoom >= MIN - 1e-12
