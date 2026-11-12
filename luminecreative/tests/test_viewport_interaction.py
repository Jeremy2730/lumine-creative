"""tests/test_viewport_interaction.py

Responsabilidad:
    - Pruebas unitarias de gui/viewport_interaction.py (sin ventana) y de la
      aritmética del visor interactivo sobre ViewportModel: zoom con rueda
      anclado al cursor, límites de zoom, paneo con límites, botón ajustar,
      100 % con distintas escalas de pantalla, redimensionado en modo ajustar
      y en zoom manual, barras de desplazamiento ↔ posición.

No conoce:
    - Ventanas, widgets ni eventos reales; no requiere display.
"""
import hashlib
import math
import subprocess
import sys
from pathlib import Path

import pytest

from gui.viewport import ViewportModel
from gui.viewport_interaction import (
    ZOOM_STEP_BUTTON,
    ZOOM_STEP_WHEEL,
    actual_size_zoom,
    format_zoom_percent,
    parse_scroll_command,
    physical_per_canvas_pixel,
    wheel_notches,
    wheel_zoom_factor,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def under(model, point):
    return model.viewport_to_image(*point)


# ------------------------------------------------------------------ rueda
@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"delta": 120}, 1.0), ({"delta": -120}, -1.0), ({"delta": 240}, 2.0),
        ({"delta": 30}, 0.25), ({"delta": 0}, 0.0),
        ({"num": 4}, 1.0), ({"num": 5}, -1.0), ({"num": 1}, 0.0),
    ],
)
def test_wheel_notches_windows_and_linux(kwargs, expected):
    assert wheel_notches(**kwargs) == pytest.approx(expected)


def test_wheel_zoom_in_and_out_cancel_exactly():
    assert wheel_zoom_factor(1) == pytest.approx(ZOOM_STEP_WHEEL)
    assert wheel_zoom_factor(1) * wheel_zoom_factor(-1) == pytest.approx(1.0)
    assert wheel_zoom_factor(0) == 1.0
    assert wheel_zoom_factor(2) == pytest.approx(ZOOM_STEP_WHEEL**2)


def test_wheel_zoom_in_and_out_change_the_zoom_in_the_right_direction():
    model = ViewportModel((2000, 1500), (800, 600))
    start = model.zoom
    model.zoom_by(wheel_zoom_factor(wheel_notches(delta=120)), (400, 300))
    assert model.zoom > start
    model.zoom_by(wheel_zoom_factor(wheel_notches(delta=-120)), (400, 300))
    assert model.zoom == pytest.approx(start)


@pytest.mark.parametrize("cursor", [(0, 0), (400, 300), (123, 457), (799, 599), (10, 590)])
def test_wheel_zoom_keeps_the_point_under_the_cursor(cursor):
    model = ViewportModel((4000, 3000), (800, 600))
    model.set_zoom(0.5, (400, 300))
    model.pan_by(-300, -200)
    for notches in (1, 1, 1, -1, 2, -3, 1):
        anchor_before = under(model, cursor)
        model.zoom_by(wheel_zoom_factor(notches), cursor)
        assert under(model, cursor) == pytest.approx(anchor_before, abs=1e-6)


def test_wheel_zoom_does_not_jump_in_small_steps():
    """Cada paso mueve la imagen exactamente lo que exige el anclaje: (f − 1) · distancia al cursor."""
    model = ViewportModel((4000, 3000), (800, 600))
    model.set_zoom(1.0)
    cursor = (333, 222)
    factor = wheel_zoom_factor(0.25)
    for _ in range(40):
        before = model.position
        zoom_before = model.zoom
        model.zoom_by(factor, cursor)
        bound = abs(model.zoom / zoom_before - 1) * math.dist(before, cursor)
        assert math.dist(before, model.position) <= bound + 1e-6


def test_zoom_respects_min_and_max_limits():
    model = ViewportModel((2000, 1500), (800, 600), min_zoom=0.1, max_zoom=8.0)
    for _ in range(200):
        model.zoom_by(wheel_zoom_factor(1), (100, 100))
    assert model.zoom == 8.0
    snapshot = (model.zoom, model.position)
    model.zoom_by(wheel_zoom_factor(1), (100, 100))
    assert (model.zoom, model.position) == snapshot  # ya en el máximo: nada cambia
    for _ in range(400):
        model.zoom_by(wheel_zoom_factor(-1), (100, 100))
    assert model.zoom == pytest.approx(model.min_zoom)
    assert model.zoom <= 0.1 + 1e-12


