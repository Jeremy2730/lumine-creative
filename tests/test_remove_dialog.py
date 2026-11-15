"""Ventana de Remove (RemoveDialog) con una sesión real y una «IA» controlable. Necesita Tk (se omite sin pantalla)."""
import time

import customtkinter as ctk
import pytest

from app.interaction import Action
from tests.test_remove_controller import Env, FakeIO, GatedRemover, MainView, lumine_free
from app.controllers.design_controller import DesignController
from app.services.processing_service import ProcessingService
from app.services.task_runner import BackgroundTaskRunner
from app.services.tool_registry import ToolRegistry
from core.design_engine import DesignEngine
from tools.remove import RemoveController, RemoveState
import tools.remove.dialog as dialog_module


def option(widget, key):
    try:
        return widget.cget(key)
    except Exception:  # el Tk simulado de las pruebas guarda las opciones en _opts
        return widget._opts[key]


@pytest.fixture
def env(tmp_path):
    try:
        root = ctk.CTk()
    except Exception as exc:
        pytest.skip(f"sin pantalla: {exc}")
    e = Env()
    e.root = root
    e.op = GatedRemover()
    registry = ToolRegistry()
    registry.register("remove_background", lambda: e.op)
    e.service = ProcessingService(DesignEngine(FakeIO()), registry, tmp_path)
    e.design = DesignController(e.service, BackgroundTaskRunner())
    e.main = MainView()
    e.design.attach_view(e.main)
    e.service.open_image(tmp_path / "foto.png")
    e.doc = e.service.snapshot()
    e.remove = RemoveController(e.design)
    assert e.remove.open()
    try:
        e.dialog = dialog_module.RemoveDialog(root, e.remove)
    except AttributeError as exc:  # el Tk simulado no implementa métodos de ventana
        root.destroy()
        pytest.skip(f"Tk simulado incompleto: {exc}")
    yield e
    if e.dialog._alive:
        e.dialog.destroy()
    root.destroy()


def pump(env, condition, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        env.design.process_pending()
        if condition():
            return
        time.sleep(0.005)
    raise AssertionError("tiempo agotado")


def enabled(env):
    d = env.dialog
    return tuple(option(b, "state") == "normal" for b in (d._run_button, d._cancel_button, d._ok_button))


def test_open_shows_the_original_with_run_and_cancel_enabled_and_ok_disabled(env):
    d = env.dialog
    assert env.remove.state is RemoveState.READY and env.op.calls == 0
    assert d._viewer.viewport is not None and d._viewer._renderer.checkerboard is True
    assert enabled(env) == (True, True, False)
    assert "Remove listo" in option(d._message, "text")
    assert option(d._run_button, "text") == "Quitar fondo" and option(d._ok_button, "text") == "OK"


def test_buttons_and_navigation_follow_the_session_state(env):
    d = env.dialog
    env.remove.run()
    assert env.op.started.wait(5)
    assert enabled(env) == (False, True, False) and not d._viewer._zoom_enabled
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert enabled(env) == (False, True, True) and d._viewer._zoom_enabled
    assert "Procesamiento completado" in option(d._message, "text")


def test_progress_bar_is_indeterminate_while_busy_and_full_when_completed(env):
    d = env.dialog
    assert option(d._progress, "mode") == "determinate" and d._busy is False
    env.remove.run()
    assert d._busy and option(d._progress, "mode") == "indeterminate"
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert d._busy is False and option(d._progress, "mode") == "determinate"


def test_ok_closes_the_window_applies_and_returns_control(env):
    env.op.gate.set()
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    d = env.dialog
    d._ok_button.invoke() if hasattr(d._ok_button, "invoke") else env.remove.ok()
    assert env.remove.state is RemoveState.CLOSED and not d._alive
    assert lumine_free(env) and len(env.main.snapshots) == 1


def test_cancel_closes_without_changes(env):
    d = env.dialog
    env.remove.cancel()
    assert env.remove.state is RemoveState.CLOSED and not d._alive and lumine_free(env)
    assert env.main.snapshots == [] and env.service.snapshot().image is env.doc.image


def test_closing_the_window_with_the_system_button_is_refused(env):
    d = env.dialog
    d.protocol  # el protocolo se registró en _build; se simula la petición del sistema:
    env.remove.refuse_close()
    assert d._alive and env.remove.state is RemoveState.READY
    assert "Cancelar" in option(d._message, "text")


def test_destroy_is_idempotent_and_late_calls_do_nothing(env):
    d = env.dialog
    env.remove.close()
    d.destroy()
    d.state_changed()
    d.show_status("tarde", dialog_module.StatusLevel.INFO)
    d.set_busy(True)
    d.show_image(env.doc.image, keep_view=True)
    assert not d._alive and lumine_free(env)
