"""tests/test_image_panel_interaction.py

Responsabilidad:
    - Pruebas de integración de la interacción del visor (ImagePanel, fase 1):
      zoom con la rueda anclado al cursor y sus límites, paneo (botón central,
      espacio + botón izquierdo) con límites y centrado, controles (acercar,
      alejar, ajustar, 100 % con distintas escalas de pantalla, porcentaje),
      barras de desplazamiento sincronizadas con el modelo y su ocultación,
      redimensionado en modo ajustar y en zoom manual, conservación del
      encuadre, agrupado de eventos rápidos sin repintados redundantes,
      destrucción con callbacks pendientes, tiempos de render y ausencia de
      cambios en la imagen mostrada.

No conoce:
    - Cómo se calcula la geometría (eso se prueba en test_viewport*.py).

Notas:
    - Los eventos se simulan llamando a los manejadores del panel con
      objetos que imitan al evento de Tk (x, y, delta, num); que los
      manejadores estén enlazados a la secuencia correcta se comprueba con
      ``canvas.bind()``.
    - Necesitan display; sin él se omiten (``xvfb-run pytest``).
"""
import hashlib
import time
import tkinter as tk
from types import SimpleNamespace

import customtkinter as ctk
import pytest
from PIL import Image

from gui.panels.image_panel import ImagePanel

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


def ev(x=0, y=0, delta=0, num=0):
    return SimpleNamespace(x=x, y=y, delta=delta, num=num)


def make_env(ratio=1.0):
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("sin display: ejecuta con xvfb-run")
    root.geometry("1000x700+0+0")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    errors = []
    root.report_callback_exception = lambda *exc: errors.append(exc)
    panel = ImagePanel(root, pixel_ratio=lambda: ratio)
    panel.grid(row=0, column=0, sticky="nsew", padx=16, pady=8)
    pump(root)
    return SimpleNamespace(root=root, panel=panel, errors=errors)


@pytest.fixture
def env():
    e = make_env()
    yield e
    try:
        e.root.destroy()
    except tk.TclError:
        pass
    assert e.errors == []


@pytest.fixture
def big(env):
    """Imagen grande ya mostrada y asentada."""
    env.image = quadrants((3000, 2000))
    env.panel.show(env.image)
    pump(env.root, 0.2)
    return env


def count_pixel_renders(panel, monkeypatch):
    calls = []
    real = panel._renderer.render
    monkeypatch.setattr(panel._renderer, "render", lambda model: (calls.append(1), real(model))[1])
    return calls


def centre(panel):
    w, h = panel.viewport.viewport_size
    return w / 2, h / 2


# ------------------------------------------------------------------ enlaces
def test_events_are_bound_on_the_canvas(env):
    bound = set(env.panel._canvas.bind())
    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>", "<ButtonPress-2>", "<B2-Motion>",
                     "<ButtonRelease-2>", "<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>",
                     "<KeyPress-space>", "<KeyRelease-space>", "<Configure>"):
        assert sequence in bound, sequence


def test_controls_are_disabled_and_scrollbars_hidden_without_an_image(env):
    panel = env.panel
    for button in panel._buttons:
        assert button.cget("state") == "disabled"
    assert panel._hbar.winfo_manager() == "" and panel._vbar.winfo_manager() == ""
    panel._on_wheel(ev(10, 10, delta=120))  # sin imagen: no falla ni hace nada
    panel.zoom_in()
    assert panel._frame_job is None


# --------------------------------------------------------------------- zoom
def test_wheel_zoom_in_then_out_returns_to_the_same_zoom(big):
    panel, model = big.panel, big.panel.viewport
    start = model.zoom
    panel._on_wheel(ev(300, 200, delta=120))
    assert model.zoom > start and not model.fit_mode
    panel._on_wheel(ev(300, 200, delta=-120))
    assert model.zoom == pytest.approx(start)


def test_wheel_zoom_anchor_is_exact_once_the_image_overflows_the_viewport(big):
    panel, model = big.panel, big.panel.viewport
    panel.actual_size()
    pump(big.root, 0.1)
    cx, cy = 250, 180
    for delta in (120, 120, -120, 240, -360, 120):
        before = model.viewport_to_image(cx, cy)
        panel._on_wheel(ev(cx, cy, delta=delta))
        assert model.viewport_to_image(cx, cy) == pytest.approx(before, abs=1e-6)


