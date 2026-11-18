"""Ventana de Remove (RemoveDialog) con una sesión real y una «IA» controlable. Necesita Tk (se omite sin pantalla)."""
import sys
import time
import types

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
    assert option(d._message, "text") == ""  # sin «Remove listo…»
    assert option(d._run_button, "text") == "Quitar fondo" and option(d._ok_button, "text") == "OK"


def test_buttons_and_navigation_follow_the_session_state(env):
    d = env.dialog
    env.remove.run()
    assert env.op.started.wait(5)
    assert enabled(env) == (False, True, False) and not d._viewer._zoom_enabled
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert enabled(env) == (False, True, True) and d._viewer._zoom_enabled
    assert option(d._message, "text") == ""  # sin «Procesamiento completado…»


def bar_visible(d):
    """La barra está puesta sobre el visor ("place") o no ("")."""
    return d._progress.winfo_manager() == "place"


def wait_hidden(env, timeout=3.0):
    """Bombea la ventana hasta que la barra se oculta (tras completar hay un llenado final)."""
    end = time.monotonic() + timeout
    while bar_visible(env.dialog) and time.monotonic() < end:
        env.dialog.update()
        time.sleep(0.01)
    return not bar_visible(env.dialog)


def center_of(widget):
    return (
        widget.winfo_rootx() + widget.winfo_width() / 2,
        widget.winfo_rooty() + widget.winfo_height() / 2,
    )


def start_run(env):
    env.op.started.clear()
    env.op.gate.clear()
    env.remove.run()
    assert env.op.started.wait(5)
    env.dialog.update()


def test_progress_animation_curves_only_move_right_and_never_reset():
    assert dialog_module._BAR_WIDTH == 189  # ancho aprobado (~5 cm a 96 DPI)
    assert dialog_module._BAR_HEIGHT > 0  # el alto es configurable: no se fija aquí; la prueba de medidas
    # reales (test_progress_bar_is_centered_...) lo compara con la constante, sea cual sea su valor
    times = [i * 0.02 for i in range(0, 3000)]  # 60 s a 20 ms
    values = [dialog_module.wait_value(x) for x in times]
    assert values[0] == 0
    assert all(b >= a for a, b in zip(values, values[1:]))  # nunca retrocede: sin reinicio ni rebote
    assert max(values) < 1.0 and max(values) <= dialog_module._WAIT_CEILING  # el 100 % no lo pone la espera
    assert max(b - a for a, b in zip(values, values[1:])) < 0.02  # sin saltos
    fill = [dialog_module.finish_value(0.4, i * 0.02) for i in range(20)]
    assert fill[0] == 0.4 and fill[-1] == 1.0 and all(b >= a for a, b in zip(fill, fill[1:]))


def test_progress_bar_is_created_once_hidden_on_open_and_reused_every_run(env):
    d = env.dialog
    bar = d._progress
    assert not bar_visible(d) and d._bar_job is None and option(bar, "mode") == "determinate"
    assert bar.master is d and bar.master is not d._viewer  # del diálogo, no del visor
    env.op.fail = True  # 1.ª ejecución: error → oculta sin completar
    env.op.gate.set()
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.ERROR)
    assert not bar_visible(d) and d._bar_job is None and "Error" in option(d._message, "text")
    env.op.fail = False  # 2.ª: reintento tras el error; mismas instancias
    start_run(env)
    assert bar_visible(d) and d._progress is bar
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert wait_hidden(env) and d._progress is bar and d._bar_job is None


def test_progress_bar_advances_continuously_without_resets_while_working(env):
    d = env.dialog
    seen = []
    real_set = d._progress.set
    d._progress.set = lambda v: (seen.append(v), real_set(v))[1]
    start_run(env)
    end = time.monotonic() + 1.2
    while time.monotonic() < end:
        d.update()
        time.sleep(0.01)
    assert len(seen) > 20 and all(b >= a for a, b in zip(seen, seen[1:])) and seen[-1] < 1.0
    env.op.gate.set()


def test_progress_bar_completes_then_disappears_and_stays_hidden_while_reviewing(env):
    d = env.dialog
    seen = []
    real_set = d._progress.set
    d._progress.set = lambda v: (seen.append(v), real_set(v))[1]
    env.op.gate.set()
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert bar_visible(d) and d._bar_finish_t0 is not None  # completando el recorrido
    assert wait_hidden(env) and d._bar_job is None
    assert 1.0 in seen  # llegó al 100 % antes de ocultarse
    for _ in range(3):
        d._viewer.zoom_in()
        d._viewer.viewport.pan_by(-10, -10)
        d.state_changed()
        d.update()
        assert not bar_visible(d) and d._bar_job is None
    env.remove.run()  # con un resultado pendiente «Quitar fondo» no procede y no debe mostrar la barra
    d.update()
    assert not bar_visible(d)


