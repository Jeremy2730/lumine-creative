"""tests/test_file_menu_gui.py

Responsabilidad:
    - Pruebas de la interfaz de archivos con una MainWindow real: menú y
      estados, atajos reales (Ctrl+O/S/Mayús+S), título, cierre con cambios
      pendientes, sondeo resistente y los envoltorios de los diálogos.

No conoce:
    - Diálogos nativos: se sustituyen por funciones falsas (son modales).

Notas:
    - Las pruebas de ventana necesitan display; sin él se saltan (en un
      servidor sin pantalla: ``xvfb-run pytest``). Las de los
      envoltorios de diálogos no lo necesitan.
"""
import time
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

import customtkinter as ctk
import pytest
from PIL import Image

import gui.main_window as main_window
from app.application import build_controllers
from app.services.file_service import SaveSuggestion
from config.settings import Settings
from gui.components import dialogs
from gui.main_window import MainWindow
from gui.panels.status_panel import StatusPanel
from gui.panels.tools_panel import ToolsPanel

TITLE = "Herramienta para Diseño"

# Estados de modificadores de X11/Tk: Shift=0x1, BloqMayús=0x2, Control=0x4.
CTRL, CTRL_SHIFT, CTRL_CAPS, CTRL_SHIFT_CAPS = 0x4, 0x5, 0x6, 0x7


def make_png(folder: Path, name="foto.png") -> Path:
    img = Image.new("RGB", (40, 20), "teal")
    for x in range(20, 40):
        for y in range(20):
            img.putpixel((x, y), (255, 140, 0))  # borde nítido: el enfoque sí cambia la imagen
    path = folder / name
    img.save(path)
    return path


@pytest.fixture
def ui(tmp_path, monkeypatch, tk_gc_on_main_thread):
    settings = Settings(output_dir=tmp_path / "descargas", app_title=TITLE)
    try:
        design, files = build_controllers(settings)
        win = MainWindow(design, settings, files)
    except tk.TclError:
        pytest.skip("sin display: ejecuta con xvfb-run")
    design.attach_view(win)
    files.attach_view(win)
    calls = SimpleNamespace(open=[], save=[], unsaved=[], flatten=[])
    answers = SimpleNamespace(open=None, save=None, unsaved="cancel", flatten=True)

    def fake_open(extensions, parent=None):
        calls.open.append(1)
        return answers.open

    def fake_save(suggestion, parent=None):
        calls.save.append(suggestion)
        return answers.save

    def fake_unsaved(name, parent=None):
        calls.unsaved.append(name)
        return answers.unsaved

    def fake_flatten(parent=None):
        calls.flatten.append(1)
        return answers.flatten

    monkeypatch.setattr(main_window, "ask_image_path", fake_open)
    monkeypatch.setattr(main_window, "ask_save_path", fake_save)
    monkeypatch.setattr(main_window, "ask_unsaved_changes", fake_unsaved)
    monkeypatch.setattr(main_window, "ask_flatten_to_jpg", fake_flatten)
    src = tmp_path / "origen"
    src.mkdir()
    yield SimpleNamespace(
        win=win, design=design, files=files, calls=calls, answers=answers, src=src, out=tmp_path / "salida"
    )
    if not win._closed:
        win.destroy()


def pump(ui, seconds=0.3):
    end = time.time() + seconds
    while time.time() < end:
        ui.win.update()
        time.sleep(0.01)


def settle(ui):
    deadline = time.time() + 5
    while time.time() < deadline:
        ui.win.update()
        if not ui.design.is_busy:
            ui.win.update()
            return
        time.sleep(0.01)
    raise AssertionError("timeout")


def open_doc(ui, name="foto.png"):
    ui.files.open_path(make_png(ui.src, name))
    settle(ui)


def key(ui, keysym, state):
    """Tecla realista: ``event_generate("<Control-S>")`` sintetiza la S CON Shift y no
    representa Bloq Mayús, así que se envía keysym + estado explícitos."""
    ui.win.focus_force()
    ui.win.update()
    ui.win.event_generate("<KeyPress>", keysym=keysym, state=state)
    ui.win.update()


