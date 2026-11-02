"""gui/panels/image_panel.py

Responsabilidad:
    - Mostrar una miniatura de la imagen actual, ajustada al espacio
      disponible del panel (sin modificar la imagen real del motor).

No conoce:
    - El estado del motor; solo recibe la imagen a mostrar vía show().
"""
from __future__ import annotations

import customtkinter as ctk
from PIL import Image


class ImagePanel(ctk.CTkFrame):
    """Muestra la imagen ajustada al espacio disponible.

    Solo escala para VISUALIZAR (copia reducida); nunca modifica la imagen del motor.
    """

    _PREVIEW_MAX = 2048

    def __init__(self, master) -> None:
        super().__init__(master, corner_radius=12, height=340)
        self.pack_propagate(False)  # el contenido no debe dictar el tamaño del panel
        self._preview: Image.Image | None = None
        self._ctk_image: ctk.CTkImage | None = None
        self._resize_job: str | None = None

        self._label = ctk.CTkLabel(
            self,
            text="Abre una imagen para comenzar\n(menú Archivos ▸ Abrir…  ·  Ctrl+O)",
            text_color=("gray40", "gray60"),
        )
        self._label.pack(expand=True, fill="both", padx=12, pady=12)
        self.bind("<Configure>", self._on_configure)

    def show(self, image: Image.Image) -> None:
        preview = image.copy()
        preview.thumbnail((self._PREVIEW_MAX, self._PREVIEW_MAX), Image.Resampling.LANCZOS)
        self._preview = preview
        self._render()

    def _on_configure(self, _event) -> None:
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(80, self._render)

    def _render(self) -> None:
        self._resize_job = None
        if self._preview is None:
            return
        avail_w = max(self.winfo_width() - 32, 50)
        avail_h = max(self.winfo_height() - 32, 50)
        pw, ph = self._preview.size
        scale = min(avail_w / pw, avail_h / ph)
        size = (max(1, int(pw * scale)), max(1, int(ph * scale)))
        self._ctk_image = ctk.CTkImage(
            light_image=self._preview, dark_image=self._preview, size=size
        )
        self._label.configure(image=self._ctk_image, text="")
