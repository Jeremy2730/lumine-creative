"""gui/components/__init__.py

Responsabilidad:
    - Exponer los componentes reutilizables: botones, chip, diálogos de
      archivo y la barra de menús.
"""
from gui.components.buttons import Chip, PrimaryButton, SecondaryButton
from gui.components.dialogs import (
    ask_flatten_to_jpg,
    ask_image_path,
    ask_save_path,
    ask_unsaved_changes,
)
from gui.components.menu_bar import MenuBar, MenuCallbacks, bind_file_shortcuts

__all__ = [
    "Chip",
    "PrimaryButton",
    "SecondaryButton",
    "MenuBar",
    "MenuCallbacks",
    "bind_file_shortcuts",
    "ask_flatten_to_jpg",
    "ask_image_path",
    "ask_save_path",
    "ask_unsaved_changes",
]