def state(menu, index):
    return str(menu.entrycget(index, "state"))


# ---------------- estructura y estados del menú ----------------

def test_menu_bar_has_the_expected_menus_entries_and_accelerators(ui):
    bar = ui.win._menu.bar
    assert [bar.entrycget(i, "label") for i in (0, 1)] == ["Archivos", "Herramientas"]
    files = ui.win._menu.files_menu
    assert [files.entrycget(i, "label") for i in (0, 1, 2, 4)] == ["Abrir…", "Guardar", "Guardar como…", "Salir"]
    assert [files.entrycget(i, "accelerator") for i in (0, 1, 2)] == ["Ctrl+O", "Ctrl+S", "Ctrl+Mayús+S"]
    tools = ui.win._menu.tools_menu
    assert [tools.entrycget(i, "label") for i in range(4)] == [
        "Quitar fondo", "Semitono", "Tamaño y resolución…", "Dar nitidez",
    ]


def test_the_big_open_and_save_buttons_are_gone(ui):
    assert not hasattr(ToolsPanel, "_open_button") and not hasattr(ui.win._tools_panel, "_open_button")
    assert not hasattr(ui.win._status_panel, "_save_button")
    assert not hasattr(StatusPanel, "set_save_enabled")


def test_menu_states_follow_document_and_busy(ui):
    files, tools = ui.win._menu.files_menu, ui.win._menu.tools_menu
    assert state(files, 0) == "normal"                       # Abrir
    assert state(files, 1) == state(files, 2) == "disabled"  # Guardar / Guardar como
    assert state(tools, 0) == "disabled"
    assert state(files, 4) == "normal"                       # Salir
    open_doc(ui)
    assert state(files, 1) == state(files, 2) == "normal" and state(tools, 0) == "normal"
    ui.design.run_task(start="lento", work=lambda: time.sleep(0.4), on_success=lambda _: None, error="x")
    pump(ui, 0.1)
    assert state(files, 0) == state(files, 1) == state(files, 2) == "disabled"
    assert state(tools, 2) == "disabled" and state(files, 4) == "normal"
    settle(ui)
    assert state(files, 0) == "normal"


# ---------------- distribución: sin botones de herramientas, más espacio para la imagen ----------------

def make_portrait(folder: Path, name="vertical.png") -> Path:
    img = Image.new("RGB", (900, 1400), "#1f6aa5")
    for y in range(700, 1400):
        for x in range(900):
            img.putpixel((x, y), (240, 160, 40))
    path = folder / name
    img.save(path)
    return path


def widgets_of(root):
    for child in root.winfo_children():
        yield child
        yield from widgets_of(child)


def layout(ui):
    pump(ui, 0.3)
    w = ui.win
    image, bottom, status = w._image_panel, w._tools_panel, w._status_panel
    return SimpleNamespace(
        window=(w.winfo_width(), w.winfo_height()),
        image=(image.winfo_width(), image.winfo_height()),
        pipeline_visible=bool(bottom.winfo_ismapped()),
        status_bottom=status.winfo_y() + status.winfo_height(),
        drawn=image.viewport.rendered_size,  # lo que dibuja el visor lo dicta el modelo
    )


def test_no_tool_buttons_remain_in_the_main_window_but_the_pipeline_history_does(ui):
    assert [w for w in widgets_of(ui.win) if isinstance(w, ctk.CTkButton)] == []
    texts = [w.cget("text") for w in widgets_of(ui.win._tools_panel) if isinstance(w, ctk.CTkLabel)]
    assert "Pipeline / procesos aplicados" in texts and "Herramientas" not in texts


