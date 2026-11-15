"""tools/remove/__init__.py

Responsabilidad:
    - Exponer la API pública de la herramienta Remove (espacio de trabajo de
      "Quitar fondo"): su controlador de sesión y los estados.

No conoce:
    - GUI: el diálogo (dialog.py) NO se reexporta aquí, para que importar este
      paquete nunca requiera CustomTkinter. Quien necesite el diálogo lo importa
      explícitamente desde tools.remove.dialog (igual que "Tamaño y resolución").

Notas:
    - El algoritmo (``BackgroundRemover``) sigue en tools/background_remover.py.
"""
from tools.remove.controller import TOOL_NAME, RemoveController, RemoveState, RemoveView

__all__ = ["RemoveController", "RemoveState", "RemoveView", "TOOL_NAME"]
