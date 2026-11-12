"""tools/size_resolution/dialog.py

Responsabilidad:
    - Diálogo de "Tamaño y resolución": ancho/alto + resolución, con
      selector de unidad de medida (Centímetros/Milímetros/Pulgadas/
      Píxeles) y de resolución (PPI/px·cm) en línea junto a cada campo,
      estilo Photoshop; con y sin remuestreo, vista previa en vivo.

No conoce:
    - Algoritmos de imagen ni el motor; todo cálculo y validación pasa
      por el ``controller`` inyectado (un SizeResolutionController),
      incluida la conversión de unidades (``length_to_cm``,
      ``length_from_cm``, ``resolution_to_ppi``, ``resolution_from_ppi``).

Notas:
    - Movido literalmente desde gui/components/dialogs.py (Fase 1 de la
      reorganización por herramienta); revisiones posteriores le
      agregaron los selectores de unidad y luego este layout compacto.
    - La referencia interna sigue siendo cm/PPI exactamente como antes:
      ``on_accept`` recibe width_cm/height_cm/dpi en cm y PPI, igual que
      siempre, sin importar qué unidad esté viendo el usuario. Las
      unidades son puramente una capa de presentación — se convierte al
      entrar a cada cálculo y al volver a mostrar un valor, nunca se
      arrastra una conversión acumulada de un campo a otro.
    - Con unidad "Centímetros" + resolución "PPI" (las dos por defecto),
      el comportamiento es exactamente el de antes de este cambio.
    - El selector de medidas usa internamente los códigos
      "cm"/"mm"/"in"/"px" (mapeados desde las etiquetas en español que
      ve el usuario). Con "Píxeles" y remuestreo activado, ancho/alto
      representan directamente los píxeles objetivo (la resolución
      sigue determinando el tamaño físico); con remuestreo desactivado,
      los píxeles quedan fijos exactamente igual que con cualquier otra
      unidad — editar el campo recalcula la resolución efectiva.
    - Los números se muestran sin ceros decimales sobrantes: "72" en vez
      de "72.00", pero "72.5" se conserva tal cual.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.exceptions import DesignToolError
from gui.components.buttons import PrimaryButton, SecondaryButton

if TYPE_CHECKING:
    from tools.size_resolution.controller import SizeResolutionController


class SizeResolutionDialog(ctk.CTkToplevel):
    """"Tamaño y resolución": ancho/alto + PPI, con y sin remuestreo.

    Con "Remuestrear" activado, ancho/alto/resolución son independientes
    (el resultado en píxeles se deriva de los tres). Con "Remuestrear"
    desactivado, los píxeles quedan fijos: editar ancho/alto recalcula la
    resolución efectiva, y editar la resolución recalcula ancho/alto —
    por eso "mantener proporción" se deshabilita en ese modo (no hay forma
    de deformar sin remuestrear).

    Todo el cálculo pasa por ``controller`` (vista previa, sin aplicar
    nada ni tocar hilos); solo "Aplicar" dispara la acción real.

    Las medidas se pueden ver en Centímetros, Milímetros, Pulgadas o
    Píxeles, y la resolución en PPI o px/cm, cada una con su propio desplegable junto
    al campo (estilo Photoshop); internamente todo sigue siendo cm y
    PPI — el cambio de unidad solo convierte lo que ya hay escrito en los
    campos, sin alterar el tamaño ni la resolución realmente configurados.
    """

    _LENGTH_UNIT_LABELS = {
        "cm": "Centímetros",
        "mm": "Milímetros",
        "in": "Pulgadas",
        "px": "Píxeles",
    }
    _RESOLUTION_UNITS = ("PPI", "px/cm")

    def __init__(
        self,
        master,
        *,
        controller: "SizeResolutionController",
        current_size_px: tuple[int, int],
        initial_width_cm: float,
        initial_height_cm: float,
        original_dpi: float,
        dpi_is_reliable: bool,
        default_dpi: float,
        max_recommended_px: int,
        on_accept: Callable[[float, float, float, bool, str], None],
    ) -> None:
        super().__init__(master)
        self._controller = controller
        self._reference_px = current_size_px
        self._max_recommended_px = max_recommended_px
        self._on_accept = on_accept
        self._updating = False
        self._length_unit_value = "cm"
        self._resolution_unit_value = "PPI"

        self.title("Tamaño y resolución")
        self.geometry("400x600")
        self.resizable(False, False)
        self.transient(master)
        self.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text=f"Dimensiones actuales: {current_size_px[0]} × {current_size_px[1]} px",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 2), sticky="w")

        origin_text = (
            f"Resolución original: {original_dpi:g} PPI"
            if dpi_is_reliable
            else f"Resolución original no disponible (usando {original_dpi:g} PPI de referencia)"
        )
        ctk.CTkLabel(
            self,
            text=origin_text,
            text_color=("gray40", "gray60"),
            wraplength=350,
            justify="left",
        ).grid(row=1, column=0, padx=20, pady=(0, 14), sticky="w")

        length_values = list(self._LENGTH_UNIT_LABELS.values())

        width_row = self._field_row(2)
        ctk.CTkLabel(width_row, text="Ancho", width=70, anchor="w").grid(row=0, column=0, sticky="w")
        self._width_entry = ctk.CTkEntry(width_row, width=100, height=36)
        self._set_entry(self._width_entry, initial_width_cm)
        self._width_entry.grid(row=0, column=1, padx=8, sticky="w")
        self._width_entry.bind("<KeyRelease>", self._on_width_changed)
        self._width_unit = ctk.CTkOptionMenu(
            width_row, values=length_values, width=130, command=self._on_length_unit_selected
        )
        self._width_unit.set(self._LENGTH_UNIT_LABELS["cm"])
        self._width_unit.grid(row=0, column=2, sticky="e")

        height_row = self._field_row(3)
        ctk.CTkLabel(height_row, text="Alto", width=70, anchor="w").grid(row=0, column=0, sticky="w")
        self._height_entry = ctk.CTkEntry(height_row, width=100, height=36)
        self._set_entry(self._height_entry, initial_height_cm)
        self._height_entry.grid(row=0, column=1, padx=8, sticky="w")
        self._height_entry.bind("<KeyRelease>", self._on_height_changed)
        self._height_unit = ctk.CTkOptionMenu(
            height_row, values=length_values, width=130, command=self._on_length_unit_selected
        )
        self._height_unit.set(self._LENGTH_UNIT_LABELS["cm"])
        self._height_unit.grid(row=0, column=2, sticky="e")

        self._proportion_checkbox = ctk.CTkCheckBox(self, text="🔒 Mantener proporción")
        self._proportion_checkbox.select()
        self._proportion_checkbox.grid(row=4, column=0, padx=20, pady=(4, 14), sticky="w")

        dpi_row = self._field_row(5)
        ctk.CTkLabel(dpi_row, text="Resolución", width=70, anchor="w").grid(row=0, column=0, sticky="w")
        self._dpi_entry = ctk.CTkEntry(dpi_row, width=100, height=36)
        self._set_entry(self._dpi_entry, original_dpi)
        self._dpi_entry.grid(row=0, column=1, padx=8, sticky="w")
        self._dpi_entry.bind("<KeyRelease>", self._on_dpi_changed)
        self._resolution_unit = ctk.CTkOptionMenu(
            dpi_row, values=list(self._RESOLUTION_UNITS), width=90, command=self._on_resolution_unit_changed
        )
        self._resolution_unit.set("PPI")
        self._resolution_unit.grid(row=0, column=2, sticky="e")

        self._resample_checkbox = ctk.CTkCheckBox(
            self, text="Remuestrear", command=self._on_resample_toggle
        )
        self._resample_checkbox.select()
        self._resample_checkbox.grid(row=6, column=0, padx=20, pady=(0, 10), sticky="w")

        ctk.CTkLabel(self, text="Método").grid(row=7, column=0, padx=20, sticky="w")
        self._method_menu = ctk.CTkOptionMenu(self, values=list(controller.resample_methods))
        self._method_menu.set("LANCZOS")
        self._method_menu.grid(row=8, column=0, padx=20, pady=(0, 12), sticky="ew")

        self._result_label = ctk.CTkLabel(self, text="", text_color=("gray20", "gray80"))
        self._result_label.grid(row=9, column=0, padx=20, pady=(4, 0), sticky="w")
        self._effective_dpi_label = ctk.CTkLabel(self, text="", text_color=("gray20", "gray80"))
        self._effective_dpi_label.grid(row=10, column=0, padx=20, sticky="w")
        self._warning_label = ctk.CTkLabel(
            self, text="", text_color=("#9a6700", "#d29922"), wraplength=350, justify="left"
        )
        self._warning_label.grid(row=11, column=0, padx=20, pady=(4, 0), sticky="w")

        self._error = ctk.CTkLabel(self, text="", text_color=("#cf222e", "#f85149"))
        self._error.grid(row=12, column=0, padx=20, pady=(6, 0))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=13, column=0, padx=20, pady=(16, 22), sticky="ew")
        buttons.columnconfigure((0, 1), weight=1)
        SecondaryButton(buttons, "Cancelar", self.destroy).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        PrimaryButton(buttons, "Aplicar", self._accept).grid(row=0, column=1, padx=(6, 0), sticky="ew")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(150, self._focus_modal)  # evita fallos de grab_set en algunos SO
        self._refresh_preview()

    def _field_row(self, row: int) -> ctk.CTkFrame:
        """Fila [etiqueta][campo][unidad] en una sola línea, estilo Photoshop."""
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.grid(row=row, column=0, padx=20, pady=(0, 8), sticky="ew")
        return frame

    def _focus_modal(self) -> None:
        if self.winfo_exists():
            self.grab_set()
            self._width_entry.focus_set()

    @staticmethod
    def _set_entry(entry: ctk.CTkEntry, value: float) -> None:
        """Dos decimales como máximo, sin ceros sobrantes: "72", no "72.00"."""
        entry.delete(0, "end")
        text = f"{float(value):.2f}".rstrip("0").rstrip(".")
        entry.insert(0, text)

    # ---- unidad actualmente seleccionada en cada campo ----
    def _length_unit_code(self) -> str:
        return self._length_unit_value

    def _resolution_unit_code(self) -> str:
        return self._resolution_unit.get()

    def _current_canonical_dpi(self) -> float:
        """Lee el campo Resolución y lo convierte a PPI canónico.

        Puede lanzar ``DesignToolError`` si el campo no tiene un número
        válido todavía (el usuario sigue escribiendo).
        """
        raw = self._controller.parse_positive(self._dpi_entry.get(), "La resolución")
        return self._controller.resolution_to_ppi(raw, self._resolution_unit_code())

    # ---- cambio de unidad: solo convierte lo ya escrito, no toca el
    # tamaño/resolución real ni los estados de remuestrear/proporción ----
    def _on_length_unit_selected(self, label: str) -> None:
        """Callback de cualquiera de los dos desplegables (ancho/alto):
        sincroniza ambos y aplica la conversión una sola vez."""
        new_unit = next(code for code, text in self._LENGTH_UNIT_LABELS.items() if text == label)
        self._width_unit.set(label)
        self._height_unit.set(label)
        self._on_length_unit_changed(new_unit)

    def _on_length_unit_changed(self, new_unit: str) -> None:
        old_unit = self._length_unit_value
        try:
            dpi = self._current_canonical_dpi()
        except DesignToolError:
            self._length_unit_value = new_unit
            return

        for entry, label in (
            (self._width_entry, "El ancho"),
            (self._height_entry, "El alto"),
        ):
            try:
                raw = self._controller.parse_positive(entry.get(), label)
                cm = self._controller.length_to_cm(raw, old_unit, dpi)
                converted = self._controller.length_from_cm(cm, new_unit, dpi)
                self._set_entry(entry, converted)
            except DesignToolError:
                pass  # campo vacío/inválido: se deja tal cual, nada que convertir

        self._length_unit_value = new_unit
        self._refresh_preview()

    def _on_resolution_unit_changed(self, new_unit: str) -> None:
        old_unit = self._resolution_unit_value
        try:
            raw = self._controller.parse_positive(self._dpi_entry.get(), "La resolución")
            ppi = self._controller.resolution_to_ppi(raw, old_unit)
            self._set_entry(self._dpi_entry, self._controller.resolution_from_ppi(ppi, new_unit))
        except DesignToolError:
            pass
        self._resolution_unit_value = new_unit
        self._refresh_preview()

    def _on_width_changed(self, _event=None) -> None:
        if self._updating:
            return
        try:
            dpi = self._current_canonical_dpi()
            raw_width = self._controller.parse_positive(self._width_entry.get(), "El ancho")
            width_cm = self._controller.length_to_cm(raw_width, self._length_unit_code(), dpi)
        except DesignToolError:
            return  # el usuario sigue escribiendo; no interrumpir
        self._updating = True
        try:
            if self._resample_checkbox.get():
                if self._proportion_checkbox.get():
                    height_cm = self._controller.paired_dimension_cm(
                        self._reference_px, width_cm, "width"
                    )
                    self._set_entry(
                        self._height_entry,
                        self._controller.length_from_cm(height_cm, self._length_unit_code(), dpi),
                    )
            else:
                new_dpi = self._controller.effective_dpi_from_cm(self._reference_px[0], width_cm)
                height_cm = self._controller.cm_from_dpi(self._reference_px[1], new_dpi)
                self._set_entry(
                    self._dpi_entry,
                    self._controller.resolution_from_ppi(new_dpi, self._resolution_unit_code()),
                )
                self._set_entry(
                    self._height_entry,
                    self._controller.length_from_cm(height_cm, self._length_unit_code(), new_dpi),
                )
        except DesignToolError:
            pass
        finally:
            self._updating = False
        self._refresh_preview()

    def _on_height_changed(self, _event=None) -> None:
        if self._updating:
            return
        try:
            dpi = self._current_canonical_dpi()
            raw_height = self._controller.parse_positive(self._height_entry.get(), "El alto")
            height_cm = self._controller.length_to_cm(raw_height, self._length_unit_code(), dpi)
        except DesignToolError:
            return
        self._updating = True
        try:
            if self._resample_checkbox.get():
                if self._proportion_checkbox.get():
                    width_cm = self._controller.paired_dimension_cm(
                        self._reference_px, height_cm, "height"
                    )
                    self._set_entry(
                        self._width_entry,
                        self._controller.length_from_cm(width_cm, self._length_unit_code(), dpi),
                    )
            else:
                new_dpi = self._controller.effective_dpi_from_cm(self._reference_px[1], height_cm)
                width_cm = self._controller.cm_from_dpi(self._reference_px[0], new_dpi)
                self._set_entry(
                    self._dpi_entry,
                    self._controller.resolution_from_ppi(new_dpi, self._resolution_unit_code()),
                )
                self._set_entry(
                    self._width_entry,
                    self._controller.length_from_cm(width_cm, self._length_unit_code(), new_dpi),
                )
        except DesignToolError:
            pass
        finally:
            self._updating = False
        self._refresh_preview()

    def _on_dpi_changed(self, _event=None) -> None:
        if self._updating:
            return
        try:
            dpi = self._current_canonical_dpi()
        except DesignToolError:
            return
        if not self._resample_checkbox.get():
            self._updating = True
            try:
                width_cm = self._controller.cm_from_dpi(self._reference_px[0], dpi)
                height_cm = self._controller.cm_from_dpi(self._reference_px[1], dpi)
                self._set_entry(
                    self._width_entry,
                    self._controller.length_from_cm(width_cm, self._length_unit_code(), dpi),
                )
                self._set_entry(
                    self._height_entry,
                    self._controller.length_from_cm(height_cm, self._length_unit_code(), dpi),
                )
            except DesignToolError:
                pass
            finally:
                self._updating = False
        self._refresh_preview()

    def _on_resample_toggle(self) -> None:
        resample = bool(self._resample_checkbox.get())
        self._proportion_checkbox.configure(state="normal" if resample else "disabled")
        if not resample:
            # Sin remuestreo, los tres campos deben quedar consistentes con los
            # píxeles fijos: se recalculan ancho/alto a partir del DPI actual.
            self._on_dpi_changed()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        try:
            dpi = self._current_canonical_dpi()
        except DesignToolError:
            self._result_label.configure(text="Resultado: —")
            self._effective_dpi_label.configure(text="")
            self._warning_label.configure(text="")
            return

        if self._resample_checkbox.get():
            try:
                raw_width = self._controller.parse_positive(self._width_entry.get(), "El ancho")
                raw_height = self._controller.parse_positive(self._height_entry.get(), "El alto")
                width_cm = self._controller.length_to_cm(raw_width, self._length_unit_code(), dpi)
                height_cm = self._controller.length_to_cm(raw_height, self._length_unit_code(), dpi)
                result_px = self._controller.preview_size_px(width_cm, height_cm, dpi)
            except DesignToolError:
                self._result_label.configure(text="Resultado: —")
                self._effective_dpi_label.configure(text="")
                self._warning_label.configure(text="")
                return
        else:
            result_px = self._reference_px  # los píxeles no cambian sin remuestreo

        self._result_label.configure(text=f"Resultado: {result_px[0]} × {result_px[1]} px")
        # La resolución efectiva siempre se informa en PPI, aunque el
        # usuario esté viendo "px/cm" (la referencia interna es PPI).
        self._effective_dpi_label.configure(text=f"Resolución efectiva: {dpi:g} PPI")

        if self._resample_checkbox.get() and max(result_px) > self._max_recommended_px:
            self._warning_label.configure(
                text=(
                    f"⚠️ El resultado supera {self._max_recommended_px:,} px de lado; "
                    "el archivo puede ser muy pesado."
                )
            )
        else:
            self._warning_label.configure(text="")

    def _accept(self) -> None:
        try:
            dpi = self._current_canonical_dpi()
            raw_width = self._controller.parse_positive(self._width_entry.get(), "El ancho")
            raw_height = self._controller.parse_positive(self._height_entry.get(), "El alto")
            width_cm = self._controller.length_to_cm(raw_width, self._length_unit_code(), dpi)
            height_cm = self._controller.length_to_cm(raw_height, self._length_unit_code(), dpi)
        except DesignToolError as exc:
            self._error.configure(text=exc.display_message("⚠️ Valor inválido."))
            return
        resample = bool(self._resample_checkbox.get())
        method = self._method_menu.get()
        self.destroy()
        self._on_accept(width_cm, height_cm, dpi, resample, method)