def test_wheel_events_from_linux_zoom_in_and_out(big):
    panel, model = big.panel, big.panel.viewport
    start = model.zoom
    panel._on_wheel(ev(100, 100, num=4))
    assert model.zoom > start
    panel._on_wheel(ev(100, 100, num=5))
    assert model.zoom == pytest.approx(start)


def test_zoom_stops_at_max_and_min_without_scheduling_work(big):
    panel, model = big.panel, big.panel.viewport
    for _ in range(300):
        panel._on_wheel(ev(100, 100, delta=120))
    assert model.zoom == model.max_zoom
    pump(big.root, 0.1)
    assert panel._frame_job is None
    panel._on_wheel(ev(100, 100, delta=120))  # ya en el máximo
    assert panel._frame_job is None
    assert panel._zoom_in_button.cget("state") == "disabled"
    for _ in range(600):
        panel._on_wheel(ev(100, 100, delta=-120))
    assert model.zoom == pytest.approx(model.min_zoom)
    pump(big.root, 0.1)
    panel._on_wheel(ev(100, 100, delta=-120))
    assert panel._frame_job is None
    assert panel._zoom_out_button.cget("state") == "disabled"


# ------------------------------------------------------------------- paneo
def zoomed(env):
    env.panel.actual_size()
    pump(env.root, 0.1)
    return env.panel, env.panel.viewport


def test_middle_button_drag_pans_horizontally_and_vertically(big):
    panel, model = zoomed(big)
    x, y = model.position
    panel._begin_pan(ev(300, 300), 2)
    panel._move_pan(ev(260, 300), 2)
    assert model.position == (x - 40, y)
    panel._move_pan(ev(260, 330), 2)
    assert model.position == (x - 40, y + 30)
    panel._finish_pan(2)
    panel._move_pan(ev(0, 0), 2)  # tras soltar ya no mueve
    assert model.position == (x - 40, y + 30)


def test_space_plus_left_button_pans_but_left_button_alone_does_not(big):
    panel, model = zoomed(big)
    start = model.position
    panel._on_left_press(ev(200, 200))
    panel._move_pan(ev(150, 150), 1)
    assert model.position == start  # sin espacio no hay paneo
    panel._finish_pan(1)
    panel._on_space_press(ev())
    panel._on_left_press(ev(200, 200))
    panel._move_pan(ev(150, 170), 1)
    assert model.position == (start[0] - 50, start[1] - 30)
    panel._finish_pan(1)
    panel._on_space_release(ev())
    assert not panel._space_down


def test_pan_is_limited_by_the_model_bounds_and_follows_the_mouse_when_it_returns(big):
    panel, model = zoomed(big)
    (min_x, max_x), (min_y, max_y) = model.position_bounds
    start = model.position
    panel._begin_pan(ev(400, 300), 2)
    panel._move_pan(ev(400 + 10_000, 300 + 10_000), 2)
    assert model.position == (max_x, max_y)
    panel._move_pan(ev(400 - 10_000, 300 - 10_000), 2)
    assert model.position == (min_x, min_y)
    panel._move_pan(ev(400, 300), 2)  # vuelve al punto de partida: la imagen vuelve a su sitio exacto
    assert model.position == pytest.approx(start)
    panel._finish_pan(2)


def test_pan_keeps_a_fitting_axis_centred(env):
    panel = env.panel
    panel.show(quadrants((6000, 200)))  # muy apaisada
    pump(env.root, 0.2)
    panel.actual_size()
    pump(env.root, 0.1)
    model = panel.viewport
    assert model.fits == (False, True)
    centred_y = model.position[1]
    panel._begin_pan(ev(300, 300), 2)
    panel._move_pan(ev(200, 100), 2)
    assert model.position[1] == centred_y
    assert model.position[0] < 0
    panel._finish_pan(2)


def test_long_drag_does_not_accumulate_error(big):
    panel, model = zoomed(big)
    start = model.position
    panel._begin_pan(ev(400, 300), 2)
    for step in range(2000):
        panel._move_pan(ev(400 + (step % 7), 300 - (step % 5)), 2)
    panel._move_pan(ev(400, 300), 2)
    assert model.position == pytest.approx(start)
    panel._finish_pan(2)


