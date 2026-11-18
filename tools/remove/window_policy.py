"""tools/remove/window_policy.py

Responsabilidad:
    - Utilidades de ventana de Remove (hija de Lumine) que NO dependen de Tk, para poder
      probarlas sin pantalla: el aviso sonoro del sistema y la petición a Windows del botón
      maximizar/restaurar de la barra de título.

No conoce:
    - Widgets, el controlador ni el estado de la sesión. Recibe un objeto con ``winfo_id``.

Notas:
    - Remove NO tiene botón minimizar: Tk crea las ventanas ``transient`` sin él y aquí no se
      añade (``WS_MINIMIZEBOX`` no se toca). No hay ninguna intercepción de ``SC_MINIMIZE``.
    - Todo lo que toca la API de Windows (``winsound``, ``ctypes.windll``) es opcional: fuera de
      Windows, o si falla, se degrada sin excepciones (el sonido cae a ``bell``; la ventana queda
      como la dejó Tk). NO verificado con Windows real desde el entorno de desarrollo.
"""
from __future__ import annotations

import sys
from typing import Callable

__all__ = ["play_warning_sound", "enable_maximize"]


def play_warning_sound(fallback: Callable[[], None] | None = None) -> bool:
    """Sonido de advertencia estándar de Windows (``MB_ICONEXCLAMATION``). Sin diálogo ni texto.

    ``fallback`` (p. ej. ``widget.bell``) se usa fuera de Windows o si el sonido falla.
    Devuelve ``True`` si sonó el sonido del sistema.
    """
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        return True
    except Exception:  # noqa: BLE001 - ImportError fuera de Windows, RuntimeError sin audio
        if fallback is not None:
            try:
                fallback()
            except Exception:  # noqa: BLE001 - un aviso sonoro nunca debe romper la ventana
                pass
        return False


_GWL_STYLE = -16
_WS_MAXIMIZEBOX = 0x00010000
_SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0020  # NOSIZE | NOMOVE | NOZORDER | FRAMECHANGED


def enable_maximize(widget) -> bool:
    """Pide a Windows el botón maximizar/restaurar para una ventana hija (``transient``).

    Tk crea las ventanas ``transient`` sin él. Se añade ``WS_MAXIMIZEBOX`` al HWND real (el padre
    del ``winfo_id`` de Tk). La ventana sigue siendo PROPIA de Lumine (sin icono en la barra de
    tareas) y sin botón minimizar. Devuelve ``True`` si se aplicó; fuera de Windows o ante
    cualquier fallo, ``False`` y nada cambia.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(widget.winfo_id()) or widget.winfo_id()
        style = user32.GetWindowLongW(hwnd, _GWL_STYLE)
        user32.SetWindowLongW(hwnd, _GWL_STYLE, style | _WS_MAXIMIZEBOX)
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, _SWP_FLAGS)
        return True
    except Exception:  # noqa: BLE001 - la ventana funciona igual sin el botón
        return False