def test_tools_menu_runs_each_tool_exactly_as_before(ui, monkeypatch):
    from tools.background_remover import BackgroundRemover
    from tools.size_resolution.dialog import SizeResolutionDialog

    monkeypatch.setattr(BackgroundRemover, "_load_rembg", staticmethod(lambda: (lambda data: data)))
    open_doc(ui)
    tools = ui.win._menu.tools_menu
    for index in (0, 1, 3):  # Quitar fondo, Semitono, Dar nitidez
        tools.invoke(index)
        settle(ui)
    labels = [op.label for op in ui.design._service.snapshot().operations]
    assert labels == ["Fondo", "Semitono", "Nitidez"]
    chips = [w.cget("text").strip() for w in widgets_of(ui.win._tools_panel._chips) if isinstance(w, ctk.CTkLabel)]
    assert [c for c in chips if c != "→"] == ["Fondo", "Semitono", "Nitidez"]  # el historial se conserva
    tools.invoke(2)  # Tamaño y resolución… abre su diálogo
    ui.win.update()
    opened = [w for w in ui.win.winfo_children() if isinstance(w, SizeResolutionDialog)]
    assert len(opened) == 1
    opened[0].destroy()


def test_image_panel_gets_all_the_freed_space_and_follows_the_window(ui):
    ui.files.open_path(make_portrait(ui.src))
    settle(ui)
    sizes = {}
    for geometry in ("1000x760", "1400x900", "820x640"):
        ui.win.geometry(geometry)
        sizes[geometry] = layout(ui)
    for geometry, m in sizes.items():
        # El espacio liberado no queda vacío: la pila de paneles llena la ventana hasta su margen inferior (16 px).
        assert abs(m.window[1] - (m.status_bottom + 16)) <= 2, geometry
        # El panel de procesos está oculto y la imagen se queda con ese espacio: domina la ventana.
        assert not m.pipeline_visible, geometry
        assert m.image[1] >= 0.7 * m.window[1], geometry
        # Sin deformar: misma proporción que el original (900×1400) y siempre dentro del panel.
        assert abs(m.drawn[0] / m.drawn[1] - 900 / 1400) < 0.01, geometry
        assert m.drawn[0] <= m.image[0] and m.drawn[1] <= m.image[1], geometry
    small, default, large = sizes["820x640"], sizes["1000x760"], sizes["1400x900"]
    # Al agrandar la ventana, TODO el espacio extra va a la imagen; los demás paneles no cambian.
    assert large.image[0] - default.image[0] >= 400 - 2 and large.image[1] - default.image[1] >= 140 - 2
    assert default.image[1] - small.image[1] >= 120 - 2


# ---------------- atajos reales ----------------

def test_ctrl_o_opens_the_open_dialog(ui):
    key(ui, "o", CTRL)
    assert len(ui.calls.open) == 1
    key(ui, "O", CTRL_CAPS)  # con Bloq Mayús
    assert len(ui.calls.open) == 2


def test_ctrl_s_saves_and_ctrl_shift_s_always_asks_for_a_destination(ui):
    open_doc(ui)
    ui.answers.save = str(ui.out / "doc.png")
    key(ui, "s", CTRL)                        # sin destino: se comporta como Guardar como
    settle(ui)
    assert len(ui.calls.save) == 1 and (ui.out / "doc.png").exists()
    key(ui, "s", CTRL)                        # ya tiene destino: escribe sin preguntar
    settle(ui)
    assert len(ui.calls.save) == 1
    key(ui, "S", CTRL_CAPS)                   # Bloq Mayús sin Shift: sigue siendo Guardar
    settle(ui)
    assert len(ui.calls.save) == 1
    ui.answers.save = str(ui.out / "otro.png")
    key(ui, "S", CTRL_SHIFT)                  # Ctrl+Mayús+S: Guardar como, siempre pregunta
    settle(ui)
    assert len(ui.calls.save) == 2 and (ui.out / "otro.png").exists()
    assert ui.files.document.save_path == ui.out / "otro.png"
    ui.answers.save = str(ui.out / "tercero.png")
    key(ui, "s", CTRL_SHIFT_CAPS)             # Ctrl+Mayús+S con Bloq Mayús activo
    settle(ui)
    assert len(ui.calls.save) == 3 and (ui.out / "tercero.png").exists()


