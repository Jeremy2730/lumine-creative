"""app/services/document_state.py

Responsabilidad:
    - Metadatos del documento de trabajo: de qué archivo se abrió
      (``origin_path``), dónde y en qué formato se guardó por última vez
      (``save_path``/``save_format``) y qué operaciones llevaba aplicadas
      cuando se abrió o guardó por última vez (``saved_operations``).
    - Responder si hay cambios pendientes y si el documento aún no tiene
      destino de guardado ("sin título").

No conoce:
    - Píxeles, GUI, hilos ni herramientas concretas. La imagen de trabajo
      sigue viviendo solo en el motor (``ProcessingState``); esto es solo
      la ficha del archivo.

Notas:
    - Cambios pendientes = las operaciones aplicadas hoy difieren de las
      que había al abrir/guardar. Se compara la TUPLA de
      ``AppliedOperation`` (nombre y etiqueta), no solo su cantidad, de
      modo que sigue siendo correcto si algún día existe deshacer. No
      hay contador de revisiones ni historial: el motor no los tiene y no
      hacen falta todavía. Limitación: dos operaciones con el mismo
      nombre y etiqueta pero parámetros distintos que no aparezcan en la
      etiqueta serían indistinguibles (hoy las etiquetas ya incluyen los
      parámetros relevantes, p. ej. "Tamaño 10×5 cm @ 300 PPI").
    - Un archivo recién abierto NO tiene ``save_path``: Guardar equivale a
      Guardar como hasta que el usuario elige un destino, de modo que el
      original jamás se sobrescribe en silencio.
    - Solo el hilo principal debe modificarlo (lo hace ``FileController``
      en los callbacks de las tareas, nunca el hilo de trabajo).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from core.models import AppliedOperation


@dataclass
class DocumentState:
    display_name: str
    origin_path: Path
    save_path: Path | None = None
    save_format: str | None = None  # "PNG" | "JPEG"
    saved_operations: tuple[AppliedOperation, ...] = ()

    @property
    def is_untitled(self) -> bool:
        """True si todavía no tiene destino de guardado."""
        return self.save_path is None

    @property
    def title_name(self) -> str:
        """Nombre a mostrar: el del archivo guardado, o el del origen."""
        return self.save_path.name if self.save_path is not None else self.display_name

    def has_unsaved_changes(self, operations: Sequence[AppliedOperation]) -> bool:
        return tuple(operations) != self.saved_operations

    def mark_saved(
        self, path: Path, fmt: str, operations: Sequence[AppliedOperation]
    ) -> None:
        """Registra un guardado correcto (nunca se llama si falló o se canceló)."""
        self.save_path = Path(path)
        self.save_format = fmt
        self.saved_operations = tuple(operations)
