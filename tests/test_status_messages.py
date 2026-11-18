"""Qué mensajes de estado ve el usuario en Lumine: solo avisos y errores; la rutina se calla.

Sin Tk: la política (``user_visible_status``) es la que usa ``StatusPanel``; aquí se recorren los
flujos reales (abrir, herramientas, guardar, avisos, errores) con una vista falsa y se calcula
lo que llegaría a la pantalla. Los controladores siguen emitiendo todos los niveles.
"""
import time
from pathlib import Path

import pytest
from PIL import Image

from app.application import build_controllers
from app.controllers.design_controller import StatusLevel, user_visible_status
from config.settings import Settings


class FakeView:
    def __init__(self):
        self.emitted = []  # todo lo que el controlador emite (sin filtrar)
        self.snapshots, self.busy_calls = [], []
        self.on_snapshot = None
        self.open_answer = None
        self.save_answers = []

    def shown(self):  # lo que vería el usuario
        return [(user_visible_status(m, lv), lv) for m, lv in self.emitted if user_visible_status(m, lv)]

    def show_snapshot(self, snapshot):
        self.snapshots.append(snapshot)
        if self.on_snapshot:
            self.on_snapshot(snapshot)

    def show_status(self, message, level):
        self.emitted.append((message, level))

    def set_busy(self, busy):
        self.busy_calls.append(busy)

    def ask_open_path(self):
        return self.open_answer

    def ask_save_path(self, suggestion):
        return self.save_answers.pop(0) if self.save_answers else None

    def ask_unsaved_changes(self, name):
        return "cancel"

    def ask_flatten_to_jpg(self):
        return True

    def ask_exit_while_processing(self, has_unsaved_changes):
        return False

    def set_window_title(self, title):
        pass

    def exit_application(self):
        pass


def wait(design):
    end = time.time() + 5
    while time.time() < end:
        design.process_pending()
        if not design.is_busy:
            return
        time.sleep(0.005)
    raise AssertionError("timeout")


@pytest.fixture
def app(tmp_path):
    design, files = build_controllers(Settings(output_dir=tmp_path / "descargas", app_title="Lumine"))
    view = FakeView()
    design.attach_view(view)
    files.attach_view(view)
    view.on_snapshot = files.on_snapshot
    src = tmp_path / "foto.png"
    Image.new("RGB", (40, 20), "green").save(src)
    return design, files, view, src, tmp_path


def open_image(app, path=None):
    design, files, view, src, _ = app
    files.open_path(path or src)
    wait(design)


# ---- la política ----
def test_only_warnings_and_errors_are_visible():
    assert user_visible_status("✅ Imagen cargada: a.png", StatusLevel.SUCCESS) == ""
    assert user_visible_status("Listo", StatusLevel.INFO) == ""
    assert user_visible_status("⚠️ Cuidado", StatusLevel.WARNING) == "⚠️ Cuidado"
    assert user_visible_status("❌ Falló", StatusLevel.ERROR) == "❌ Falló"


def test_the_remove_window_follows_the_same_criterion():
    """Referencia (sin modificar Remove): su vista solo deja pasar WARNING y ERROR."""
    source = (Path(__file__).resolve().parent.parent / "tools" / "remove" / "dialog.py").read_text(encoding="utf-8")
    assert "level not in (StatusLevel.ERROR, StatusLevel.WARNING)" in source


# ---- lo rutinario desaparece ----
def test_opening_an_image_says_nothing(app):
    open_image(app)
    assert app[2].emitted  # el controlador sigue informando...
    assert app[2].shown() == []  # ...pero el usuario no ve «Imagen cargada» ni «Abriendo»


def test_tools_and_saving_say_nothing_when_they_work(app):
    design, files, view, src, tmp = app
    open_image(app)
    design.sharpen()
    wait(design)
    design.comic_effect()
    wait(design)
    view.save_answers = [str(tmp / "salida" / "resultado.png")]
    files.save_as()
    wait(design)
    assert any(lv is StatusLevel.SUCCESS for _, lv in view.emitted)  # hubo éxitos emitidos
    assert view.shown() == [] and view.busy_calls  # y la barra de progreso (set_busy) sigue funcionando
    assert (tmp / "salida" / "resultado.png").exists()


# ---- lo importante se conserva ----
def test_a_failed_open_still_shows_the_error(app):
    design, files, view, src, tmp = app
    bad = tmp / "rota.png"
    bad.write_bytes(b"no es una imagen")
    open_image(app, bad)
    assert [lv for _, lv in view.shown()] == [StatusLevel.ERROR]
    assert "No se pudo abrir" in view.shown()[0][0]


def test_acting_without_an_image_still_warns(app):
    design, files, view, src, tmp = app
    design.sharpen()
    assert [lv for _, lv in view.shown()] == [StatusLevel.WARNING]


def test_an_invalid_extension_still_warns(app):
    design, files, view, src, tmp = app
    open_image(app)
    view.save_answers = [str(tmp / "x.bmp")]
    files.save_as()
    wait(design)
    shown = view.shown()
    assert [lv for _, lv in shown] == [StatusLevel.WARNING] and ".png" in shown[0][0]


def test_a_second_action_while_busy_still_warns(app):
    design, files, view, src, tmp = app
    open_image(app)
    design.sharpen()  # queda en curso
    design.comic_effect()  # rechazada: hay un proceso activo
    wait(design)
    assert [lv for _, lv in view.shown()] == [StatusLevel.WARNING]
    assert "Espera" in view.shown()[0][0]


def test_a_tool_failure_still_shows_the_error_and_logs_the_detail(app, caplog):
    design, files, view, src, tmp = app
    open_image(app)
    design._service.preview_tool = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fallo interno"))
    design._service.apply_tool = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fallo interno"))
    with caplog.at_level("ERROR"):
        design.sharpen()
        wait(design)
    assert [lv for _, lv in view.shown()] == [StatusLevel.ERROR]
    assert "fallo interno" not in view.shown()[0][0]  # el detalle técnico no se enseña...
    assert "fallo interno" in caplog.text  # ...pero sigue en el log