def test_progress_bar_on_error_hides_without_completing(env):
    d = env.dialog
    seen = []
    real_set = d._progress.set
    d._progress.set = lambda v: (seen.append(v), real_set(v))[1]
    env.op.fail = True
    env.op.gate.set()
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.ERROR)
    assert not bar_visible(d) and d._bar_job is None and 1.0 not in seen
    assert "Error" in option(d._message, "text")


def test_progress_bar_keeps_running_when_cancel_is_pressed_during_rmbg(env, monkeypatch):
    monkeypatch.setattr(dialog_module, "play_warning_sound", lambda fallback=None: True)
    d = env.dialog
    start_run(env)
    env.remove.cancel()  # con RMBG trabajando solo avisa: la barra no se toca
    d.update()
    assert bar_visible(d) and d._bar_job is not None
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)


def test_progress_bar_is_centered_on_the_image_area_and_follows_resizes(env):
    d = env.dialog
    d.update()
    start_run(env)
    canvas, overlay = d._viewer.view_area, d._progress
    cx, cy = center_of(canvas)
    ox, oy = center_of(overlay)
    assert abs(ox - cx) <= 2 and abs(oy - cy) <= 2  # centrada horizontal y verticalmente
    assert abs(d._progress.winfo_width() - d._progress._apply_widget_scaling(dialog_module._BAR_WIDTH)) <= 2
    assert abs(d._progress.winfo_height() - d._progress._apply_widget_scaling(dialog_module._BAR_HEIGHT)) <= 2
    for geometry in ("760x600", "1200x900", "980x760"):  # redimensionar el visor
        d.geometry(geometry)
        d.update()
        time.sleep(0.15)
        d.update()
        cx, cy = center_of(canvas)
        ox, oy = center_of(overlay)
        assert abs(ox - cx) <= 2 and abs(oy - cy) <= 2
    env.op.gate.set()


def test_zoom_and_pan_do_not_move_the_bar_and_the_bar_does_not_move_the_viewer(env):
    d = env.dialog
    d.update()
    canvas = d._viewer.view_area
    size_before = (canvas.winfo_width(), canvas.winfo_height(), canvas.winfo_rooty())
    env.op.gate.set()
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    d.update()
    assert bar_visible(d)  # completando el recorrido: el zoom/paneo ya están permitidos
    before = center_of(d._progress)
    d._viewer.zoom_in()
    d._viewer.viewport.pan_by(-30, -20)
    d.update()
    after = center_of(d._progress)
    assert abs(before[0] - after[0]) <= 1 and abs(before[1] - after[1]) <= 1
    assert (canvas.winfo_width(), canvas.winfo_height(), canvas.winfo_rooty()) == size_before
    assert wait_hidden(env)
    assert (canvas.winfo_width(), canvas.winfo_height(), canvas.winfo_rooty()) == size_before
    d._viewer.fit_to_window()
    d.update()
    assert all(canvas.type(i) != "window" for i in canvas.find_all())  # la barra no es un elemento del canvas


def test_no_status_messages_anywhere_but_errors_are_still_reported(env):
    d = env.dialog
    texts = []
    real = d._message.configure
    d._message.configure = lambda **kw: (texts.append(kw.get("text")), real(**kw))[1]
    assert option(d._message, "text") == ""  # reposo: sin «Remove listo…»
    start_run(env)
    d.update()
    assert option(d._message, "text") == ""  # ni «Quitando fondo…»
    env.remove.show_progress(types.SimpleNamespace(stage="Inferencia", message="procesando", percent=35))
    d.update()
    assert option(d._message, "text") == ""  # ni textos de etapa
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert option(d._message, "text") == ""  # ni «Procesamiento completado…»
    assert all(not x for x in texts)  # en ningún momento hubo texto informativo
    env.remove.cancel()


def test_errors_are_still_notified_with_the_existing_mechanism(env):
    d = env.dialog
    env.op.fail = True
    env.op.gate.set()
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.ERROR)
    assert "Error" in option(d._message, "text") and not bar_visible(d)
    env.op.fail = False  # un reintento limpia el error y no deja texto informativo
    start_run(env)
    assert option(d._message, "text") == ""
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert option(d._message, "text") == ""


