"""tests/test_interaction_state.py

Responsabilidad:
    - Pruebas del estado central de interacción (app/interaction.py) y de su
      integración con DesignController: transiciones IDLE/PROCESSING/ERROR,
      política por herramienta (Remove bloquea todo el editor; Tamaño y
      resolución y el resto conservan el comportamiento heredado), liberación
      de bloqueos al terminar o fallar, y que una operación fallida no
      altere el documento.

No conoce:
    - Ventanas ni Tk: no requiere display.
"""
import threading
import time

import pytest
from PIL import Image

from app.controllers.design_controller import DesignController, StatusLevel
from app.interaction import (
    DEFAULT_POLICY,
    FULL_LOCK,
    LEGACY_LOCK,
    TOOL_POLICIES,
    Action,
    AppState,
    InteractionState,
)
from app.services.processing_service import ProcessingService
from app.services.task_runner import BackgroundTaskRunner
from app.services.tool_registry import ToolRegistry
from core.design_engine import DesignEngine
from core.models import ProcessingState
from tools.background_remover import BackgroundRemover
from tools.comic_effect import ComicEffect
from tools.image_loader import ImageLoader
from tools.image_sharpener import ImageSharpener

ALL = set(Action)
LEGACY_BLOCKED = {Action.OPEN_IMAGE, Action.SAVE, Action.OPEN_TOOL}


# ------------------------------------------------------------------ estado puro
def test_everything_is_allowed_when_idle_and_after_error():
    state = InteractionState()
    assert state.state is AppState.IDLE and all(state.can(a) for a in Action)
    state.begin("remove_background")
    state.fail()
    assert state.state is AppState.ERROR and all(state.can(a) for a in Action)  # nunca bloqueada


def test_transitions_and_rejection_of_a_second_task():
    state = InteractionState()
    assert state.begin("remove_background") is True
    assert state.is_processing and state.active_tool == "remove_background"
    assert state.begin("sharpen") is False and state.active_tool == "remove_background"
    state.end()
    assert state.state is AppState.IDLE and state.active_tool is None
    state.begin("sharpen")
    state.fail()
    assert state.state is AppState.ERROR
    assert state.begin("sharpen") is True  # el siguiente intento sale de ERROR
    state.end()
    state.end()  # sin tarea: no hace nada
    state.recover()
    assert state.state is AppState.IDLE


def test_recover_only_acts_from_error():
    state = InteractionState()
    state.begin("remove_background")
    state.recover()
    assert state.is_processing
    state.fail()
    state.recover()
    assert state.state is AppState.IDLE


def test_remove_blocks_the_whole_editor_while_processing():
    state = InteractionState()
    state.begin("remove_background")
    assert {a for a in Action if not state.can(a)} == ALL
    assert state.policy is FULL_LOCK


@pytest.mark.parametrize("tool", ["size_resolution", "comic_effect", "sharpen", None, "herramienta_nueva"])
def test_other_tools_and_non_tool_tasks_keep_the_legacy_behaviour(tool):
    state = InteractionState()
    state.begin(tool)
    assert {a for a in Action if not state.can(a)} == LEGACY_BLOCKED
    assert state.can(Action.ZOOM) and state.can(Action.PAN)
    assert state.policy is LEGACY_LOCK


def test_size_resolution_is_declared_explicitly_and_the_default_is_legacy():
    assert TOOL_POLICIES["size_resolution"] is LEGACY_LOCK and TOOL_POLICIES["remove_background"] is FULL_LOCK
    assert DEFAULT_POLICY is LEGACY_LOCK
    assert set(TOOL_POLICIES) == {"remove_background", "size_resolution"}  # las demás: por defecto


def test_policies_can_be_injected():
    state = InteractionState({"sharpen": FULL_LOCK})
    state.begin("sharpen")
    assert not state.can(Action.ZOOM)
    state.end()
    state.begin("remove_background")
    assert state.can(Action.ZOOM)  # sin entrada propia: el comportamiento por defecto


def test_observers_are_notified_on_changes_only_and_a_broken_one_does_not_break_the_state():
    state = InteractionState()
    seen = []
    unsubscribe = state.subscribe(lambda s: seen.append((s.state, s.active_tool)))
    state.subscribe(lambda s: 1 / 0)
    state.begin("remove_background")
    state.begin("remove_background")  # rechazado: sin notificación
    state.end()
    assert seen == [(AppState.PROCESSING, "remove_background"), (AppState.IDLE, None)]
    assert state.state is AppState.IDLE
    unsubscribe()
    state.begin(None)
    assert len(seen) == 2