def test_focus_loss_releases_space_and_the_drag(big):
    panel, _ = zoomed(big)
    panel._on_space_press(ev())
    panel._on_left_press(ev(10, 10))
    assert panel._pan is not None
    panel._on_focus_out(ev())
    assert panel._pan is None and not panel._space_down


# ---------------------------------------------------------------- controles
def test_zoom_in_and_out_buttons(big):
    panel, model = big.panel, big.panel.viewport
    start = model.zoom
    panel._zoom_in_button.invoke()
    assert model.zoom > start
    panel._zoom_out_button.invoke()
    assert model.zoom == pytest.approx(start)


def test_fit_button_returns_to_the_whole_image(big):
    panel, model = zoomed(big)
    panel._on_wheel(ev(100, 100, delta=240))
    panel._fit_button.invoke()
    pump(big.root, 0.1)
    assert model.fit_mode and model.fits == (True, True)
    x, y, w, h = displayed(panel)
    assert x >= 0 and y >= 0 and x + w <= panel._canvas.winfo_width() and y + h <= panel._canvas.winfo_height()


def displayed(panel):
    (item,) = [i for i in panel._canvas.find_all() if panel._canvas.type(i) == "image"]
    x, y = panel._canvas.coords(item)
    return x, y, panel._photo.width(), panel._photo.height()


@pytest.mark.parametrize("ratio", [1.0, 1.25, 1.5, 2.0])
def test_actual_size_button_is_one_to_one_with_physical_pixels(ratio):
    e = make_env(ratio)
    try:
        e.panel.show(quadrants((3000, 2000)))
        pump(e.root, 0.2)
        e.panel._actual_button.invoke()
        assert e.panel.viewport.zoom * ratio == pytest.approx(1.0)
        pump(e.root, 0.1)  # el indicador se actualiza con el repintado agrupado
        assert e.panel._zoom_label.cget("text") == "100 %"
    finally:
        e.root.destroy()
    assert e.errors == []


def test_zoom_indicator_follows_the_model(big):
    panel, model = big.panel, big.panel.viewport
    assert panel._zoom_label.cget("text") == f"{model.zoom * 100:.0f} %"
    panel._on_wheel(ev(100, 100, delta=120))
    pump(big.root, 0.1)
    assert panel._zoom_label.cget("text") == f"{model.zoom * 100:.0f} %"


# ------------------------------------------------------------------- barras
def test_scrollbars_hidden_when_the_image_fits_and_shown_when_zoomed(big):
    panel = big.panel
    assert panel._hbar.winfo_manager() == "" and panel._vbar.winfo_manager() == ""
    panel.actual_size()
    pump(big.root, 0.1)
    assert panel._hbar.winfo_manager() == "pack" and panel._vbar.winfo_manager() == "pack"
    panel.fit_to_window()
    pump(big.root, 0.1)
    assert panel._hbar.winfo_manager() == "" and panel._vbar.winfo_manager() == ""


def test_hiding_scrollbars_does_not_change_the_canvas_size(big):
    panel = big.panel
    size = panel._canvas.winfo_width(), panel._canvas.winfo_height()
    panel.actual_size()
    pump(big.root, 0.2)
    assert (panel._canvas.winfo_width(), panel._canvas.winfo_height()) == size


def test_only_the_overflowing_axis_shows_its_scrollbar(env):
    panel = env.panel
    panel.show(quadrants((6000, 200)))
    pump(env.root, 0.2)
    panel.actual_size()
    pump(env.root, 0.1)
    assert panel._hbar.winfo_manager() == "pack" and panel._vbar.winfo_manager() == ""


def test_scrollbars_mirror_the_model_after_zoom_and_pan(big):
    panel, model = zoomed(big)
    for action in (
        lambda: panel._on_wheel(ev(300, 200, delta=120)),
        lambda: (panel._begin_pan(ev(300, 300), 2), panel._move_pan(ev(200, 250), 2), panel._finish_pan(2)),
        lambda: panel._on_wheel(ev(50, 400, delta=-120)),
    ):
        action()
        pump(big.root, 0.1)
        fx, fy = model.scroll_fractions
        assert panel._hbar.get() == pytest.approx(fx, abs=1e-6)
        assert panel._vbar.get() == pytest.approx(fy, abs=1e-6)


