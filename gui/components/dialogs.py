"""gui/components/dialogs.py

Responsabilidad:
    - Diálogos de archivo y de confirmación que usa la ventana principal:
      elegir qué abrir (``ask_image_path``), elegir dónde guardar y en qué
      formato (``ask_save_path``), qué hacer con los cambios pendientes
      (``ask_unsaved_changes``) y si se acepta aplanar una imagen
      transparente para JPG (``ask_flatten_to_jpg``).

No conoce:
    - Algoritmos de imagen ni cuándo conviene preguntar: esa decisión es de
      ``FileController``; aquí solo se muestra el diálogo y se devuelve la
      respuesta (``None``/``"cancel"``/``False`` si el usuario cancela).

Notas:
    - Son diálogos modales nativos de Tk: no se pueden ejecutar sin pantalla,
      así que las pruebas los sustituyen por funciones falsas.
    - Los textos de los botones de ``askyesnocancel`` dependen del idioma
      del sistema; por eso el mensaje explica qué hace cada uno.
    - ResizeDialog se eliminó junto con la herramienta "Redimensionar";
      SizeResolutionDialog vive en tools/size_resolution/dialog.py.
"""
from __future__ import annotations

from collections.abc import Iterable
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import tkinter as tk

    from app.services.file_service import SaveSuggestion


def ask_image_path(extensions: Iterable[str], parent: "tk.Misc | None" = None) -> str | None:
    """Abre el selector de archivos. Devuelve la ruta o ``None`` si se cancela."""
    patterns = " ".join(f"*{ext}" for ext in sorted(extensions))
    path = filedialog.askopenfilename(
        parent=parent,
        title="Abrir imagen",
        filetypes=[("Imágenes", patterns), ("Todos los archivos", "*.*")],
    )
    return path or None


def ask_save_path(suggestion: "SaveSuggestion", parent: "tk.Misc | None" = None) -> str | None:
    """Diálogo Guardar como (PNG o JPG). ``None`` si el usuario cancela.

    El formato sugerido va primero en la lista de tipos y su extensión es la
    que se añade si el usuario escribe un nombre sin extensión. La
    confirmación de sobrescritura la hace el propio diálogo nativo.
    """
    types = {"PNG": ("PNG", "*.png"), "JPEG": ("JPEG", "*.jpg *.jpeg")}
    ordered = [types[suggestion.format]] + [v for k, v in types.items() if k != suggestion.format]
    path = filedialog.asksaveasfilename(
        parent=parent,
        title="Guardar como",
        initialdir=str(suggestion.directory),
        initialfile=suggestion.filename,
        defaultextension=".jpg" if suggestion.format == "JPEG" else ".png",
        filetypes=ordered,
    )
    return str(path) if path else None


def ask_unsaved_changes(
    name: str, parent: "tk.Misc | None" = None
) -> Literal["save", "discard", "cancel"]:
    """Hay cambios sin guardar: Guardar, Descartar o Cancelar."""
    answer = messagebox.askyesnocancel(
        title="Cambios sin guardar",
        message=(
            f"«{name}» tiene cambios sin guardar.\n\n"
            "Sí: guardar los cambios\n"
            "No: descartarlos\n"
            "Cancelar: volver sin hacer nada"
        ),
        icon="warning",
        parent=parent,
    )
    if answer is None:
        return "cancel"
    return "save" if answer else "discard"


def ask_flatten_to_jpg(parent: "tk.Misc | None" = None) -> bool:
    """True si el usuario acepta aplanar sobre blanco; False si cancela."""
    return bool(
        messagebox.askokcancel(
            title="El JPG no admite transparencia",
            message=(
                "La imagen tiene zonas transparentes y el formato JPG no las admite.\n\n"
                "¿Aplanarla sobre un fondo blanco y guardar esa copia en JPG?\n"
                "(La imagen de trabajo no se modifica.)"
            ),
            icon="warning",
            parent=parent,
        )
    )
