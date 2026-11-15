"""Visor de Remove (zoom mínimo 70 %, tablero) frente al visor principal. Necesita Tk (se omite sin pantalla)."""
import time
from types import SimpleNamespace as NS

import customtkinter as ctk
import pytest
from PIL import Image

from gui.panels.image_panel import ImagePanel
from tools.remove.dialog import MIN_ZOOM


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
    panel = ImagePanel(root, pixel_ratio=lambda: ratio, min_zoom=MIN_ZOOM, transparency_checkerboard=True)
    panel.pack(fill="both", expand=True)
    root.update()
    return panel


def percent(panel, ratio=1.0):
    return panel.viewport.zoom * ratio


IMAGES = [(6000, 4000), (4000, 6000), (5000, 5000), (8000, 300), (300, 8000), (100, 80)]


@pytest.mark.parametrize("size", IMAGES)
@pytest.mark.parametrize("ratio", [1.0, 1.25, 2.0])
def test_fit_and_zoom_out_never_go_below_70_percent(root, size, ratio):
    panel = remove_panel(root, ratio)
    panel.show(Image.new("RGBA", size, (255, 0, 0, 255)))
    settle(root)
    assert percent(panel, ratio) >= MIN_ZOOM - 1e-9
    for _ in range(30):
        panel.zoom_out()
    assert percent(panel, ratio) == pytest.approx(MIN_ZOOM) or percent(panel, ratio) > MIN_ZOOM
    panel.fit_to_window()
    assert percent(panel, ratio) >= MIN_ZOOM - 1e-9


def test_a_large_image_is_fitted_at_70_and_can_be_panned(root):
    panel = remove_panel(root)
    panel.show(Image.new("RGBA", (6000, 4000), (0, 0, 0, 255)))
    settle(root)
    model = panel.viewport
    assert model.zoom == pytest.approx(MIN_ZOOM) and model.fit_mode and model.fits == (False, False)
    before = model.position
    panel._on_wheel(NS(x=100, y=100, delta=120, num=0))  # acercar y seguir moviendo
    panel.viewport.pan_by(-40, -30)
    assert panel.viewport.position != before


def test_zoom_out_is_a_noop_at_the_minimum_and_zoom_in_still_works(root):
    panel = remove_panel(root)
    panel.show(Image.new("RGBA", (6000, 4000), (0, 0, 0, 255)))
    settle(root)
    panel.zoom_out()
    assert panel.viewport.zoom == pytest.approx(MIN_ZOOM)
    panel.zoom_in()
    assert panel.viewport.zoom > MIN_ZOOM
    panel.actual_size()
    assert panel.viewport.zoom == pytest.approx(1.0)
    panel.fit_to_window()
    assert panel.viewport.zoom == pytest.approx(MIN_ZOOM)


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
    assert main._min_zoom is None and main._model_options() == {}
    main.show(Image.new("RGBA", (6000, 4000), (0, 0, 0, 255)))
    settle(root)
    assert main.viewport.zoom < MIN_ZOOM and main.viewport.fit_mode  # el principal sigue ajustando a < 70 %
    other = remove_panel(root)
    other.show(Image.new("RGBA", (6000, 4000), (0, 0, 0, 255)))
    settle(root)
    assert other.viewport.zoom == pytest.approx(MIN_ZOOM) and main.viewport.zoom < MIN_ZOOM
    assert main._renderer is not other._renderer and main._renderer.checkerboard is False
    assert other._renderer.checkerboard is True


def test_invalid_min_zoom_is_rejected(root):
    for bad in (0, -1):
        with pytest.raises(ValueError):
            ImagePanel(root, min_zoom=bad)
