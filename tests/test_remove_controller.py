"""Sesión de Remove (RemoveController) con hilos reales y una «IA» controlable. Sin Tk."""
import threading
import time

import pytest
from PIL import Image

from app.controllers.design_controller import DesignController, StatusLevel
from app.interaction import Action, Scope
from app.services.processing_service import ProcessingService
from app.services.task_runner import BackgroundTaskRunner
from app.services.tool_registry import ToolRegistry
from core.design_engine import DesignEngine
from core.operation import ImageOperation
from core.exceptions import StalePreviewError
from tools.remove import RemoveController, RemoveState


class FakeIO:
    def load(self, path):
        return Image.new("RGB", (6, 4), "white")

    def save(self, image, path):
        return path

    def unique_output_path(self, directory, stem):
        return directory / stem


class GatedRemover(ImageOperation):
    """Sustituto de RMBG: espera a que el test lo suelte; puede fallar."""

    name = "remove_background"

    def __init__(self):
        self.gate = threading.Event()
        self.started = threading.Event()
        self.calls = 0
        self.fail = False

    @property
    def label(self):
        return "Fondo"

    def apply(self, image):
        return self.apply_with_progress(image, None)

    def apply_with_progress(self, image, reporter):
        self.calls += 1
        if reporter is not None:
            reporter.report("Inferencia", 0.35, "procesando")
        self.started.set()
        assert self.gate.wait(5), "el test no soltó la IA"
        if self.fail:
            raise RuntimeError("modelo caído")
        out = image.convert("RGBA")
        out.putalpha(Image.new("L", image.size, 100))
        return out


class MainView:
    """Vista principal falsa: lo que NO debe recibir nada de Remove."""

    def __init__(self):
        self.statuses, self.busy, self.progress, self.snapshots = [], [], [], []

    def show_snapshot(self, snapshot):
        self.snapshots.append(snapshot)

    def show_status(self, message, level):
        self.statuses.append((message, level))

    def set_busy(self, busy):
        self.busy.append(busy)

    def show_progress(self, event):
        self.progress.append(event)


class RemoveViewFake:
    """Doble de la ventana: solo lo que define ``RemoveView`` (sin show_progress ni confirm_exit)."""

    def __init__(self):
        self.images, self.statuses, self.busy = [], [], []
        self.state_changes = 0
        self.closed = 0
        self.alerts = 0
        self.after_close = []  # cualquier llamada posterior al cierre (no debe haber)

    def _guard(self, what):
        if self.closed:
            self.after_close.append(what)

    def show_image(self, image, *, keep_view):
        self._guard("show_image")
        self.images.append((image, keep_view))

    def show_status(self, message, level):
        self._guard("show_status")
        self.statuses.append((message, level))

    def set_busy(self, busy):
        self._guard("set_busy")
        self.busy.append(busy)

    def state_changed(self):
        self._guard("state_changed")
        self.state_changes += 1

    def alert(self):
        self._guard("alert")
        self.alerts += 1

    def close(self):
        self.closed += 1


class Env:
    pass


@pytest.fixture
def env(tmp_path):
    e = Env()
    e.op = GatedRemover()
    registry = ToolRegistry()
    registry.register("remove_background", lambda: e.op)
    e.service = ProcessingService(DesignEngine(FakeIO()), registry, tmp_path)
    e.design = DesignController(e.service, BackgroundTaskRunner())
    e.main = MainView()
    e.design.attach_view(e.main)
    e.service.open_image(tmp_path / "foto.png")
    e.doc = e.service.snapshot()
    e.view = RemoveViewFake()
    e.remove = RemoveController(e.design)
    return e


def opened(env):
    assert env.remove.open()
    env.remove.attach_view(env.view)
    return env