def test_zoom_never_changes_image_size_or_proportions():
    model = ViewportModel((1234, 777), (800, 600))
    for f in (1.7, 0.3, 5.0, 0.01):
        model.zoom_by(f, (50, 80))
        assert model.image_size == (1234, 777)
        assert model.rendered_size[0] / model.rendered_size[1] == pytest.approx(1234 / 777)


# ------------------------------------------------------------------ paneo
def test_pan_horizontal_and_vertical_move_the_image():
    model = ViewportModel((4000, 3000), (800, 600))
    model.set_zoom(1.0)
    x, y = model.position
    model.pan_by(25, 0)
    assert model.position == (x + 25, y)
    model.pan_by(0, -40)
    assert model.position == (x + 25, y - 40)


def test_pan_respects_the_bounds_and_does_not_lose_the_image():
    model = ViewportModel((4000, 3000), (800, 600))
    model.set_zoom(1.0)
    model.pan_by(10**6, 10**6)
    assert model.position == (0.0, 0.0)
    model.pan_by(-10**6, -10**6)
    assert model.position == (800 - 4000, 600 - 3000)


def test_pan_keeps_a_fitting_axis_centred():
    model = ViewportModel((4000, 300), (800, 600))
    model.set_zoom(1.0)
    centred_y = (600 - 300) / 2
    model.pan_by(-100, 77)
    assert model.position[1] == centred_y
    assert model.position[0] == -100 + model.position_bounds[0][1] or model.position[0] < 0


def test_absolute_drag_does_not_drift_over_long_movements():
    """El panel coloca la imagen en origen + desplazamiento total, no suma deltas."""
    model = ViewportModel((20000, 20000), (800, 600))
    model.set_zoom(1.0)
    origin = model.position
    mouse0 = (400.0, 300.0)
    for step in range(1, 5001):
        mouse = (mouse0[0] + 0.1 * math.sin(step) + step * 0.01, mouse0[1] - step * 0.02)
        tx, ty = origin[0] + (mouse[0] - mouse0[0]), origin[1] + (mouse[1] - mouse0[1])
        model.pan_by(tx - model.position[0], ty - model.position[1])
    assert model.position[0] == pytest.approx(origin[0] + 50 + 0.1 * math.sin(5000), abs=1e-6)
    assert model.position[1] == pytest.approx(origin[1] - 100, abs=1e-6)


# ------------------------------------------------- ajustar / 100 % / escala
def test_fit_returns_to_the_whole_image_and_fit_mode():
    model = ViewportModel((2000, 1000), (800, 600))
    fit_zoom = model.zoom
    model.zoom_by(4.0, (10, 10))
    model.pan_by(-50, -50)
    assert not model.fit_mode
    model.fit()
    assert model.fit_mode and model.zoom == pytest.approx(fit_zoom)
    assert model.scroll_fractions == (None, None)


@pytest.mark.parametrize("ratio, expected", [(1.0, 1.0), (1.25, 0.8), (1.5, 1 / 1.5), (2.0, 0.5)])
def test_actual_size_zoom_depends_on_the_physical_per_canvas_pixel_ratio(ratio, expected):
    assert actual_size_zoom(ratio) == pytest.approx(expected)


@pytest.mark.parametrize("bad", [0, -1.0, None])
def test_actual_size_zoom_ignores_invalid_ratios(bad):
    assert actual_size_zoom(bad) == 1.0


@pytest.mark.parametrize("ratio", [1.0, 1.5, 2.0])
def test_actual_size_is_one_physical_pixel_per_image_pixel(ratio):
    model = ViewportModel((4000, 3000), (800, 600))
    model.set_zoom(actual_size_zoom(ratio))
    assert model.zoom * ratio == pytest.approx(1.0)
    assert format_zoom_percent(model.zoom, ratio) == "100 %"


def test_default_ratio_is_one_outside_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert physical_per_canvas_pixel() == 1.0