def test_shortcuts_do_not_fire_while_a_dialog_has_the_focus(ui):
    dialog = ctk.CTkToplevel(ui.win)
    entry = ctk.CTkEntry(dialog)
    entry.pack()
    ui.win.update()
    dialog.update()
    entry.focus_force()
    dialog.update()
    entry._entry.event_generate("<Control-o>")
    ui.win.update()
    dialog.destroy()
    assert ui.calls.open == []  # bind en la ventana principal, no bind_all


def test_shortcut_without_a_document_only_warns(ui):
    key(ui, "s", CTRL)
    assert ui.calls.save == []
    assert "Primero abre una imagen" in ui.win._status_panel._label.cget("text")


# ---------------- título, edición y guardado desde la ventana ----------------

def test_title_follows_open_edit_and_save_end_to_end(ui):
    assert ui.win.title() == TITLE
    open_doc(ui)
    assert ui.win.title() == f"foto.png — {TITLE}"
    ui.win._menu.tools_menu.invoke(3)  # Dar nitidez, desde el menú Herramientas
    settle(ui)
    assert ui.win.title() == f"foto.png * — {TITLE}"
    ui.answers.save = str(ui.out / "final.png")
    ui.win._menu.files_menu.invoke(1)  # Guardar
    settle(ui)
    assert ui.win.title() == f"final.png — {TITLE}"


def test_opening_another_file_with_pending_changes_asks_once(ui):
    open_doc(ui)
    ui.design.sharpen()
    settle(ui)
    ui.answers.open = str(make_png(ui.src, "b.png"))
    ui.answers.unsaved = "cancel"
    ui.win._menu.files_menu.invoke(0)  # Abrir…
    settle(ui)
    assert ui.calls.unsaved == ["foto.png"] and ui.files.document.origin_path.name == "foto.png"
    ui.answers.unsaved = "discard"
    ui.win._menu.files_menu.invoke(0)
    settle(ui)
    assert ui.files.document.origin_path.name == "b.png" and ui.win.title() == f"b.png — {TITLE}"


# ---------------- cierre de la aplicación ----------------

def close_with_x(ui):
    ui.win.tk.call(ui.win.protocol("WM_DELETE_WINDOW"))
    if not ui.win._closed:
        ui.win.update()


def test_closing_a_clean_window_closes_without_asking(ui):
    open_doc(ui)
    close_with_x(ui)
    assert ui.win._closed and ui.calls.unsaved == []


def test_closing_with_pending_changes_offers_save_discard_cancel(ui):
    open_doc(ui)
    ui.design.sharpen()
    settle(ui)
    ui.answers.unsaved = "cancel"
    close_with_x(ui)
    assert not ui.win._closed and ui.calls.unsaved == ["foto.png"]
    ui.answers.unsaved = "save"
    ui.answers.save = None  # Guardar cancelado → no cierra
    close_with_x(ui)
    settle(ui)
    assert not ui.win._closed
    ui.answers.save = str(ui.out / "cierre.png")  # Guardar correcto → cierra
    close_with_x(ui)
    deadline = time.time() + 5
    while not ui.win._closed and time.time() < deadline:
        ui.win.update()
        time.sleep(0.01)
    assert ui.win._closed and (ui.out / "cierre.png").exists()


def test_closing_with_pending_changes_and_discard_closes(ui):
    open_doc(ui)
    ui.design.sharpen()
    settle(ui)
    ui.answers.unsaved = "discard"
    close_with_x(ui)
    assert ui.win._closed and not ui.out.exists()


def test_salir_menu_entry_goes_through_the_same_close_path(ui):
    open_doc(ui)
    ui.design.sharpen()
    settle(ui)
    ui.answers.unsaved = "cancel"
    ui.win._menu.files_menu.invoke(4)
    assert not ui.win._closed and ui.calls.unsaved == ["foto.png"]
    ui.answers.unsaved = "discard"
    ui.win._menu.files_menu.invoke(4)
    assert ui.win._closed