def pump(env, condition, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        env.design.process_pending()
        if condition():
            return
        time.sleep(0.003)
    raise AssertionError("tiempo agotado esperando a la tarea")


def run_to_completion(env):
    env.op.gate.set()
    assert env.remove.run()
    pump(env, lambda: env.remove.state is not RemoveState.PROCESSING)


def revision(env):
    return env.service._engine._state.revision


def document_untouched(env):
    snap = env.service.snapshot()
    return snap.image is env.doc.image and snap.operations == () and revision(env) == 1


def lumine_free(env):
    return env.design.interaction.workspace is None and all(env.design.can(a) for a in Action)


# ---- 1 y 2: abrir muestra el original y no procesa ----
def test_open_shows_the_original_unprocessed_and_does_not_run_rmbg(env):
    opened(env)
    assert env.remove.state is RemoveState.READY
    assert env.view.images == [(env.doc.image, False)]
    assert "Remove listo" in env.view.statuses[0][0]
    assert env.op.calls == 0 and not env.design.is_busy
    assert env.design.interaction.workspace == "remove_background"
    assert document_untouched(env) and env.main.snapshots == []
    assert env.remove.can_run and env.remove.can_cancel and not env.remove.can_ok
    time.sleep(0.05)
    env.design.process_pending()
    assert env.op.calls == 0


def test_open_without_image_is_refused_and_does_not_block_lumine(tmp_path):
    registry = ToolRegistry()
    design = DesignController(ProcessingService(DesignEngine(FakeIO()), registry, tmp_path), BackgroundTaskRunner())
    main = MainView()
    design.attach_view(main)
    remove = RemoveController(design)
    assert remove.open() is False
    assert design.interaction.workspace is None and design.can(Action.OPEN_IMAGE)
    assert main.statuses and main.statuses[-1][1] is StatusLevel.WARNING


def test_open_refused_while_busy_or_with_another_session(env):
    env.design.interaction.begin("sharpen")
    assert RemoveController(env.design).open() is False
    env.design.interaction.end()
    assert opened(env)
    assert RemoveController(env.design).open() is False
    assert env.design.interaction.workspace == "remove_background"


# ---- Quitar fondo ----
def test_run_executes_rmbg_and_shows_a_preview_without_touching_the_document(env):
    opened(env)
    assert env.remove.run() is True
    assert env.remove.state is RemoveState.PROCESSING
    assert env.op.started.wait(5)
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    shown, keep = env.view.images[-1]
    assert shown is env.remove.result.image and keep is True and shown.mode == "RGBA"
    assert document_untouched(env) and env.main.snapshots == []
    assert env.remove.can_ok and env.remove.can_cancel and not env.remove.can_run
    assert "Procesamiento completado" in env.view.statuses[-1][0]


def test_run_twice_is_ignored(env):
    opened(env)
    assert env.remove.run()
    assert env.remove.run() is False
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert env.op.calls == 1
    assert env.remove.run() is False  # con resultado en pantalla: primero OK o Cancelar


def test_while_processing_buttons_and_navigation_are_locked(env):
    opened(env)
    inter = env.design.interaction
    assert inter.can(Action.ZOOM, Scope.TOOL) and inter.can(Action.PAN, Scope.TOOL)
    env.remove.run()
    assert env.op.started.wait(5)
    assert not inter.can(Action.ZOOM, Scope.TOOL) and not inter.can(Action.PAN, Scope.TOOL)
    assert not any(inter.can(a) for a in Action)  # y lo principal, también
    assert not env.remove.can_run and not env.remove.can_ok and env.remove.can_cancel
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert inter.can(Action.ZOOM, Scope.TOOL) and inter.can(Action.PAN, Scope.TOOL)


# ---- Mensajes y progreso ----
def test_status_messages_follow_the_stages_and_end_with_completed(env):
    opened(env)
    run_to_completion(env)
    texts = [m for m, _ in env.view.statuses]
    assert "Eliminando fondo…" in texts
    assert texts.index("Eliminando fondo…") < texts.index(env.view.statuses[-1][0])
    assert env.view.busy == [True, False]
    assert env.main.progress == [] and env.main.busy == []
    assert not any("Eliminando" in m or "Quitando" in m for m, _ in env.main.statuses)


def test_stage_messages_cover_the_real_rmbg_stage_labels():
    from tools import background_remover as br
    from tools.remove import controller as rc

    labels = {label for label, _ in br._STAGES.values()}
    assert set(rc._STAGE_MESSAGES) <= labels  # si renombran una etapa, el mensaje no queda huérfano


def test_progress_text_is_not_repeated(env):
    from core.progress import ProgressEvent

    opened(env)
    before = len(env.view.statuses)
    for _ in range(3):
        env.remove.show_progress(ProgressEvent("Inferencia", 0.4, "x"))
    assert len(env.view.statuses) == before + 1 and env.view.statuses[-1][0] == "Eliminando fondo…"
    env.remove.show_progress(ProgressEvent("Imagen", 0.1, "x"))
    assert env.view.statuses[-1][0] == "Preparando imagen…"


# ---- OK ----
def test_ok_commits_updates_lumine_and_closes(env):
    opened(env)
    run_to_completion(env)
    result = env.remove.result
    assert env.remove.ok() is True
    assert env.remove.state is RemoveState.CLOSED and env.view.closed == 1
    snap = env.service.snapshot()
    assert snap.image is result.image and snap.image.mode == "RGBA"
    assert len(snap.operations) == 1 and "remove_background" in repr(snap.operations[0]) + getattr(snap.operations[0], "name", "")
    assert revision(env) == 2
    assert len(env.main.snapshots) == 1 and env.main.snapshots[0].image is result.image
    assert lumine_free(env)
    assert env.view.after_close == []


def test_ok_is_refused_without_result_and_while_processing(env):
    opened(env)
    assert env.remove.ok() is False and env.remove.state is RemoveState.READY and document_untouched(env)
    env.remove.run()
    assert env.op.started.wait(5)
    assert env.remove.can_ok is False and env.remove.ok() is False
    assert env.remove.state is RemoveState.PROCESSING and document_untouched(env)
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert env.remove.can_ok


def test_ok_twice_commits_once(env):
    opened(env)
    run_to_completion(env)
    assert env.remove.ok() is True
    assert env.remove.ok() is False
    assert revision(env) == 2 and len(env.main.snapshots) == 1


def test_stale_result_is_rejected_by_commit_and_the_session_stays_open(env, tmp_path):
    opened(env)
    run_to_completion(env)
    env.service.open_image(tmp_path / "otra.png")  # el documento cambió por detrás
    other = env.service.snapshot()
    assert env.remove.ok() is False
    assert env.remove.state is RemoveState.ERROR and env.view.closed == 0
    assert env.service.snapshot().image is other.image  # nada aplicado
    assert env.view.statuses[-1][1] is StatusLevel.ERROR
    assert env.view.images[-1][0] is env.remove._original
    assert env.design.interaction.workspace == "remove_background"
    assert env.remove.result is None and env.remove.can_ok is False
    assert env.remove.can_cancel and env.remove.can_run
    env.remove.cancel()
    assert env.remove.state is RemoveState.CLOSED and lumine_free(env)


def test_commit_failure_keeps_the_document_intact(env, monkeypatch):
    opened(env)
    run_to_completion(env)

    def boom(preview):
        raise RuntimeError("disco")

    monkeypatch.setattr(env.service, "commit_preview", boom)
    assert env.remove.ok() is False
    assert env.remove.state is RemoveState.ERROR and env.view.closed == 0
    assert document_untouched(env) and env.main.snapshots == []


def test_design_commit_preview_returns_none_while_processing(env):
    opened(env)
    run_to_completion(env)
    result = env.remove.result
    env.design.interaction.begin("sharpen")
    assert env.design.commit_preview(result, "remove_background") is None
    env.design.interaction.end()
    assert revision(env) == 1


# ---- Cancelar ----
def test_cancel_in_ready_closes_without_changes(env):
    opened(env)
    env.remove.cancel()
    assert env.remove.state is RemoveState.CLOSED and env.view.closed == 1
    assert lumine_free(env) and document_untouched(env) and env.main.snapshots == []


def test_cancel_with_a_result_discards_and_closes(env):
    opened(env)
    run_to_completion(env)
    env.remove.cancel()
    assert env.remove.state is RemoveState.CLOSED and env.remove.result is None
    assert document_untouched(env) and env.main.snapshots == []
    assert lumine_free(env) and env.view.closed == 1


def test_cancel_while_processing_only_alerts_and_the_ai_keeps_working(env):
    opened(env)
    env.remove.run()
    assert env.op.started.wait(5)
    snapshot = (list(env.view.statuses), list(env.view.images), env.view.state_changes, list(env.view.busy))
    env.remove.cancel()
    assert env.view.alerts == 1
    # nada más: ni estado, ni mensajes, ni imagen, ni repintado de botones, ni cierre
    assert env.remove.state is RemoveState.PROCESSING and env.view.closed == 0
    assert (list(env.view.statuses), list(env.view.images), env.view.state_changes, list(env.view.busy)) == snapshot
    assert env.remove.can_cancel and env.remove.ok() is False
    assert env.design.interaction.workspace == "remove_background"
    assert document_untouched(env) and env.main.statuses == [] and env.main.snapshots == []


def test_processing_continues_and_completes_after_cancel_attempts(env):
    opened(env)
    env.remove.run()
    assert env.op.started.wait(5)
    env.remove.cancel()
    env.remove.cancel()
    assert env.view.alerts == 2 and env.op.calls == 1
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert env.remove.result is not None and env.remove.can_ok and env.view.closed == 0
    assert env.view.images[-1][0] is env.remove.result.image
    assert env.view.alerts == 2  # al terminar no suena nada más
    assert env.remove.ok() is True and revision(env) == 2 and env.view.after_close == []


def test_a_failed_run_after_cancel_attempts_is_a_normal_error_and_stays_usable(env):
    opened(env)
    env.op.fail = True
    env.remove.run()
    assert env.op.started.wait(5)
    env.remove.cancel()
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.ERROR)
    assert env.view.statuses[-1][1] is StatusLevel.ERROR and env.view.closed == 0
    assert env.remove.can_run and env.remove.can_cancel and document_untouched(env)
    env.remove.cancel()  # ya sin tarea: Cancelar vuelve a funcionar y cierra
    assert env.remove.state is RemoveState.CLOSED and lumine_free(env) and env.view.alerts == 1