def test_dragging_or_clicking_a_scrollbar_moves_the_view(big):
    panel, model = zoomed(big)
    panel._on_scrollbar(0, "moveto", "0.5")
    assert model.scroll_fractions[0][0] == pytest.approx(0.5, abs=1e-6)
    panel._on_scrollbar(1, "moveto", "0.0")
    assert model.position[1] == 0.0
    y = model.position[1]
    panel._on_scrollbar(0, "scroll", "1", "units")  # clic en la flecha / rueda sobre la barra
    panel._on_scrollbar(1, "scroll", "1", "pages")  # clic en el cauce
    assert model.position[1] < y
    panel._on_scrollbar(0, "bogus")  # orden desconocida: se ignora
    pump(big.root, 0.1)
    fx, fy = model.scroll_fractions
    assert panel._hbar.get() == pytest.approx(fx, abs=1e-6) and panel._vbar.get() == pytest.approx(fy, abs=1e-6)


def test_scrollbars_do_not_keep_their_own_geometry(big):
    panel, model = zoomed(big)
    model.pan_to(-123, -45)  # el modelo cambia por fuera del panel
    panel.redraw()
    assert panel._hbar.get() == pytest.approx(model.scroll_fractions[0], abs=1e-6)


# ------------------------------------------------------------- redimensionado
def test_resize_in_fit_mode_shows_the_whole_image_again(big):
    panel, model = big.panel, big.panel.viewport
    for geometry in ("1300x850+0+0", "850x650+0+0", "1000x700+0+0"):
        big.root.geometry(geometry)
        pump(big.root, 0.4)
        assert model.fit_mode and model.viewport_size == (panel._canvas.winfo_width(), panel._canvas.winfo_height())
        x, y, w, h = displayed(panel)
        assert x >= 0 and y >= 0 and x + w <= model.viewport_size[0] and y + h <= model.viewport_size[1]
        assert abs((x + w / 2) - model.viewport_size[0] / 2) <= 1 and abs((y + h / 2) - model.viewport_size[1] / 2) <= 1


def test_resize_in_manual_zoom_keeps_zoom_and_the_central_image_point(big):
    panel, model = zoomed(big)
    panel._on_wheel(ev(100, 100, delta=120))
    pump(big.root, 0.2)
    zoom = model.zoom
    cx, cy = centre(panel)
    point = model.viewport_to_image(cx, cy)
    big.root.geometry("1200x800+0+0")
    pump(big.root, 0.5)
    cx, cy = centre(panel)
    assert model.zoom == zoom and not model.fit_mode
    assert model.viewport_to_image(cx, cy) == pytest.approx(point, abs=1.0)


def test_resize_bursts_still_produce_a_single_render(big, monkeypatch):
    panel = big.panel
    calls = count_pixel_renders(panel, monkeypatch)
    for _ in range(30):
        panel._on_configure(None)
    pump(big.root, 0.4)
    assert len(calls) == 1


# ---------------------------------------------------- encuadre y propiedades
def test_framing_is_kept_when_a_tool_result_is_shown(big):
    panel, model = zoomed(big)
    panel._on_wheel(ev(100, 100, delta=120))
    panel._begin_pan(ev(300, 300), 2)
    panel._move_pan(ev(220, 260), 2)
    panel._finish_pan(2)
    pump(big.root, 0.2)
    zoom, position, fit = model.zoom, model.position, model.fit_mode
    panel.show(quadrants((3000, 2000)), keep_view=True)  # mismo tamaño: resultado de una herramienta
    assert model.zoom == zoom and model.fit_mode == fit
    assert model.position == pytest.approx(position)
    panel.show(quadrants((3000, 2000)), keep_view=False)  # imagen nueva: se ajusta
    assert model.fit_mode