# ------------------------------------------------------------ con el controlador
class FakeView:
    def __init__(self, controller):
        self.controller, self.statuses, self.snapshots = controller, [], []
        self.permissions_on_snapshot = []

    def show_snapshot(self, snapshot):
        self.snapshots.append(snapshot)
        self.permissions_on_snapshot.append({a: self.controller.can(a) for a in Action})

    def show_status(self, message, level):
        self.statuses.append((message, level))

    def set_busy(self, busy):
        pass


@pytest.fixture
def setup(tmp_path):
    gate = threading.Event()
    fail = {"on": False}

    def remove(data, session=None):
        gate.wait(5)
        if fail["on"]:
            raise RuntimeError("modelo caído")
        return data

    registry = ToolRegistry()
    registry.register("remove_background", lambda: BackgroundRemover(remove_fn=remove))
    registry.register("comic_effect", ComicEffect)
    registry.register("sharpen", ImageSharpener)
    service = ProcessingService(DesignEngine(ImageLoader({".png"})), registry, tmp_path / "out")
    controller = DesignController(service, BackgroundTaskRunner())
    view = FakeView(controller)
    controller.attach_view(view)
    src = tmp_path / "foto.png"
    Image.new("RGB", (60, 40), "green").save(src)
    controller.open_image(src)
    settle(controller)
    return controller, view, gate, fail


def settle(controller, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        controller.process_pending()
        if not controller.is_busy:
            return
        time.sleep(0.005)
    raise AssertionError("timeout")


def test_running_remove_locks_the_editor_and_a_second_tool_is_refused(setup):
    controller, view, gate, _ = setup
    controller.remove_background()
    assert controller.is_busy and controller.interaction.active_tool == "remove_background"
    assert not any(controller.can(a) for a in Action)
    n = len(view.snapshots)
    controller.sharpen()  # otra herramienta: rechazada por la compuerta
    assert view.statuses[-1][1] is StatusLevel.WARNING and controller.interaction.active_tool == "remove_background"
    gate.set()
    settle(controller)
    assert len(view.snapshots) == n + 1  # solo el resultado de Remove


def test_permissions_are_restored_before_the_result_is_shown(setup):
    controller, view, gate, _ = setup
    controller.remove_background()
    gate.set()
    settle(controller)
    assert all(view.permissions_on_snapshot[-1].values())  # el visor ya está liberado al actualizarse
    assert controller.interaction.state is AppState.IDLE
    assert view.statuses[-1][1] is StatusLevel.SUCCESS


def test_failed_remove_reports_the_error_unlocks_everything_and_keeps_the_document(setup):
    controller, view, gate, fail = setup
    before = controller._service.snapshot()
    fail["on"] = True
    controller.remove_background()
    gate.set()
    settle(controller)
    assert view.statuses[-1][1] is StatusLevel.ERROR
    assert controller.interaction.state is AppState.ERROR and all(controller.can(a) for a in Action)
    after = controller._service.snapshot()
    assert after.image is before.image and after.operations == before.operations  # documento intacto
    fail["on"] = False  # y se puede volver a intentar
    controller.sharpen()
    settle(controller)
    assert controller.interaction.state is AppState.IDLE and view.statuses[-1][1] is StatusLevel.SUCCESS


def test_other_tools_do_not_lock_the_viewer_while_running(setup):
    controller, view, gate, _ = setup
    controller.run_tool("comic_effect")  # herramienta heredada
    assert controller.can(Action.ZOOM) and controller.can(Action.PAN)
    assert not controller.can(Action.OPEN_IMAGE) and not controller.can(Action.OPEN_TOOL)
    settle(controller)


def test_a_task_without_tool_keeps_the_legacy_behaviour(setup):
    controller, _, _, _ = setup
    controller.run_task(start="x", work=lambda: time.sleep(0.05), on_success=lambda _: None, error="e")
    assert controller.can(Action.ZOOM) and not controller.can(Action.SAVE)
    settle(controller)


def test_a_failing_success_callback_does_not_leave_the_app_locked(setup):
    controller, _, _, _ = setup

    def boom(_):
        raise RuntimeError("la vista falló")

    controller.run_task(start="x", work=lambda: 1, on_success=boom, error="e", tool="remove_background")
    with pytest.raises(RuntimeError):
        deadline = time.time() + 5
        while time.time() < deadline:
            controller.process_pending()
            time.sleep(0.005)
    assert all(controller.can(a) for a in Action)  # los bloqueos se liberaron antes del callback


# ------------------------------------------------------ ProcessingState.original
def test_processing_state_no_longer_keeps_a_second_full_resolution_reference():
    state = ProcessingState()
    assert not hasattr(state, "original")
    image = Image.new("RGB", (4, 4))
    state.load(__import__("pathlib").Path("a.png"), image)
    assert state.current is image and not state.operations
