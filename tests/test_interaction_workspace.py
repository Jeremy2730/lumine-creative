"""Ámbitos MAIN/TOOL y espacio de trabajo de InteractionState (lógica pura, sin Tk)."""
import pytest

from app.interaction import (
    DEFAULT_POLICY,
    FULL_LOCK,
    LEGACY_LOCK,
    TOOL_POLICIES,
    Action,
    InteractionState,
    Scope,
)

ALL = list(Action)


def _can(state, scope=Scope.MAIN):
    return {a: state.can(a, scope) for a in ALL}


def test_without_workspace_nothing_changes():
    s = InteractionState()
    assert s.workspace is None
    assert all(_can(s).values())  # IDLE: todo permitido, como antes
    assert not any(_can(s, Scope.TOOL).values())  # no hay espacio de herramienta
    s.begin("sharpen")
    assert not s.can(Action.SAVE) and s.can(Action.ZOOM)  # LEGACY_LOCK, como antes
    assert not any(_can(s, Scope.TOOL).values())


def test_existing_policies_are_untouched():
    assert TOOL_POLICIES["remove_background"] is FULL_LOCK
    assert TOOL_POLICIES["size_resolution"] is LEGACY_LOCK
    assert DEFAULT_POLICY is LEGACY_LOCK
    assert set(TOOL_POLICIES) == {"remove_background", "size_resolution"}


def test_workspace_open_and_idle_blocks_main_and_frees_tool():
    s = InteractionState()
    assert s.enter_workspace("remove_background") is True
    assert s.workspace == "remove_background"
    assert not any(_can(s).values())  # la aplicación principal: todo bloqueado
    assert all(_can(s, Scope.TOOL).values())  # el espacio de la herramienta: todo libre


def test_workspace_processing_with_full_lock_blocks_tool_navigation_too():
    s = InteractionState()
    s.enter_workspace("remove_background")
    assert s.begin("remove_background")
    tool = _can(s, Scope.TOOL)
    assert tool[Action.ZOOM] is False and tool[Action.PAN] is False
    assert not any(_can(s).values())


def test_workspace_processing_follows_the_tool_policy():
    s = InteractionState()
    s.enter_workspace("size_resolution")
    s.begin("size_resolution")  # LEGACY_LOCK: el visor sigue navegable
    assert s.can(Action.ZOOM, Scope.TOOL) and s.can(Action.PAN, Scope.TOOL)
    assert not s.can(Action.SAVE, Scope.TOOL)


def test_error_never_leaves_the_tool_blocked():
    s = InteractionState()
    s.enter_workspace("remove_background")
    s.begin("remove_background")
    s.fail()
    assert all(_can(s, Scope.TOOL).values())
    assert not any(_can(s).values())  # lo principal sigue bloqueado: el espacio sigue abierto


def test_end_after_processing_frees_the_tool_scope():
    s = InteractionState()
    s.enter_workspace("remove_background")
    s.begin("remove_background")
    s.end()
    assert all(_can(s, Scope.TOOL).values())


def test_leave_workspace_restores_main():
    s = InteractionState()
    s.enter_workspace("remove_background")
    s.leave_workspace()
    assert s.workspace is None
    assert all(_can(s).values())
    assert not any(_can(s, Scope.TOOL).values())


def test_cannot_enter_while_processing_or_with_another_workspace_open():
    s = InteractionState()
    s.begin("sharpen")
    assert s.enter_workspace("remove_background") is False and s.workspace is None
    s.end()
    assert s.enter_workspace("remove_background") is True
    assert s.enter_workspace("size_resolution") is False
    assert s.workspace == "remove_background"


def test_observers_hear_enter_and_leave_once_each():
    s = InteractionState()
    calls = []
    s.subscribe(lambda st: calls.append(st.workspace))
    s.enter_workspace("remove_background")
    s.enter_workspace("remove_background")  # rechazado: sin aviso
    s.leave_workspace()
    s.leave_workspace()  # ya cerrado: sin aviso
    assert calls == ["remove_background", None]


def test_enter_leave_many_times_ends_clean():
    s = InteractionState()
    for _ in range(25):
        assert s.enter_workspace("remove_background")
        s.begin("remove_background")
        s.end()
        s.leave_workspace()
    assert s.workspace is None and s.state.value == "idle" and all(_can(s).values())


@pytest.mark.parametrize("action", ALL)
def test_default_scope_is_main(action):
    s = InteractionState()
    s.enter_workspace("remove_background")
    assert s.can(action) == s.can(action, Scope.MAIN) is False