def test_a_window_without_file_controller_still_closes_and_has_no_file_actions(tmp_path):
    settings = Settings(output_dir=tmp_path / "d")
    from app.application import build_controller

    try:
        win = MainWindow(build_controller(settings), settings)
    except tk.TclError:
        pytest.skip("sin display: ejecuta con xvfb-run")
    win.update()
    assert str(win._menu.files_menu.entrycget(0, "state")) == "disabled"
    win.tk.call(win.protocol("WM_DELETE_WINDOW"))
    assert win._closed


# ---------------- sondeo resistente ----------------

def test_poll_survives_a_failing_result_callback(ui):
    ui.win.report_callback_exception = lambda *args: None  # silenciar el traceback esperado
    delivered = []

    def boom(_result):
        raise RuntimeError("callback roto")

    ui.design._runner.submit(lambda: 1, boom, lambda e: None)
    pump(ui, 0.3)
    ui.design._runner.submit(lambda: 2, lambda r: delivered.append(r), lambda e: None)
    pump(ui, 0.4)
    assert delivered == [2]  # antes: el sondeo moría y esto nunca llegaba


# ---------------- envoltorios de diálogos (sin display) ----------------

def test_unsaved_changes_dialog_maps_answers_and_explains_each_button(monkeypatch):
    for raw, expected in ((True, "save"), (False, "discard"), (None, "cancel")):
        monkeypatch.setattr(dialogs.messagebox, "askyesnocancel", lambda raw=raw, **kw: raw)
        assert dialogs.ask_unsaved_changes("foto.png") == expected
    seen = {}
    monkeypatch.setattr(dialogs.messagebox, "askyesnocancel", lambda **kw: seen.update(kw))
    dialogs.ask_unsaved_changes("foto.png")
    assert "foto.png" in seen["message"] and "guardar" in seen["message"] and "descartarlos" in seen["message"]


def test_flatten_dialog_returns_true_only_when_accepted(monkeypatch):
    monkeypatch.setattr(dialogs.messagebox, "askokcancel", lambda **kw: True)
    assert dialogs.ask_flatten_to_jpg() is True
    monkeypatch.setattr(dialogs.messagebox, "askokcancel", lambda **kw: False)
    assert dialogs.ask_flatten_to_jpg() is False


@pytest.mark.parametrize("fmt,first,ext", [("PNG", "PNG", ".png"), ("JPEG", "JPEG", ".jpg")])
def test_save_dialog_puts_the_suggested_format_first_and_passes_name_and_folder(monkeypatch, tmp_path, fmt, first, ext):
    seen = {}
    monkeypatch.setattr(dialogs.filedialog, "asksaveasfilename", lambda **kw: seen.update(kw) or str(tmp_path / "x"))
    suggestion = SaveSuggestion(directory=tmp_path, filename=f"foto_editada{ext}", format=fmt)
    assert dialogs.ask_save_path(suggestion) == str(tmp_path / "x")
    assert seen["filetypes"][0][0] == first and seen["defaultextension"] == ext
    assert seen["initialfile"] == f"foto_editada{ext}" and seen["initialdir"] == str(tmp_path)
    assert {name for name, _ in seen["filetypes"]} == {"PNG", "JPEG"}


@pytest.mark.parametrize("cancelled", ["", ()])
def test_cancelled_file_dialogs_return_none(monkeypatch, tmp_path, cancelled):
    monkeypatch.setattr(dialogs.filedialog, "asksaveasfilename", lambda **kw: cancelled)
    monkeypatch.setattr(dialogs.filedialog, "askopenfilename", lambda **kw: cancelled)
    suggestion = SaveSuggestion(directory=tmp_path, filename="a.png", format="PNG")
    assert dialogs.ask_save_path(suggestion) is None
    assert dialogs.ask_image_path({".png"}) is None