def test_cancel_only_alerts_while_processing_and_works_normally_otherwise(env):
    opened(env)
    run_to_completion(env)
    env.remove.cancel()
    assert env.view.alerts == 0 and env.remove.state is RemoveState.CLOSED


# ---- Cierre ----
def test_refuse_close_warns_and_never_closes(env):
    opened(env)
    env.remove.refuse_close()
    assert env.view.closed == 0 and env.remove.state is RemoveState.READY
    assert env.view.statuses[-1][1] is StatusLevel.WARNING and "Cancelar" in env.view.statuses[-1][0]
    env.remove.run()
    assert env.op.started.wait(5)
    env.remove.refuse_close()
    assert env.view.closed == 0 and env.remove.state is RemoveState.PROCESSING
    assert env.design.interaction.workspace == "remove_background"
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    env.remove.refuse_close()
    assert env.view.closed == 0 and env.remove.result is not None


def test_the_session_never_closes_with_an_active_task(env):
    opened(env)
    env.remove.run()
    assert env.op.started.wait(5)
    env.remove.cancel()
    assert env.remove.request_close(never_asked) is False
    env.remove.refuse_close()
    assert env.view.closed == 0 and env.design.interaction.workspace == "remove_background"
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)


def test_close_is_idempotent_and_ignores_late_events(env):
    from core.progress import ProgressEvent

    opened(env)
    env.remove.cancel()
    env.remove.cancel()
    env.remove.close()
    env.remove.refuse_close()
    assert env.remove.run() is False and env.remove.ok() is False
    env.remove.show_progress(ProgressEvent("Inferencia", 0.4, "x"))
    env.remove.show_status("tarde", StatusLevel.INFO)
    env.remove.set_busy(True)
    assert env.view.closed == 1 and env.view.after_close == []


