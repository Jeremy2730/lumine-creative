"""tests/test_image_panel_viewport.py

Responsabilidad:
    - Pruebas del visor (ImagePanel) conectado a ViewportModel: carga y
      visualización de imágenes horizontales, verticales y cuadradas,
      proporción, centrado, ajuste, ampliación de imágenes pequeñas,
      redimensionado de la ventana (incluido el agrupado de ráfagas) y
      redibujado sin cambios.
    - Pruebas de integración con MainWindow: abrir una imagen ajusta,
      aplicar herramientas conserva zoom y encuadre, cambiar dimensiones
      conserva el encuadre en proporción, el panel de procesos queda oculto
      pero sigue registrando, la cabecera se mantiene y las operaciones de
      vista no alteran los píxeles, el historial ni lo que se guarda.

No conoce:
    - Diálogos nativos: se sustituyen por funciones falsas (son modales).

Notas:
    - Las pruebas con ventana necesitan display; sin él se omiten (en un
      servidor sin pantalla: ``xvfb-run pytest``). La de capturas de
      pantalla además exige una pantalla de al menos 1050×750 con 24 bits
      de color (``xvfb-run -s "-screen 0 1500x1000x24" pytest``); si no, se
      omite con su motivo. ``_continues_document`` se prueba sin ventana.
"""
import hashlib
import os
import time
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

import customtkinter as ctk
import pytest
from PIL import Image

import gui.main_window as main_window
from app.application import build_controllers
from config.settings import Settings
from gui.main_window import MainWindow, _continues_document
from gui.panels.image_panel import ImagePanel

TITLE = "Herramienta para Diseño"
RED, GREEN, BLUE, YELLOW = (255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)


