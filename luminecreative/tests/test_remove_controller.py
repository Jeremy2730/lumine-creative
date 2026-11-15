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
    def __init__(self, confirm=True):
        self.images, self.statuses, self.progress, self.busy = [], [], [], []
        self.state_changes = 0
        self.confirm_calls = []
        self.confirm_answer = confirm
        self.closed = 0
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

    def show_progress(self, event):
        self._guard("show_progress")
        self.progress.append(event)

    def set_busy(self, busy):
        self._guard("set_busy")
        self.busy.append(busy)

    def state_changed(self):
        self._guard("state_changed")
        self.state_changes += 1

    def confirm_exit(self, *, processing):
        self.confirm_calls.append(processing)
        return self.confirm_answer

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


def document_untouched(env):
    snap = env.service.snapshot()
    return snap.image is env.doc.image and snap.operations == () and env.service._engine._state.revision == 1


# ---- 1 y 2: abrir muestra el original y no procesa ----
def test_open_shows_the_original_unprocessed_and_does_not_run_rmbg(env):
    opened(env)
    assert env.remove.state is RemoveState.READY
    assert env.view.images == [(env.doc.image, False)]  # la misma imagen, sin procesar
    assert env.op.calls == 0 and not env.design.is_busy
    assert env.design.interaction.workspace == "remove_background"
    assert document_untouched(env) and env.main.snapshots == []
    time.sleep(0.05)
    env.design.process_pending()
    assert env.op.calls == 0  # ni siquiera después de un rato: nadie lo lanzó


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
    assert RemoveController(env.design).open() is False  # ya hay un espacio abierto
    assert env.design.interaction.workspace == "remove_background"


# ---- 3, 4 y 5: Quitar fondo ejecuta; se bloquea; se recupera ----
def test_run_executes_rmbg_and_shows_a_preview_without_touching_the_document(env):
    opened(env)
    assert env.remove.run() is True
    assert env.remove.state is RemoveState.PROCESSING
    assert env.op.started.wait(5)
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert env.op.calls == 1
    shown, keep = env.view.images[-1]
    assert shown is env.remove.result.image and keep is True and shown.mode == "RGBA"
    assert document_untouched(env)  # nada confirmado en el documento principal
    assert env.main.snapshots == []


def test_run_twice_is_ignored(env):
    opened(env)
    assert env.remove.run()
    assert env.remove.run() is False
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert env.op.calls == 1
    assert env.remove.run() is False  # COMPLETED: primero hay que descartar


def test_while_processing_incompatible_interactions_are_blocked(env):
    opened(env)
    inter = env.design.interaction
    assert inter.can(Action.ZOOM, Scope.TOOL) and inter.can(Action.PAN, Scope.TOOL)  # en reposo, libres
    env.remove.run()
    assert env.op.started.wait(5)
    assert not inter.can(Action.ZOOM, Scope.TOOL) and not inter.can(Action.PAN, Scope.TOOL)
    assert not env.remove.can_interact(Action.ZOOM)
    assert not any(inter.can(a) for a in Action)  # y lo principal, también
    assert env.remove.can_run is False and env.remove.can_exit is True and env.remove.can_cancel is True
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)


def test_when_finished_the_allowed_interactions_come_back(env):
    opened(env)
    run_to_completion(env)
    inter = env.design.interaction
    assert inter.can(Action.ZOOM, Scope.TOOL) and inter.can(Action.PAN, Scope.TOOL)
    assert env.remove.can_cancel and env.remove.can_exit and not env.remove.can_run
    assert not inter.can(Action.OPEN_IMAGE)  # lo principal sigue bloqueado hasta salir


def test_progress_and_status_go_to_remove_not_to_the_main_window(env):
    opened(env)
    run_to_completion(env)
    assert [e.stage for e in env.view.progress] == ["Inferencia"]
    assert env.view.busy == [True, False]
    assert env.main.progress == [] and env.main.busy == []
    assert not any("Quitando" in m for m, _ in env.main.statuses)
    assert any("Quitando" in m for m, _ in env.view.statuses)