def test_there_is_no_opaque_card_only_the_bar_with_flat_ends(env):
    d = env.dialog
    assert not hasattr(d, "_progress_overlay") and d._progress.master is d
    assert option(d._progress, "corner_radius") == 0  # sin esquinas con el color del fondo
    start_run(env)
    placed = [w for w in d.winfo_children() if w.winfo_manager() == "place"]
    assert placed == [d._progress]  # nada más flota sobre el visor: ni tarjeta ni texto
    assert d._progress.winfo_width() <= d._progress._apply_widget_scaling(dialog_module._BAR_WIDTH) + 2
    env.op.gate.set()


def test_the_bar_never_reaches_the_image_that_lumine_receives(env):
    d = env.dialog
    env.op.gate.set()
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert d._progress.master is d  # ni el canvas ni el renderizador conocen la barra
    assert d._progress not in d._viewer.winfo_children()
    expected = env.doc.image.convert("RGBA")
    env.remove.ok()
    out = env.service.snapshot().image.convert("RGBA")
    assert out.size == expected.size and out.getchannel("A").getextrema() == (100, 100)
    assert out.convert("RGB").tobytes() == expected.convert("RGB").tobytes()  # píxeles RGB intactos


def test_closing_or_cancelling_leaves_no_bar_animation_running(env):
    d = env.dialog
    start_run(env)
    assert bar_visible(d) and d._bar_job is not None
    env.remove.close()  # cierre con tarea en curso
    assert not d._alive and d._bar_job is None
    env.op.gate.set()


def test_cancelling_during_the_final_fill_leaves_no_animation(env):
    d = env.dialog
    env.op.gate.set()
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert bar_visible(d) and d._bar_job is not None
    env.remove.cancel()
    assert not d._alive and d._bar_job is None


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


def never_ask(monkeypatch):
    monkeypatch.setattr(
        dialog_module, "ask_discard_changes",
        lambda parent: pytest.fail("no debía pedir confirmación: no hay cambios pendientes"),
    )


def finish_run(env):
    env.op.gate.set()
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)


def test_x_without_pending_changes_closes_directly_without_a_warning(env, monkeypatch):
    never_ask(monkeypatch)
    d = env.dialog
    d._on_close_request()  # es lo que ejecuta el protocolo WM_DELETE_WINDOW
    assert env.remove.state is RemoveState.CLOSED and not d._alive and lumine_free(env)
    assert env.main.snapshots == [] and env.service.snapshot().image is env.doc.image


def test_x_with_a_pending_result_asks_and_keep_editing_keeps_the_window_as_it_was(env, monkeypatch):
    finish_run(env)
    d, result, asked = env.dialog, env.remove.result, []
    monkeypatch.setattr(dialog_module, "ask_discard_changes", lambda parent: asked.append(parent) or False)
    d._on_close_request()
    assert asked == [d] and d._alive
    assert env.remove.state is RemoveState.COMPLETED and env.remove.result is result and env.remove.can_ok
    assert env.main.snapshots == [] and env.service.snapshot().image is env.doc.image
    assert env.design.interaction.workspace == "remove_background"


def test_x_with_a_pending_result_and_discard_acts_like_cancel(env, monkeypatch):
    finish_run(env)
    d = env.dialog
    monkeypatch.setattr(dialog_module, "ask_discard_changes", lambda parent: True)
    d._on_close_request()
    assert env.remove.state is RemoveState.CLOSED and not d._alive and lumine_free(env)
    assert env.main.snapshots == [] and env.service.snapshot().image is env.doc.image


def sounds(monkeypatch):
    played = []
    monkeypatch.setattr(dialog_module, "play_warning_sound", lambda fallback=None: played.append(fallback) or True)
    return played


def test_cancel_during_rmbg_only_plays_the_warning_sound(env, monkeypatch):
    never_ask(monkeypatch)
    played, d = sounds(monkeypatch), env.dialog
    start_run(env)
    texts_before, enabled_before = option(d._message, "text"), enabled(env)
    d._cancel_button.invoke()  # el botón real
    d.update()
    assert len(played) == 1
    assert d._alive and env.remove.state is RemoveState.PROCESSING
    assert option(d._message, "text") == texts_before == ""  # ni mensaje ni aviso escrito
    assert enabled(env) == enabled_before and bar_visible(d)
    assert [w for w in d.winfo_children() if isinstance(w, dialog_module.ctk.CTkToplevel)] == []  # ni diálogo
    env.op.gate.set()