def test_interaction_never_changes_the_image(env):
    panel = env.panel
    image = quadrants((900, 600))
    image.info["dpi"] = (300.0, 300.0)
    digest = hashlib.sha256(image.tobytes()).hexdigest()
    size, mode, info = image.size, image.mode, dict(image.info)
    panel.show(image)
    pump(env.root, 0.2)
    panel._on_wheel(ev(200, 200, delta=360))
    panel._begin_pan(ev(300, 300), 2)
    panel._move_pan(ev(100, 80), 2)
    panel._finish_pan(2)
    panel.actual_size()
    panel._on_scrollbar(0, "moveto", "0.3")
    panel.fit_to_window()
    pump(env.root, 0.3)
    assert panel._renderer.source is image
    assert hashlib.sha256(image.tobytes()).hexdigest() == digest
    assert (image.size, image.mode, dict(image.info)) == (size, mode, info)
    assert image.getpixel((0, 0)) == RED  # la transparencia / canal alfa sigue ahí
    assert panel.viewport.image_size == (900.0, 600.0)


def test_100_percent_renders_exact_pixels(env):
    panel = env.panel
    image = quadrants((2000, 1500))
    panel.show(image)
    pump(env.root, 0.2)
    panel.actual_size()
    pump(env.root, 0.2)
    shown = panel._shown
    area = panel.viewport.visible_area()
    x0, y0, x1, y1 = area.destination
    assert shown.image.size == (x1 - x0, y1 - y0)
    sx, sy = round(area.source[0]), round(area.source[1])
    expected = image.crop((sx, sy, sx + shown.image.width, sy + shown.image.height))
    assert shown.image.tobytes() == expected.tobytes()  # copia exacta de píxeles: sin remuestreo


# ---------------------------------------- eventos rápidos y destrucción
def test_burst_of_wheel_events_renders_once(big, monkeypatch):
    panel, model = big.panel, big.panel.viewport
    calls = count_pixel_renders(panel, monkeypatch)
    for _ in range(40):
        panel._on_wheel(ev(200, 150, delta=120))
        panel._on_wheel(ev(200, 150, delta=-120))
        panel._on_wheel(ev(200, 150, delta=120))
    assert calls == []  # nada se renderizó durante la ráfaga
    assert panel._frame_job is not None
    pump(big.root, 0.3)
    assert len(calls) == 1
    assert panel._frame_job is None