# ---- 6: Cancelar ----
def test_cancel_while_processing_discards_the_result_when_it_arrives(env):
    opened(env)
    env.remove.run()
    assert env.op.started.wait(5)
    env.remove.cancel()
    # Honestidad: la IA sigue ejecutándose, así que NO se declara cancelada todavía.
    assert env.remove.state is RemoveState.PROCESSING and env.remove.cancel_requested
    assert env.remove.can_cancel is False
    assert "no se puede interrumpir" in env.view.statuses[-1][0]
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.CANCELLED)
    assert env.remove.result is None
    assert env.view.images[-1] == (env.doc.image, True)  # vuelve a verse el original
    assert document_untouched(env)
    assert env.design.interaction.can(Action.ZOOM, Scope.TOOL)  # no queda bloqueado


def test_cancel_with_a_result_on_screen_discards_it(env):
    opened(env)
    run_to_completion(env)
    assert env.remove.result is not None
    env.remove.cancel()
    assert env.remove.state is RemoveState.CANCELLED and env.remove.result is None
    assert env.view.images[-1] == (env.doc.image, True)
    assert document_untouched(env)
    assert env.remove.can_run  # se puede volver a procesar


def test_cancel_when_there_is_nothing_to_discard_does_nothing(env):
    opened(env)
    assert env.remove.can_cancel is False
    changes = env.view.state_changes
    env.remove.cancel()
    assert env.remove.state is RemoveState.READY and env.view.state_changes == changes


def test_a_cancelled_run_can_be_repeated_and_applies_nothing_old(env):
    opened(env)
    env.remove.run()
    env.op.started.wait(5)
    env.remove.cancel()
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.CANCELLED)
    assert env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert env.op.calls == 2 and env.remove.result is not None and document_untouched(env)


# ---- 7: Salir ----
def test_exit_from_ready_closes_and_returns_control_to_lumine(env):
    opened(env)
    env.remove.request_exit()
    assert env.remove.state is RemoveState.CLOSED
    assert env.view.closed == 1 and env.view.confirm_calls == []  # sin nada que perder: sin pregunta
    assert env.design.interaction.workspace is None
    assert all(env.design.can(a) for a in Action)
    assert document_untouched(env)


def test_exit_with_a_result_asks_first(env):
    opened(env)
    run_to_completion(env)
    env.view.confirm_answer = False
    env.remove.request_exit()
    assert env.view.confirm_calls == [False] and env.remove.state is RemoveState.COMPLETED
    assert env.view.closed == 0 and env.remove.result is not None  # no se perdió por accidente
    env.view.confirm_answer = True
    env.remove.request_exit()
    assert env.remove.state is RemoveState.CLOSED and env.view.closed == 1
    assert env.remove.result is None and document_untouched(env)


def test_exit_while_processing_waits_for_the_inference_then_closes(env):
    opened(env)
    env.remove.run()
    assert env.op.started.wait(5)
    env.view.confirm_answer = False
    env.remove.request_exit()
    assert env.view.confirm_calls == [True] and env.remove.state is RemoveState.PROCESSING
    assert not env.remove.exit_requested  # el usuario dijo que no
    env.view.confirm_answer = True
    env.remove.request_exit()
    assert env.remove.exit_requested and env.view.closed == 0  # la IA sigue: la ventana también
    assert env.remove.can_exit is False and env.design.interaction.workspace == "remove_background"
    env.remove.request_exit()  # otro intento: se ignora (sin doble cierre ni doble pregunta)
    assert env.view.confirm_calls == [True, True]
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.CLOSED)
    assert env.view.closed == 1
    assert env.design.interaction.workspace is None and not env.design.is_busy
    assert env.remove.result is None and document_untouched(env)
    assert env.view.after_close == []  # nada tocó la ventana después de cerrarla


def test_close_is_idempotent_and_ignores_late_events(env):
    opened(env)
    env.remove.request_exit()
    env.remove.request_exit()
    env.remove.close()
    env.remove.cancel()
    assert env.remove.run() is False
    env.remove.show_progress(object())
    env.remove.show_status("tarde", StatusLevel.INFO)
    env.remove.set_busy(True)
    assert env.view.closed == 1 and env.view.after_close == []