def test_a_failing_window_close_still_unlocks_lumine(env):
    opened(env)

    def boom():
        raise RuntimeError("Tk falló")

    env.view.close = boom
    env.remove.cancel()
    assert env.remove.state is RemoveState.CLOSED and lumine_free(env)


def test_repeated_sessions_leave_no_threads_or_locks(env):
    base = threading.active_count()
    for _ in range(3):
        remove = RemoveController(env.design)
        assert remove.open()
        remove.attach_view(RemoveViewFake())
        env.op.gate.set()
        assert remove.run()
        pump(env, lambda: remove.state is RemoveState.COMPLETED)
        remove.cancel()
        assert lumine_free(env)
    time.sleep(0.1)
    assert threading.active_count() <= base + 1 and document_untouched(env)


def test_the_main_window_gets_nothing_from_a_remove_session_except_the_final_commit(env):
    opened(env)
    run_to_completion(env)
    assert env.main.snapshots == [] and env.main.progress == [] and env.main.busy == []
    env.remove.ok()
    assert len(env.main.snapshots) == 1 and env.main.progress == []


# ---- La X de Remove: advertencia solo con cambios pendientes (request_close) ----
def never_asked():
    raise AssertionError("no debía pedir confirmación: no hay cambios pendientes")


def test_pending_changes_are_exactly_a_result_waiting_for_ok(env):
    opened(env)
    assert env.remove.has_pending_changes is False
    env.remove.run()
    assert env.op.started.wait(5)
    assert env.remove.has_pending_changes is False  # procesando: aún no hay nada que confirmar
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert env.remove.has_pending_changes is True and env.remove.can_ok
    env.remove.ok()
    assert env.remove.has_pending_changes is False  # confirmado: ya vive en el documento


