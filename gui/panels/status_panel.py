"""gui/panels/status_panel.py

Responsabilidad:
    - Mostrar el mensaje de estado (con color según nivel) y una barra de
      progreso indeterminada mientras hay trabajo en curso.

No conoce:
    - Qué operación está en curso ni cómo se abre o guarda un archivo.

Notas:
    - El botón "Guardar resultado" se retiró: Guardar y Guardar como están
      en el menú Archivos y en sus atajos (ver gui/components/menu_bar.py).
"""
from __future__ import annotations

import customtkinter as ctk

from app.controllers.design_controller import StatusLevel

_COLORS: dict[StatusLevel, tuple[str, str]] = {
    StatusLevel.INFO: ("gray20", "gray80"),
    StatusLevel.SUCCESS: ("#1a7f37", "#3fb950"),
    StatusLevel.WARNING: ("#9a6700", "#d29922"),
    StatusLevel.ERROR: ("#cf222e", "#f85149"),
}


class StatusPanel(ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master, corner_radius=12)
        self.columnconfigure(0, weight=1)

        self._label = ctk.CTkLabel(self, text="Estado: Listo", anchor="w", justify="left")
        self._label.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="ew")
        self.bind("<Configure>", lambda e: self._label.configure(wraplength=max(e.width - 32, 100)))

        self._progress = ctk.CTkProgressBar(self, mode="indeterminate")
        self._progress.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")
        self._progress.grid_remove()

    def set_message(self, message: str, level: StatusLevel = StatusLevel.INFO) -> None:
        self._label.configure(text=f"Estado: {message}", text_color=_COLORS[level])

    def set_busy(self, busy: bool) -> None:
        if busy:
            self._progress.grid()
            self._progress.start()
        else:
            self._progress.stop()
            self._progress.grid_remove()