def test_burst_of_drag_events_keeps_a_single_pending_callback(big, monkeypatch):
    panel, _ = zoomed(big)
    calls = count_pixel_renders(panel, monkeypatch)
    panel._begin_pan(ev(400, 300), 2)
    jobs = set()
    for step in range(1, 200):
        panel._move_pan(ev(400 - step, 300 - step // 2), 2)
        jobs.add(panel._frame_job)
    assert len(jobs) == 1  # un solo after pendiente durante todo el arrastre
    pump(big.root, 0.3)
    panel._finish_pan(2)
    assert len(calls) == 1


def test_events_without_state_change_do_not_render(big, monkeypatch):
    panel, _ = zoomed(big)
    panel.fit_to_window()
    pump(big.root, 0.2)
    calls = count_pixel_renders(panel, monkeypatch)
    panel.fit_to_window()  # ya ajustada
    panel._begin_pan(ev(10, 10), 2)
    panel._move_pan(ev(90, 90), 2)  # imagen entera visible: el paneo no hace nada
    panel._finish_pan(2)
    pump(big.root, 0.2)
    assert calls == [] and panel._frame_job is None


def test_destroying_the_panel_with_pending_callbacks_is_safe(big):
    panel = big.panel
    panel._on_wheel(ev(100, 100, delta=120))  # repintado pendiente
    panel._on_configure(None)  # redimensionado pendiente
    assert panel._frame_job is not None and panel._resize_job is not None
    panel.destroy()
    assert panel._frame_job is None and panel._resize_job is None
    pump(big.root, 0.3)  # los callbacks cancelados no se ejecutan
    panel._on_wheel(ev(1, 1, delta=120))  # eventos tardíos: se ignoran
    panel._render()
    assert big.errors == []


def test_destroying_the_whole_window_with_pending_callbacks_is_safe(big):
    big.panel._on_wheel(ev(100, 100, delta=120))
    big.panel._on_configure(None)
    big.root.destroy()
    time.sleep(0.2)
    assert big.errors == []


def test_photo_reference_is_kept_and_released_on_the_main_thread(big):
    panel = big.panel
    assert panel._photo is not None
    panel._on_wheel(ev(100, 100, delta=120))
    pump(big.root, 0.2)
    assert panel._photo is not None  # sin referencia Tk dibujaría una imagen vacía
    panel.destroy()
    assert panel._photo is None


# ------------------------------------------------------------------ tiempos
def test_render_timings_are_recorded(big):
    panel = big.panel
    n = len(panel.render_timings)
    assert n >= 1
    panel._on_wheel(ev(100, 100, delta=120))
    pump(big.root, 0.2)
    timings = panel.render_timings
    assert len(timings) == n + 1
    last = timings[-1]
    assert last.total_ms >= last.render_ms >= 0 and last.photo_ms >= 0
    assert last.source_size == (3000, 2000) and last.drawn_size[0] > 0
    stats = panel.render_stats()
    assert stats["count"] == len(timings) and stats["max_ms"] >= stats["mean_ms"] > 0


# ------------------------------------- bloqueo de navegación (política de interacción)
def test_blocked_zoom_ignores_wheel_buttons_and_leaves_the_view_untouched(big):
    panel, model = big.panel, big.panel.viewport
    panel.set_navigation_enabled(zoom=False, pan=False)
    state = (model.zoom, model.position, model.fit_mode)
    panel._on_wheel(ev(200, 150, delta=120))
    panel.zoom_in(); panel.zoom_out(); panel.actual_size(); panel.fit_to_window()
    assert (model.zoom, model.position, model.fit_mode) == state
    assert panel._frame_job is None  # ni siquiera se programó un repintado
    for button in panel._buttons:
        assert button.cget("state") == "disabled"


def test_blocked_pan_ignores_drag_space_drag_and_scrollbars(big):
    panel, model = zoomed(big)
    panel.set_navigation_enabled(zoom=False, pan=False)
    position = model.position
    panel._begin_pan(ev(300, 300), 2)
    assert panel._pan is None
    panel._move_pan(ev(100, 100), 2)
    panel._on_space_press(ev()); panel._on_left_press(ev(300, 300)); panel._move_pan(ev(100, 100), 1)
    assert model.position == position and panel._pan is None
    shown = panel._hbar.get()
    panel._hbar.set(0.9, 1.0)  # la barra movió su indicador al arrastrarla…
    panel._on_scrollbar(0, "moveto", "0.9")
    assert model.position == position and panel._hbar.get() == shown  # …y vuelve a donde está la vista


def test_blocking_cancels_a_drag_in_progress(big):
    panel, model = zoomed(big)
    panel._begin_pan(ev(300, 300), 2)
    assert panel._pan is not None
    panel.set_navigation_enabled(zoom=False, pan=False)
    assert panel._pan is None
    position = model.position
    panel._move_pan(ev(100, 100), 2)
    assert model.position == position


def test_unblocking_restores_every_interaction(big):
    panel, model = big.panel, big.panel.viewport
    panel.set_navigation_enabled(zoom=False, pan=False)
    panel.set_navigation_enabled(zoom=True, pan=True)
    start = model.zoom
    panel._on_wheel(ev(200, 150, delta=120))
    assert model.zoom > start
    pump(big.root, 0.1)
    for button in panel._buttons:
        assert button.cget("state") == "normal" or button is panel._zoom_in_button
    panel.actual_size()
    pump(big.root, 0.1)
    before = model.position
    panel._begin_pan(ev(300, 300), 2)
    panel._move_pan(ev(260, 280), 2)
    panel._finish_pan(2)
    assert model.position != before


def test_zoom_and_pan_permissions_are_independent(big):
    panel, model = zoomed(big)
    panel.set_navigation_enabled(zoom=False, pan=True)
    zoom, position = model.zoom, model.position
    panel._on_wheel(ev(100, 100, delta=120))
    assert model.zoom == zoom
    panel._begin_pan(ev(300, 300), 2)
    panel._move_pan(ev(260, 300), 2)
    panel._finish_pan(2)
    assert model.position != position


def test_the_displayed_image_and_resizing_keep_working_while_locked(big):
    panel, model = big.panel, big.panel.viewport
    panel.set_navigation_enabled(zoom=False, pan=False)
    big.root.geometry("1200x800+0+0")
    pump(big.root, 0.5)
    assert model.fit_mode and model.viewport_size == (panel._canvas.winfo_width(), panel._canvas.winfo_height())
    panel.show(quadrants((3000, 2000)), keep_view=True)  # un resultado se sigue mostrando
    assert panel._photo is not None