def test_x_without_pending_changes_closes_directly_and_does_not_ask(env):
    opened(env)
    assert env.remove.request_close(never_asked) is True
    assert env.remove.state is RemoveState.CLOSED and env.view.closed == 1
    assert document_untouched(env) and lumine_free(env)


def test_x_after_an_error_or_a_discarded_result_closes_without_asking(env):
    opened(env)
    env.op.fail = True
    env.op.gate.set()
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.ERROR)
    assert env.remove.has_pending_changes is False
    assert env.remove.request_close(never_asked) is True
    assert env.remove.state is RemoveState.CLOSED and document_untouched(env)


def test_x_with_a_pending_result_asks_and_keep_editing_leaves_everything_as_it_was(env):
    opened(env)
    run_to_completion(env)
    result, closed_before, statuses = env.remove.result, env.view.closed, list(env.view.statuses)
    asked = []
    assert env.remove.request_close(lambda: asked.append(1) or False) is False
    assert asked == [1]
    assert env.remove.state is RemoveState.COMPLETED and env.remove.result is result
    assert env.remove.can_ok and env.view.closed == closed_before == 0
    assert env.view.statuses == statuses and document_untouched(env)
    assert env.design.interaction.workspace == "remove_background"
    assert env.remove.ok() is True  # y se puede seguir: confirmar sigue funcionando
    assert env.service.snapshot().operations != ()


def test_x_discarding_a_pending_result_behaves_like_cancel(env):
    opened(env)
    run_to_completion(env)
    assert env.remove.request_close(lambda: True) is True
    assert env.remove.state is RemoveState.CLOSED and env.remove.result is None
    assert env.view.closed == 1 and env.view.after_close == []
    assert document_untouched(env) and env.main.snapshots == [] and lumine_free(env)


def test_x_never_loses_what_ok_already_confirmed(env):
    opened(env)
    run_to_completion(env)
    assert env.remove.ok() is True
    confirmed = env.service.snapshot()
    assert confirmed.operations != () and revision(env) == 2
    assert env.remove.request_close(never_asked) is True  # sesión ya cerrada: no hace ni pregunta nada
    # Remove se abre de nuevo: es otra sesión; lo confirmado antes NO cuenta como cambio pendiente.
    again = RemoveController(env.design)
    view = RemoveViewFake()
    assert again.open()
    again.attach_view(view)
    assert again.has_pending_changes is False
    assert again.request_close(never_asked) is True
    snap = env.service.snapshot()
    assert snap.image is confirmed.image and snap.operations == confirmed.operations and revision(env) == 2


def test_new_edits_after_an_error_are_detected_again(env):
    opened(env)
    env.op.fail = True
    env.op.gate.set()
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.ERROR)
    assert env.remove.has_pending_changes is False
    env.op.fail = False
    assert env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert env.remove.has_pending_changes is True
    asked = []
    assert env.remove.request_close(lambda: asked.append(1) or False) is False and asked == [1]


def test_x_while_processing_only_alerts_does_not_ask_and_processing_continues(env):
    opened(env)
    env.remove.run()
    assert env.op.started.wait(5)
    snapshot = (list(env.view.statuses), list(env.view.images), env.view.state_changes)
    assert env.remove.request_close(never_asked) is False
    assert env.view.alerts == 1 and env.view.closed == 0
    assert env.remove.state is RemoveState.PROCESSING
    assert (list(env.view.statuses), list(env.view.images), env.view.state_changes) == snapshot
    assert env.design.interaction.workspace == "remove_background"
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert env.remove.result is not None and env.view.alerts == 1 and env.op.calls == 1
    # terminada la IA, la X vuelve a ser la normal: con resultado pendiente pregunta
    assert env.remove.request_close(lambda: False) is False and env.view.alerts == 1


def test_cancel_and_x_attempts_together_do_not_interrupt_the_task(env):
    opened(env)
    env.remove.run()
    assert env.op.started.wait(5)
    env.remove.cancel()
    assert env.remove.request_close(never_asked) is False
    env.remove.cancel()
    assert env.view.alerts == 3 and env.remove.state is RemoveState.PROCESSING
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert env.remove.ok() is True and document_untouched(env) is False and revision(env) == 2


def test_the_existing_cancel_button_is_unchanged_by_request_close(env):
    opened(env)
    run_to_completion(env)
    env.remove.cancel()  # Cancelar nunca pregunta, haya o no cambios pendientes
    assert env.remove.state is RemoveState.CLOSED and document_untouched(env) and lumine_free(env)
