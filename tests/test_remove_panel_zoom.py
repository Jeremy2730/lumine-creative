"""Visor de Remove (piso de zoom = ajuste, tablero) frente al visor principal. Necesita Tk (se omite sin pantalla)."""
import time
from types import SimpleNamespace as NS

import customtkinter as ctk
import pytest
from PIL import Image

from gui.panels.image_panel import ImagePanel


@pytest.fixture
def root():
    try:
        window = ctk.CTk()
    except Exception as exc:  # sin display
        pytest.skip(f"sin pantalla: {exc}")
    window.geometry("1000x700+0+0")
    window.update()
    yield window
    window.destroy()


def settle(root):
    end = time.time() + 0.2
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def remove_panel(root, ratio=1.0):
    panel = ImagePanel(root, pixel_ratio=lambda: ratio, fit_min_zoom=True, transparency_checkerboard=True)
    panel.pack(fill="both", expand=True)
    root.update()
    return panel


def percent(panel, ratio=1.0):
    return panel.viewport.zoom * ratio


IMAGES = [(6000, 4000), (4000, 6000), (5000, 5000), (8000, 300), (300, 8000), (100, 80)]


def fit_for(panel):
    w, h = panel._viewport_size()
    iw, ih = panel.viewport.image_size
    return min(w / iw, h / ih)


@pytest.mark.parametrize("size", IMAGES)
@pytest.mark.parametrize("ratio", [1.0, 1.25, 2.0])
def test_opens_fitted_and_zoom_out_stops_at_the_fit(root, size, ratio):
    panel = remove_panel(root, ratio)
    panel.show(Image.new("RGBA", size, (255, 0, 0, 255)))
    settle(root)
    model = panel.viewport
    assert model.fit_mode and model.fits == (True, True)
    assert model.zoom == pytest.approx(min(fit_for(panel), model.max_zoom))
    base = model.zoom
    panel.zoom_in()
    assert panel.viewport.zoom > base
    for _ in range(40):
        panel.zoom_out()
        assert panel.viewport.zoom >= base - 1e-9
    assert panel.viewport.zoom == pytest.approx(base)
    panel.zoom_in()
    panel.fit_to_window()
    assert panel.viewport.zoom == pytest.approx(base) and panel.viewport.fits == (True, True)


def test_pan_works_after_zooming_in(root):
    panel = remove_panel(root)
    panel.show(Image.new("RGBA", (6000, 4000), (0, 0, 0, 255)))
    settle(root)
    for _ in range(3):
        panel.zoom_in()
    model = panel.viewport
    assert model.fits == (False, False)
    before = model.position
    panel.viewport.pan_by(-40, -30)
    assert panel.viewport.position != before


def test_limit_follows_the_viewer_size(root):
    panel = remove_panel(root)
    panel.show(Image.new("RGBA", (6000, 4000), (0, 0, 0, 255)))
    settle(root)
    first = panel.viewport.min_zoom
    root.geometry("500x400+0+0")
    root.update()
    settle(root)
    assert panel.viewport.min_zoom == pytest.approx(fit_for(panel))
    assert panel.viewport.min_zoom != pytest.approx(first)
    assert panel.viewport.fit_mode and panel.viewport.fits == (True, True)


def test_navigation_lock_still_applies_to_the_remove_viewer(root):
    panel = remove_panel(root)
    panel.show(Image.new("RGBA", (6000, 4000), (0, 0, 0, 255)))
    settle(root)
    panel.set_navigation_enabled(zoom=False, pan=False)
    z, p = panel.viewport.zoom, panel.viewport.position
    panel.actual_size()
    panel._on_wheel(NS(x=100, y=100, delta=120, num=0))
    assert (panel.viewport.zoom, panel.viewport.position) == (z, p)
    panel.set_navigation_enabled(zoom=True, pan=True)
    panel.actual_size()
    assert panel.viewport.zoom == pytest.approx(1.0)


def test_main_viewer_defaults_are_unchanged_and_independent_of_remove(root):
    main = ImagePanel(root)
    main.pack(fill="both", expand=True)
    root.update()
    assert main._min_zoom is None and not main._fit_min_zoom and main._model_options() == {}
    main.show(Image.new("RGBA", (6000, 4000), (0, 0, 0, 255)))
    settle(root)
    fit = main.viewport.zoom
    main.zoom_out()
    assert main.viewport.zoom < fit  # el principal sigue pudiendo bajar del ajuste
    other = remove_panel(root)
    other.show(Image.new("RGBA", (6000, 4000), (0, 0, 0, 255)))
    settle(root)
    other.zoom_out()
    assert other.viewport.zoom == pytest.approx(other.viewport.fit_zoom)
    assert main._renderer is not other._renderer and main._renderer.checkerboard is False
    assert other._renderer.checkerboard is True


def test_invalid_options_are_rejected(root):
    for bad in (0, -1):
        with pytest.raises(ValueError):
            ImagePanel(root, min_zoom=bad)
    with pytest.raises(ValueError):
        ImagePanel(root, min_zoom=0.7, fit_min_zoom=True)
