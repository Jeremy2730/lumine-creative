"""gui/panels/tools_panel.py

Responsabilidad:
    - Mostrar el historial de procesos aplicados a la imagen actual (los
      "chips" del pipeline). Es información de estado, no una acción.

No conoce:
    - Herramientas ni cómo se aplican: solo recibe las etiquetas a mostrar
      (``set_operations``).

Notas:
    - Los botones de herramientas se retiraron de aquí porque duplicaban el
      menú Herramientas (gui/components/menu_bar.py), que es ahora el único
      acceso a ellas; el espacio liberado lo aprovecha el panel de la imagen
      (fila con peso en gui/main_window.py).
    - Abrir y guardar tampoco tienen botón: viven en el menú Archivos y en
      sus atajos de teclado.
"""
from __future__ import annotations

from collections.abc import Sequence

import customtkinter as ctk

from gui.components.buttons import Chip


class ToolsPanel(ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master, corner_radius=12)
        self.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="Pipeline / procesos aplicados", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")
        self._chips = ctk.CTkFrame(self, fg_color="transparent")
        self._chips.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")
        self.set_operations([])

    def set_operations(self, labels: Sequence[str]) -> None:
        for child in self._chips.winfo_children():
            child.destroy()
        if not labels:
            ctk.CTkLabel(
                self._chips, text="Sin procesos aplicados", text_color=("gray40", "gray60")
            ).pack(side="left")
            return
        for index, label in enumerate(labels):
            if index:
                ctk.CTkLabel(self._chips, text="→", text_color=("gray40", "gray60")).pack(
                    side="left", padx=4
                )
            Chip(self._chips, label).pack(side="left")