def test_a_failing_window_close_still_unlocks_lumine(env):
    opened(env)

    def boom():
        raise RuntimeError("Tk falló")

    env.view.close = boom
    env.remove.request_exit()
    assert env.remove.state is RemoveState.CLOSED
    assert env.design.interaction.workspace is None and env.design.can(Action.OPEN_IMAGE)


# ---- 8: errores ----
def test_error_leaves_remove_usable_and_not_blocked(env):
    opened(env)
    env.op.fail = True
    env.op.gate.set()
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.ERROR)
    inter = env.design.interaction
    assert inter.can(Action.ZOOM, Scope.TOOL) and not inter.is_processing
    assert env.remove.can_run and env.remove.can_exit and not env.remove.can_cancel
    assert env.view.statuses[-1][1] is StatusLevel.ERROR  # el error no se pierde en silencio
    assert env.view.busy[-1] is False and document_untouched(env)
    # reintento
    env.op.fail = False
    env.remove.run()
    pump(env, lambda: env.remove.state is RemoveState.COMPLETED)
    assert env.remove.result is not None


def test_error_after_cancel_request_is_reported_not_swallowed(env):
    opened(env)
    env.op.fail = True
    env.remove.run()
    env.op.started.wait(5)
    env.remove.cancel()
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.ERROR)
    assert env.view.statuses[-1][1] is StatusLevel.ERROR and env.remove.cancel_requested is False


def test_error_while_exit_was_requested_still_closes(env):
    opened(env)
    env.op.fail = True
    env.remove.run()
    env.op.started.wait(5)
    env.remove.request_exit()
    env.op.gate.set()
    pump(env, lambda: env.remove.state is RemoveState.CLOSED)
    assert env.view.closed == 1 and env.design.interaction.workspace is None
    assert env.design.interaction.state.value == "error"  # el fallo quedó registrado, sin bloquear nada
    assert env.design.can(Action.OPEN_IMAGE)


# ---- 9: entrar y salir varias veces ----
def test_entering_and_leaving_many_times_leaves_no_threads_or_locks(env):
    baseline = threading.active_count()
    for i in range(6):
        remove = RemoveController(env.design)
        view = RemoveViewFake()
        assert remove.open()
        remove.attach_view(view)
        env.op.gate.set()
        if i % 3 == 0:  # una de cada tres sesiones procesa de verdad
            remove.run()
            end = time.monotonic() + 5
            while remove.state is RemoveState.PROCESSING and time.monotonic() < end:
                env.design.process_pending()
                time.sleep(0.003)
            if i % 2 == 0:
                remove.cancel()  # descarta el resultado; las impares salen con el resultado en pantalla
        view.confirm_answer = True
        remove.request_exit()
        assert remove.state is RemoveState.CLOSED and view.closed == 1 and view.after_close == []
        assert env.design.interaction.workspace is None
        assert env.design.interaction.state.value == "idle" and all(env.design.can(a) for a in Action)
    deadline = time.monotonic() + 2
    while threading.active_count() > baseline and time.monotonic() < deadline:
        time.sleep(0.01)
    assert threading.active_count() <= baseline  # ningún hilo de trabajo quedó vivo
    assert document_untouched(env)


# ---- compatibilidad de DesignController ----
def test_run_tool_without_sink_still_reports_to_the_main_view(env):
    env.op.gate.set()
    env.design.run_tool("remove_background")
    pump(env, lambda: bool(env.main.snapshots))
    assert env.main.busy == [True, False]
    assert [e.stage for e in env.main.progress] == ["Inferencia"]
    assert env.main.snapshots[-1].operations[0].name == "remove_background"  # este camino SÍ confirma


def test_preview_commit_path_leaves_the_engine_revision_alone(env):
    opened(env)
    run_to_completion(env)
    assert env.remove.result.base_revision == env.service._engine._state.revision