def test_ratio_detection_never_raises_on_windows_without_win_api(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    assert physical_per_canvas_pixel() == 1.0  # ctypes.windll no existe aquí → 1,0


@pytest.mark.parametrize(
    "zoom, text", [(1.0, "100 %"), (0.375, "38 %"), (0.05, "5.0 %"), (32.0, "3200 %"), (0.0999, "10 %")]
)
def test_zoom_percent_text(zoom, text):
    assert format_zoom_percent(zoom) == text


def test_button_steps_are_inverse_of_each_other():
    model = ViewportModel((2000, 1500), (800, 600))
    model.set_zoom(1.0)
    model.zoom_by(ZOOM_STEP_BUTTON)
    model.zoom_by(1.0 / ZOOM_STEP_BUTTON)
    assert model.zoom == pytest.approx(1.0)


# ------------------------------------------------- órdenes de las barras
@pytest.mark.parametrize(
    "args, expected",
    [
        (("moveto", "0.25"), ("moveto", 0.25)), (("moveto", 1), ("moveto", 1.0)),
        (("scroll", "1", "units"), ("units", 1.0)), (("scroll", "-2", "pages"), ("pages", -2.0)),
        (("scroll", "1", "bogus"), None), (("moveto",), None), (("moveto", "abc"), None), ((), None),
    ],
)
def test_parse_scroll_command(args, expected):
    assert parse_scroll_command(args) == expected


def test_scrollbar_moveto_and_fractions_are_consistent_after_zoom_and_pan():
    model = ViewportModel((6000, 4000), (900, 600))
    model.zoom_by(5.0, (450, 300))
    for step in range(30):
        model.pan_by(-37, 21)
        for axis in (0, 1):
            first, last = model.scroll_fractions[axis]
            span = last - first
            model.scroll_to_fraction(axis, first)  # reaplicar lo que muestra la barra no mueve nada
            assert model.scroll_fractions[axis] == pytest.approx((first, last))
            assert span == pytest.approx(model.viewport_size[axis] / model.rendered_size[axis])


def test_scrollbars_become_inactive_when_the_image_fits_and_active_when_zoomed():
    model = ViewportModel((2000, 1500), (800, 600))
    assert model.scroll_fractions == (None, None)  # ajustada
    model.zoom_by(3.0)
    assert None not in model.scroll_fractions
    model.fit()
    assert model.scroll_fractions == (None, None)


def test_scrollbar_page_and_unit_commands_translate_to_pan():
    model = ViewportModel((6000, 4000), (900, 600))
    model.set_zoom(1.0)
    model.pan_to(0, 0)
    kind, value = parse_scroll_command(("scroll", "1", "units"))
    model.pan_by(-value * 40, 0)
    assert model.position[0] == -40
    kind, value = parse_scroll_command(("scroll", "1", "pages"))
    model.pan_by(-value * 0.9 * model.viewport_size[0], 0)
    assert model.position[0] == pytest.approx(-40 - 810)


# ------------------------------------------------- redimensionado
def test_resize_in_fit_mode_refits_and_centres():
    model = ViewportModel((2000, 1000), (800, 600))
    model.set_viewport_size(1200, 500)
    assert model.fit_mode and model.zoom == pytest.approx(0.5)
    rw, rh = model.rendered_size
    assert model.position == pytest.approx(((1200 - rw) / 2, (500 - rh) / 2))


def test_resize_in_manual_zoom_keeps_zoom_and_the_central_image_point():
    model = ViewportModel((4000, 3000), (800, 600))
    model.set_zoom(1.0, (400, 300))
    model.pan_by(-500, -300)
    centre = model.viewport_to_image(400, 300)
    zoom = model.zoom
    model.set_viewport_size(1000, 700)
    assert model.zoom == zoom and not model.fit_mode
    assert model.viewport_to_image(500, 350) == pytest.approx(centre, abs=1e-6)


# ------------------------------------------------- independencia
def test_interaction_module_does_not_import_the_gui_or_pillow():
    code = (
        "import sys; import gui.viewport_interaction; "
        "bad = [m for m in ('tkinter', 'customtkinter', 'PIL', 'numpy') if m in sys.modules]; "
        "print(bad); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_view_math_does_not_touch_pixel_data_properties():
    """El modelo solo maneja tamaños: tras cualquier secuencia el tamaño original es el mismo."""
    model = ViewportModel((640, 480), (300, 200))
    digest = hashlib.sha256(repr(model.image_size).encode()).hexdigest()
    for f in (3.0, 0.2, 1.1):
        model.zoom_by(f, (10, 10))
        model.pan_by(-5, 5)
    model.fit()
    assert hashlib.sha256(repr(model.image_size).encode()).hexdigest() == digest
