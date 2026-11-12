"""gui/panels/status_panel.py

Responsabilidad:
    - Mostrar el mensaje de estado (con color según nivel) y una barra de
      progreso mientras hay trabajo en curso: indeterminada si la
      operación no informa su avance, y DETERMINADA (porcentaje, nombre de
      etapa y mensaje) cuando recibe eventos de progreso.

No conoce:
    - Qué operación está en curso ni cómo se abre o guarda un archivo.

Notas:
    - El botón "Guardar resultado" se retiró: Guardar y Guardar como están
      en el menú Archivos y en sus atajos (ver gui/components/menu_bar.py).
    - ``set_progress`` cambia la barra a modo determinado en el primer
      evento y NO repite actualizaciones idénticas. El porcentaje es el de
      la última etapa confirmada: si una etapa no tiene avance real (la
      inferencia), la barra no se mueve ni se anima; solo cambia el texto.
    - ``set_busy(False)`` deja todo reiniciado (modo indeterminado, valor 0,
      oculto) para la siguiente tarea. Tras ``destroy`` los métodos no hacen
      nada (un callback tardío no toca widgets destruidos).
"""
from __future__ import annotations

import customtkinter as ctk

from app.controllers.design_controller import StatusLevel
from core.progress import ProgressEvent

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

        self._detail = ctk.CTkLabel(
            self, text="", anchor="w", justify="left", text_color=("gray40", "gray60")
        )
        self._detail.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="ew")
        self._detail.grid_remove()
        self._determinate = False
        self._last_progress: tuple[int, str, str] | None = None
        self._destroyed = False

    def destroy(self) -> None:
        self._destroyed = True
        super().destroy()

    def set_message(self, message: str, level: StatusLevel = StatusLevel.INFO) -> None:
        if self._destroyed:
            return
        self._label.configure(text=f"Estado: {message}", text_color=_COLORS[level])

    def set_busy(self, busy: bool) -> None:
        if self._destroyed:
            return
        self._progress.stop()
        self._reset_progress()
        if busy:
            self._progress.grid()
            self._progress.start()  # indeterminada hasta que llegue un evento de progreso
        else:
            self._progress.grid_remove()

    def set_progress(self, event: ProgressEvent) -> None:
        """Avance por etapas: porcentaje, nombre de la etapa y mensaje."""
        if self._destroyed:
            return
        percent = round(min(1.0, max(0.0, event.fraction)) * 100)
        key = (percent, event.stage, event.message)
        if key == self._last_progress:
            return  # nada cambió: sin trabajo redundante
        self._last_progress = key
        if not self._determinate:
            self._progress.stop()
            self._progress.configure(mode="determinate")
            self._determinate = True
            self._progress.grid()
        self._progress.set(percent / 100)
        self._detail.configure(text=f"{event.stage} · {percent} %  —  {event.message}")
        self._detail.grid()

    def _reset_progress(self) -> None:
        if self._determinate:
            self._progress.configure(mode="indeterminate")
            self._determinate = False
        self._progress.set(0)
        self._detail.configure(text="")
        self._detail.grid_remove()
        self._last_progress = None
