"""Regresión puntual: 'Tamaño y resolución' debe precargar el DPI REAL de la
imagen (no siempre 300 PPI). Requiere un display (real o xvfb); si no hay
ninguno disponible, el test se salta en vez de fallar la suite.
"""
import time

import pytest
from PIL import Image

pytest.importorskip("customtkinter")

from app.application import build_controller
from config.settings import Settings


def _open_window(tmp_path, dpi):
    try:
        from gui.main_window import MainWindow
    except Exception as exc:  # tkinter sin display disponible
        pytest.skip(f"sin display para probar la GUI: {exc}")

    src = tmp_path / "foto.png"
    Image.new("RGB", (400, 200), "gray").save(src, dpi=(dpi, dpi))

    settings = Settings(output_dir=tmp_path / "resultado")
    controller = build_controller(settings)
    try:
        win = MainWindow(controller=controller, settings=settings)
    except Exception as exc:
        pytest.skip(f"sin display para probar la GUI: {exc}")

    controller.attach_view(win)
    controller.open_image(src)
    deadline = time.time() + 5
    while time.time() < deadline and controller.is_busy:
        win.update()
        time.sleep(0.01)
    win.update()
    return win, controller


@pytest.mark.parametrize("dpi", [72, 150, 300])
def test_dialog_preloads_the_real_image_dpi_not_300(tmp_path, dpi):
    win, controller = _open_window(tmp_path, dpi)
    try:
        before_size = win._snapshot.size
        before_ops = len(win._snapshot.operations)

        win._on_size_resolution()
        win.update()
        dialog = win.winfo_children()[-1]

        shown_dpi = float(dialog._dpi_entry.get())
        assert shown_dpi == pytest.approx(dpi, abs=0.5), (
            f"con imagen a {dpi} PPI, el campo mostró {shown_dpi} PPI"
        )

        # Abrir (y cerrar sin aplicar) el diálogo no debe tocar la imagen.
        dialog.destroy()
        win.update()
        assert win._snapshot.size == before_size
        assert len(win._snapshot.operations) == before_ops
    finally:
        win.destroy()
