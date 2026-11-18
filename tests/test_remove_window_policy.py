"""Reglas de ventana de Remove como hija de Lumine (tools/remove/window_policy.py). Sin Tk."""
import sys
import types

import pytest

from tools.remove import window_policy as wp


def fake_winsound(monkeypatch, fail=False):
    played = []
    module = types.ModuleType("winsound")
    module.MB_ICONEXCLAMATION = 0x30

    def beep(kind):
        if fail:
            raise RuntimeError("sin audio")
        played.append(kind)

    module.MessageBeep = beep
    monkeypatch.setitem(sys.modules, "winsound", module)
    return played


def test_warning_sound_is_the_standard_exclamation_sound_and_nothing_else(monkeypatch):
    played = fake_winsound(monkeypatch)
    fallback = []
    assert wp.play_warning_sound(lambda: fallback.append(1)) is True
    assert played == [0x30] and fallback == []


def test_warning_sound_falls_back_to_the_widget_bell(monkeypatch):
    fake_winsound(monkeypatch, fail=True)
    bells = []
    assert wp.play_warning_sound(lambda: bells.append(1)) is False and bells == [1]
    monkeypatch.setitem(sys.modules, "winsound", None)  # fuera de Windows: ImportError
    assert wp.play_warning_sound(lambda: bells.append(2)) is False and bells == [1, 2]


def test_warning_sound_never_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, "winsound", None)

    def broken():
        raise RuntimeError("sin bell")

    assert wp.play_warning_sound(broken) is False
    assert wp.play_warning_sound() is False


def test_maximize_button_is_a_noop_outside_windows(monkeypatch):
    monkeypatch.setattr(wp.sys, "platform", "linux")
    assert wp.enable_maximize(object()) is False


def test_maximize_adds_only_the_maximize_style_and_never_the_minimize_one(monkeypatch):
    calls = {}

    class User32:
        def GetParent(self, child):
            return 4242  # el HWND envoltorio de Tk

        def GetWindowLongW(self, hwnd, index):
            calls["get"] = (hwnd, index)
            return 0x00C80000  # WS_CAPTION | WS_SYSMENU

        def SetWindowLongW(self, hwnd, index, value):
            calls["set"] = (hwnd, index, value)

        def SetWindowPos(self, *args):
            calls["pos"] = args

    fake = types.SimpleNamespace(windll=types.SimpleNamespace(user32=User32()))
    monkeypatch.setattr(wp.sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "ctypes", fake)
    assert wp.enable_maximize(types.SimpleNamespace(winfo_id=lambda: 7)) is True
    assert calls["get"] == (4242, -16)
    assert calls["set"] == (4242, -16, 0x00C80000 | 0x00010000)  # WS_MAXIMIZEBOX
    assert calls["set"][2] & 0x00020000 == 0  # WS_MINIMIZEBOX: ni se añade
    assert calls["pos"][0] == 4242 and calls["pos"][-1] == 0x0001 | 0x0002 | 0x0004 | 0x0020


def test_maximize_failure_is_silent(monkeypatch):
    monkeypatch.setattr(wp.sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "ctypes", types.SimpleNamespace())  # sin windll
    assert wp.enable_maximize(types.SimpleNamespace(winfo_id=lambda: 1)) is False


def test_the_module_exposes_no_minimize_machinery():
    assert sorted(wp.__all__) == ["enable_maximize", "play_warning_sound"]
    for gone in ("install_minimize_hook", "MinimizeHook", "is_minimize_command", "window_report",
                 "log_window_report", "enable_minimize_maximize", "_KEEP_ALIVE"):
        assert not hasattr(wp, gone), gone


def _code_words(path):
    """Identificadores y cadenas del código real (sin comentarios ni docstrings, que pueden explicar lo que ya no existe)."""
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
                docstrings.add(id(first.value))
    words = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            words.add(node.id)
        elif isinstance(node, ast.Attribute):
            words.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            words.add(node.name)
        elif isinstance(node, ast.arg):
            words.add(node.arg)
        elif isinstance(node, ast.alias):
            words.add(node.name)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            words.add(node.value)
        elif isinstance(node, ast.Constant) and isinstance(node.value, int):
            words.add(hex(node.value))
    return words


def test_no_production_file_keeps_remove_minimize_code():
    """Limpieza: nada de intercepción de SC_MINIMIZE, PostMessage, WNDPROC ni sincronización de ventanas."""
    from pathlib import Path

    root = Path(wp.__file__).resolve().parents[2]
    banned = {"SC_MINIMIZE", "0xf020", "0x20000", "PostMessageW", "WNDPROC", "WINFUNCTYPE", "SetWindowLongPtrW",
              "CallWindowProcW", "WS_MINIMIZEBOX", "_hidden_with_main", "_minimized_with_main",
              "_watch_main_window", "_on_main_unmap", "_on_main_map", "_retake_modal", "_modal_job",
              "install_minimize_hook", "enable_minimize_maximize", "log_window_report", "window_report",
              "LUMINE_DEBUG_WINDOWS", "iconify", "withdraw"}
    for path in (root / "tools" / "remove" / "dialog.py", root / "tools" / "remove" / "window_policy.py",
                 root / "tools" / "remove" / "controller.py", root / "gui" / "main_window.py"):
        assert _code_words(path).isdisjoint(banned), (path.name, _code_words(path) & banned)


def test_the_remove_window_only_asks_for_the_maximize_button():
    from pathlib import Path

    root = Path(wp.__file__).resolve().parents[2]
    words = _code_words(root / "tools" / "remove" / "dialog.py")
    assert "enable_maximize" in words and "transient" in words  # sigue siendo hija de Lumine
