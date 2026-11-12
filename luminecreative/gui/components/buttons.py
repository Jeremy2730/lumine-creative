"""gui/components/buttons.py

Responsabilidad:
    - Botones (PrimaryButton, SecondaryButton) y etiqueta (Chip) con
      estilo consistente para toda la GUI.

No conoce:
    - Qué acción ejecuta cada botón (recibe el callback ya armado).
"""
from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk


class PrimaryButton(ctk.CTkButton):
    """Acción principal (p. ej. Guardar)."""

    def __init__(self, master, text: str, command: Callable[[], None], **kwargs) -> None:
        super().__init__(
            master,
            text=text,
            command=command,
            height=38,
            corner_radius=8,
            font=ctk.CTkFont(weight="bold"),
            **kwargs,
        )


class SecondaryButton(ctk.CTkButton):
    """Acción de herramienta / secundaria."""

    def __init__(self, master, text: str, command: Callable[[], None], **kwargs) -> None:
        super().__init__(
            master,
            text=text,
            command=command,
            height=36,
            corner_radius=8,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            hover_color=("gray80", "gray25"),
            **kwargs,
        )


class Chip(ctk.CTkLabel):
    """Etiqueta redondeada para el historial de procesos."""

    def __init__(self, master, text: str, **kwargs) -> None:
        super().__init__(
            master,
            text=f"  {text}  ",
            corner_radius=12,
            fg_color=("gray80", "gray25"),
            height=26,
            **kwargs,
        )