def test_x_during_rmbg_only_plays_the_warning_sound(env, monkeypatch):
    never_ask(monkeypatch)
    played, d = sounds(monkeypatch), env.dialog
    start_run(env)
    d._on_close_request()  # es lo que ejecuta el protocolo WM_DELETE_WINDOW
    d.update()
    assert len(played) == 1 and d._alive and env.remove.state is RemoveState.PROCESSING
    assert option(d._message, "text") == "" and bar_visible(d)
    assert [w for w in d.winfo_children() if isinstance(w, dialog_module.ctk.CTkToplevel)] == []
    env.op.gate.set()


def test_processing_continues_and_finishes_after_cancel_and_x_attempts(env, monkeypatch):
    never_ask(monkeypatch)
    played, d = sounds(monkeypatch), env.dialog
    start_run(env)
    d._cancel_button.invoke()
    d._on_close_request()
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert len(played) == 2 and d._alive and env.op.calls == 1
    assert env.remove.result is not None and env.remove.can_ok and enabled(env) == (False, True, True)
    assert env.main.snapshots == [] and env.service.snapshot().image is env.doc.image  # nada aplicado sin OK


def test_the_alert_is_a_system_sound_and_never_raises(env, monkeypatch):
    d = env.dialog
    played = sounds(monkeypatch)
    d.alert()
    assert played == [d.bell]  # sonido del sistema; ``bell`` solo como respaldo


# ---- Remove como ventana hija de Lumine ----
def test_remove_is_a_child_window_of_lumine(env):
    d = env.dialog
    assert str(d.tk.call("wm", "transient", str(d))) == str(env.root)  # propia de Lumine: sin icono propio
    assert d.resizable() == (True, True)


windows_only = pytest.mark.skipif(sys.platform != "win32", reason="comportamiento de ventanas de Windows")


def settle(env, condition, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        env.root.update()
        if condition():
            return True
        time.sleep(0.02)
    return condition()


@windows_only
def test_remove_title_bar_has_maximize_but_no_minimize_button(env):
    import ctypes

    d = env.dialog
    d.update()
    settle(env, lambda: d._setup_job is None)
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(user32.GetParent(d.winfo_id()), -16) & 0xFFFFFFFF
    assert style & 0x00010000  # WS_MAXIMIZEBOX
    assert not style & 0x00020000  # WS_MINIMIZEBOX


@windows_only
def test_minimizing_lumine_with_remove_closed_is_untouched(env):
    d, root = env.dialog, env.root
    settle(env, lambda: d._setup_job is None)
    env.remove.close()
    root.iconify()
    assert settle(env, lambda: root.state() == "iconic")
    root.deiconify()
    assert settle(env, lambda: root.state() == "normal")  # el − de Lumine hace lo de siempre


@windows_only
def test_maximizing_and_restoring_remove_does_not_change_lumine(env):
    d, root = env.dialog, env.root
    root.update()
    settle(env, lambda: d._setup_job is None)
    lumine = (root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height(), root.state())
    before = (d.winfo_width(), d.winfo_height())
    d.state("zoomed")
    assert settle(env, lambda: d.state() == "zoomed")
    assert (root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height(), root.state()) == lumine
    d.state("normal")
    assert settle(env, lambda: d.state() == "normal")
    assert (d.winfo_width(), d.winfo_height()) == before  # vuelve a su tamaño anterior
    assert (root.winfo_x(), root.winfo_y(), root.winfo_width(), root.winfo_height(), root.state()) == lumine


def test_the_confirmation_dialog_returns_the_chosen_option(env):
    d = env.dialog
    for method, expected in (("_drop", True), ("_keep", False)):
        confirmation = dialog_module._DiscardChangesDialog(d)
        assert confirmation.discard is False
        getattr(confirmation, method)()
        assert confirmation.discard is expected
    assert d._alive and env.remove.state is RemoveState.READY


def test_destroy_is_idempotent_and_late_calls_do_nothing(env):
    d = env.dialog
    env.remove.close()
    d.destroy()
    d.state_changed()
    d.show_status("tarde", dialog_module.StatusLevel.INFO)
    d.set_busy(True)
    d.show_image(env.doc.image, keep_view=True)
    assert not d._alive and lumine_free(env)


def test_closing_right_after_opening_cancels_the_deferred_window_setup(env):
    d = env.dialog
    assert d._setup_job is not None  # la preparación modal sigue pendiente justo tras abrir
    env.remove.close()
    assert not d._alive and d._setup_job is None