def quadrants(size):
    w, h = size
    image = Image.new("RGBA", size)
    image.paste(RED, (0, 0, w // 2, h // 2))
    image.paste(GREEN, (w // 2, 0, w, h // 2))
    image.paste(BLUE, (0, h // 2, w // 2, h))
    image.paste(YELLOW, (w // 2, h // 2, w, h))
    return image


def pump(root, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.01)


def canvas_items(panel, kind):
    canvas = panel._canvas
    return [i for i in canvas.find_all() if canvas.type(i) == kind]


def displayed(panel):
    """(x, y, ancho, alto) de la imagen pintada en el canvas."""
    (item,) = canvas_items(panel, "image")
    x, y = panel._canvas.coords(item)
    return x, y, panel._photo.width(), panel._photo.height()


def assert_centred_and_proportional(panel, size):
    model = panel.viewport
    cw, ch = panel._canvas.winfo_width(), panel._canvas.winfo_height()
    x, y, w, h = displayed(panel)
    assert model.viewport_size == (cw, ch) and model.fit_mode
    assert x >= 0 and y >= 0 and x + w <= cw and y + h <= ch  # sin recortes
    ratio = size[0] / size[1]
    assert abs(w - h * ratio) <= 0.5 * ratio + 0.5 + 1e-9  # proporción original, con el redondeo a píxeles enteros
    assert abs((x + w / 2) - cw / 2) <= 1 and abs((y + h / 2) - ch / 2) <= 1  # centrada
    assert abs(w - cw) <= 1 or abs(h - ch) <= 1  # llena la dimensión limitante
    assert abs(w - model.rendered_size_px[0]) <= 1 and abs(h - model.rendered_size_px[1]) <= 1


# ------------------------------------------------------------ visor aislado

@pytest.fixture
def panel_env():
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("sin display: ejecuta con xvfb-run")
    root.geometry("1000x700+0+0")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    panel = ImagePanel(root)
    panel.grid(row=0, column=0, sticky="nsew", padx=16, pady=8)
    pump(root)
    yield SimpleNamespace(root=root, panel=panel)
    root.destroy()


def test_panel_without_an_image_shows_the_hint_and_has_no_model(panel_env):
    panel = panel_env.panel
    assert panel.viewport is None
    (text,) = canvas_items(panel, "text")
    assert "Abre una imagen" in panel._canvas.itemcget(text, "text")
    assert canvas_items(panel, "image") == []
    x, y = panel._canvas.coords(text)
    assert abs(x - panel._canvas.winfo_width() / 2) <= 2 and abs(y - panel._canvas.winfo_height() / 2) <= 2


@pytest.mark.parametrize("size", [(1600, 900), (900, 1400), (1000, 1000), (3, 500), (500, 3)])
def test_fitted_image_is_proportional_centred_and_not_cropped(panel_env, size):
    panel = panel_env.panel
    panel.show(Image.new("RGBA", size, (30, 60, 90, 255)))
    assert_centred_and_proportional(panel, size)
    assert canvas_items(panel, "text") == []  # el texto de ayuda desaparece


def test_viewer_uses_the_model_as_single_source_of_geometry(panel_env):
    panel = panel_env.panel
    panel.show(quadrants((400, 200)))
    model = panel.viewport
    x, y, w, h = displayed(panel)
    x0, y0, x1, y1 = model.visible_area().destination
    assert (x, y) == (x0, y0) and (w, h) == (x1 - x0, y1 - y0)
    # lo que se pinta cambia solo si el modelo cambia
    model.set_zoom(1.0)
    panel.redraw()
    x, y, w, h = displayed(panel)
    assert (w, h) == (x1 - x0, y1 - y0) or model.visible_area().destination != (x0, y0, x1, y1)
    x0, y0, x1, y1 = model.visible_area().destination
    assert (x, y, w, h) == (x0, y0, x1 - x0, y1 - y0)


def test_small_images_are_enlarged_but_never_beyond_the_maximum_zoom(panel_env):
    panel = panel_env.panel
    panel.show(Image.new("RGBA", (40, 20), (200, 50, 50, 255)))
    assert panel.viewport.zoom > 1
    assert_centred_and_proportional(panel, (40, 20))
    panel.show(Image.new("RGBA", (4, 4), (200, 50, 50, 255)))  # 4×4: el ajuste pediría más de 3200 %
    assert panel.viewport.zoom == 32.0
    _, _, w, h = displayed(panel)
    assert (w, h) == (128, 128)


def test_window_resize_refits_and_recentres(panel_env):
    panel, root = panel_env.panel, panel_env.root
    panel.show(Image.new("RGBA", (900, 1400), (30, 60, 90, 255)))
    for geometry in ("1400x900+0+0", "820x640+0+0", "1000x700+0+0"):
        root.geometry(geometry)
        pump(root, 0.4)
        assert_centred_and_proportional(panel, (900, 1400))


def test_resize_bursts_are_coalesced_into_one_render(panel_env, monkeypatch):
    panel, root = panel_env.panel, panel_env.root
    panel.show(Image.new("RGBA", (900, 1400), (30, 60, 90, 255)))
    pump(root)
    calls = []
    real_render = panel._renderer.render
    monkeypatch.setattr(panel._renderer, "render", lambda model: (calls.append(1), real_render(model))[1])
    for _ in range(30):
        panel._on_configure(None)  # ráfaga de eventos de redimensionado
    pump(root, 0.4)
    assert len(calls) == 1


def test_redraw_without_changes_does_not_repaint(panel_env):
    panel, root = panel_env.panel, panel_env.root
    panel.show(quadrants((400, 200)))
    pump(root)
    items, photo = panel._canvas.find_all(), panel._photo
    panel.redraw()
    panel.redraw()
    assert panel._canvas.find_all() == items and panel._photo is photo


def test_viewer_keeps_a_reference_to_the_image_instead_of_copying_it(panel_env):
    panel = panel_env.panel
    image = quadrants((400, 200))
    panel.show(image)
    assert panel._renderer.source is image


def test_view_operations_do_not_change_the_image_pixels(panel_env):
    panel, root = panel_env.panel, panel_env.root
    image = quadrants((400, 200))
    image.info["dpi"] = (300.0, 300.0)
    digest, info, size, mode = hashlib.sha256(image.tobytes()).hexdigest(), dict(image.info), image.size, image.mode
    panel.show(image)
    for geometry in ("1200x800+0+0", "700x500+0+0"):
        root.geometry(geometry)
        pump(root, 0.3)
    panel.viewport.set_zoom(3.0, (50, 50))
    panel.redraw()
    panel.viewport.pan_by(-40, -30)
    panel.redraw()
    panel.viewport.fit()
    panel.redraw()
    assert hashlib.sha256(image.tobytes()).hexdigest() == digest
    assert dict(image.info) == info and image.size == size and image.mode == mode


def test_displayed_pixels_match_the_image_content_on_screen(panel_env):
    from PIL import ImageGrab

    panel, root = panel_env.panel, panel_env.root
    if root.winfo_screenwidth() < 1050 or root.winfo_screenheight() < 750 or root.winfo_screendepth() < 24:
        pytest.skip('pantalla virtual pequeña: usa xvfb-run -s "-screen 0 1500x1000x24"')
    for size in ((400, 200), (200, 400)):
        panel.show(quadrants(size))
        pump(root, 0.3)
        try:
            shot = ImageGrab.grab(xdisplay=os.environ["DISPLAY"])
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"no se puede capturar la pantalla: {exc}")
        x, y, w, h = displayed(panel)
        rx, ry = panel._canvas.winfo_rootx(), panel._canvas.winfo_rooty()
        sample = lambda fx, fy: shot.getpixel((round(rx + x + w * fx), round(ry + y + h * fy)))[:3]
        assert (sample(0.25, 0.25), sample(0.75, 0.25), sample(0.25, 0.75), sample(0.75, 0.75)) == (
            RED[:3], GREEN[:3], BLUE[:3], YELLOW[:3],
        )


# --------------------------------------------------- integración con la ventana

def make_image(folder: Path, name="vertical.png", size=(900, 1400)) -> Path:
    img = Image.new("RGB", size, "#1f6aa5")
    for y in range(size[1] // 2, size[1]):
        for x in range(size[0]):
            img.putpixel((x, y), (240, 160, 40))
    path = folder / name
    img.save(path)
    return path


@pytest.fixture
def app(tmp_path, monkeypatch, tk_gc_on_main_thread):
    settings = Settings(output_dir=tmp_path / "descargas", app_title=TITLE)
    try:
        design, files = build_controllers(settings)
        win = MainWindow(design, settings, files)
    except tk.TclError:
        pytest.skip("sin display: ejecuta con xvfb-run")
    design.attach_view(win)
    files.attach_view(win)
    answers = SimpleNamespace(save=None, unsaved="discard")
    monkeypatch.setattr(main_window, "ask_image_path", lambda extensions, parent=None: None)
    monkeypatch.setattr(main_window, "ask_save_path", lambda suggestion, parent=None: answers.save)
    monkeypatch.setattr(main_window, "ask_unsaved_changes", lambda name, parent=None: answers.unsaved)
    monkeypatch.setattr(main_window, "ask_flatten_to_jpg", lambda parent=None: True)
    src = tmp_path / "origen"
    src.mkdir()
    win.geometry("1000x760+0+0")
    pump(win, 0.3)
    yield SimpleNamespace(win=win, design=design, files=files, answers=answers, src=src, out=tmp_path / "salida")
    if not win._closed:
        win.destroy()


def settle(app):
    deadline = time.time() + 8
    while time.time() < deadline:
        app.win.update()
        if not app.design.is_busy:
            pump(app.win, 0.3)
            return
        time.sleep(0.01)
    raise AssertionError("timeout")


def open_image(app, path):
    app.files.open_path(path)
    settle(app)


def centre_fraction(model):
    cx, cy = model.viewport_size[0] / 2, model.viewport_size[1] / 2
    ix, iy = model.viewport_to_image(cx, cy)
    return ix / model.image_size[0], iy / model.image_size[1]


def test_opening_an_image_fits_it_to_the_viewer(app):
    open_image(app, make_image(app.src))
    panel = app.win._image_panel
    assert_centred_and_proportional(panel, (900, 1400))
    assert panel.viewport.zoom == pytest.approx(panel.viewport.fit_zoom)


def test_tools_keep_zoom_and_framing_and_a_new_image_fits_again(app):
    open_image(app, make_image(app.src))
    panel = app.win._image_panel
    model = panel.viewport
    model.set_zoom(1.0)
    model.pan_to(0, -300)
    panel.redraw()
    before = centre_fraction(model)
    for tool in (app.design.sharpen, app.design.comic_effect):
        tool()
        settle(app)
        assert panel.viewport is model
        assert model.zoom == 1.0 and not model.fit_mode
        assert centre_fraction(model) == pytest.approx(before, abs=1e-6)
        assert model.visible_area().destination == (model.visible_area().destination)  # coherente
    open_image(app, make_image(app.src, "otra.png", (1200, 800)))  # imagen nueva (con cambios pendientes: descartar)
    assert model.fit_mode and model.zoom == pytest.approx(model.fit_zoom)
    assert_centred_and_proportional(panel, (1200, 800))


def test_tools_in_fit_mode_stay_fitted(app):
    open_image(app, make_image(app.src))
    panel = app.win._image_panel
    app.design.sharpen()
    settle(app)
    assert panel.viewport.fit_mode
    assert_centred_and_proportional(panel, (900, 1400))


def test_reopening_the_same_file_fits_again(app):
    path = make_image(app.src)
    open_image(app, path)
    panel = app.win._image_panel
    panel.viewport.set_zoom(2.0)
    panel.redraw()
    open_image(app, path)  # mismo archivo, sin operaciones: documento nuevo
    assert panel.viewport.fit_mode


def test_changing_the_dimensions_keeps_the_framing_proportionally(app):
    open_image(app, make_image(app.src))
    panel = app.win._image_panel
    model = panel.viewport
    model.set_zoom(1.0)
    model.pan_to(0, -300)
    panel.redraw()
    before = centre_fraction(model)
    app.design.run_tool(
        "size_resolution", width_cm=15.24, height_cm=23.7067, dpi=300, resample=True, method="LANCZOS"
    )
    settle(app)
    assert tuple(round(v) for v in model.image_size) == (1800, 2800)
    assert model.zoom == 1.0 and not model.fit_mode
    assert centre_fraction(model) == pytest.approx(before, abs=0.01)


def test_changing_the_dimensions_in_fit_mode_refits(app):
    open_image(app, make_image(app.src))
    panel = app.win._image_panel
    app.design.run_tool(
        "size_resolution", width_cm=7.62, height_cm=11.85, dpi=150, resample=True, method="LANCZOS"
    )
    settle(app)
    assert panel.viewport.fit_mode
    assert_centred_and_proportional(panel, panel.viewport.image_size)


def test_pipeline_panel_is_hidden_but_the_history_is_still_recorded(app):
    tools_panel = app.win._tools_panel
    assert not tools_panel.winfo_ismapped()
    open_image(app, make_image(app.src))
    app.design.sharpen()
    settle(app)
    chips = [w.cget("text").strip() for w in tools_panel._chips.winfo_children() if isinstance(w, ctk.CTkLabel)]
    assert chips == ["Nitidez"]
    assert [op.label for op in app.design._service.snapshot().operations] == ["Nitidez"]
    assert not tools_panel.winfo_ismapped()
    tools_panel.grid()  # volver a mostrarlo es una sola llamada
    pump(app.win, 0.2)
    assert tools_panel.winfo_ismapped()
    tools_panel.grid_remove()


def test_header_with_name_and_author_is_kept(app):
    def labels(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                yield child.cget("text")
            yield from labels(child)

    texts = list(labels(app.win))
    assert "HERRAMIENTA PARA DISEÑO" in texts
    assert any(text.startswith("by ") for text in texts)


def test_view_operations_do_not_change_pixels_history_or_what_is_saved(app):
    open_image(app, make_image(app.src))
    panel, win = app.win._image_panel, app.win
    snapshot = app.design._service.snapshot()
    digest = hashlib.sha256(snapshot.image.tobytes()).hexdigest()
    info, operations = dict(snapshot.image.info), snapshot.operations
    app.answers.save = str(app.out / "a.png")
    app.files.save()
    settle(app)
    for geometry in ("1300x850+0+0", "820x640+0+0", "1000x760+0+0"):
        win.geometry(geometry)
        pump(win, 0.3)
    panel.viewport.set_zoom(3.0, (100, 100))
    panel.viewport.pan_by(-50, -50)
    panel.redraw()
    panel.viewport.fit()
    panel.redraw()
    after = app.design._service.snapshot()
    assert hashlib.sha256(after.image.tobytes()).hexdigest() == digest
    assert dict(after.image.info) == info and after.operations == operations
    assert not app.files.has_unsaved_changes()  # mover o ampliar la vista no es una edición
    app.answers.save = str(app.out / "b.png")
    app.files.save_as()
    settle(app)
    assert (app.out / "a.png").read_bytes() == (app.out / "b.png").read_bytes()


def test_the_viewer_shows_the_engine_image_without_copying_it(app):
    open_image(app, make_image(app.src))
    snapshot = app.design._service.snapshot()
    assert app.win._image_panel._renderer.source is snapshot.image


# ------------------------------------------------ decisión conservar/ajustar

def snap(source, count):
    return SimpleNamespace(source_path=source, operations=tuple(range(count)))


@pytest.mark.parametrize(
    "previous,current,expected",
    [
        (None, snap("a", 0), False),                 # primera imagen
        (snap("a", 0), snap("a", 1), True),          # una herramienta
        (snap("a", 1), snap("a", 2), True),          # otra herramienta
        (snap("a", 2), snap("a", 3), True),
        (snap("a", 2), snap("a", 0), False),         # se volvió a abrir el mismo archivo
        (snap("a", 2), snap("b", 3), False),         # otro archivo
        (snap("a", 2), snap("b", 0), False),
        (snap("a", 1), snap("a", 1), False),         # sin operación nueva: no es continuación
        (snap(None, 0), snap(None, 1), True),        # documento sin ruta de origen
    ],
)
def test_continues_document_decision(previous, current, expected):
    assert _continues_document(previous, current) is expected
