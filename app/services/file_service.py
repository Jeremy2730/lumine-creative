"""app/services/file_service.py

Responsabilidad:
    - Lógica de archivos del documento: abrir una imagen (PNG/JPG) a través
      del motor existente, sugerir destino y formato de "Guardar como",
      decidir si hace falta aplanar la transparencia y escribir el
      archivo.

No conoce:
    - GUI, diálogos ni hilos. Las preguntas al usuario las hace
      ``FileController``; este servicio solo calcula y escribe.
    - Herramientas de procesamiento ni el estado de la interfaz.

Notas:
    - ``open`` y ``write`` están pensados para ejecutarse en el hilo de
      trabajo (los lanza ``FileController`` mediante la compuerta de
      tareas de ``DesignController``) y NO modifican ningún
      ``DocumentState``: el controlador lo actualiza después, en el hilo
      principal, solo si la operación terminó bien. Así un fallo o una
      cancelación nunca cambian el destino ni el estado de guardado.
    - Reutiliza ``ProcessingService.open_image`` (el motor no cambia) y
      ``ImageLoader`` (formato real por extensión, aplanado y escritura
      atómica).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.document_state import DocumentState
from app.services.processing_service import ProcessingService
from core.models import AppliedOperation, ImageSnapshot
from tools.image_loader import ImageLoader, has_transparency

_EXTENSION_FOR_FORMAT = {"PNG": ".png", "JPEG": ".jpg"}


@dataclass(frozen=True)
class OpenResult:
    snapshot: ImageSnapshot
    document: DocumentState


@dataclass(frozen=True)
class SaveSuggestion:
    """Valores iniciales del diálogo "Guardar como"."""

    directory: Path
    filename: str
    format: str  # "PNG" | "JPEG"


@dataclass(frozen=True)
class SaveResult:
    path: Path
    format: str
    operations: tuple[AppliedOperation, ...]


class FileService:
    def __init__(self, loader: ImageLoader, processing: ProcessingService) -> None:
        self._loader = loader
        self._processing = processing

    # ---- consulta (hilo principal) ----
    def current_snapshot(self) -> ImageSnapshot | None:
        return self._processing.snapshot() if self._processing.has_image else None

    def format_for_path(self, path: Path) -> str:
        """Formato real por extensión; ``UnsupportedFormatError`` si no se puede guardar."""
        return self._loader.format_for_path(path)

    def needs_flatten(self, snapshot: ImageSnapshot, fmt: str) -> bool:
        """JPG con transparencia real: hay que preguntar antes de aplanar."""
        return fmt == "JPEG" and has_transparency(snapshot.image)

    def suggest_save_target(
        self, document: DocumentState, snapshot: ImageSnapshot
    ) -> SaveSuggestion:
        """Carpeta, nombre y formato iniciales de "Guardar como".

        - Formato: PNG si la imagen tiene transparencia real; si no, el del
          último guardado o, en su defecto, el del archivo de origen
          (``.jpg``/``.jpeg`` → JPEG; cualquier otro → PNG).
        - Nombre: ``<origen>_editada.<ext>`` sin pisar archivos existentes.
          Si ya se guardó antes, se propone el mismo nombre del destino.
        - Carpeta: la del último destino o, si no hay, la del origen.
        """
        if has_transparency(snapshot.image):
            fmt = "PNG"
        elif document.save_format is not None:
            fmt = document.save_format
        elif document.origin_path.suffix.lower() in (".jpg", ".jpeg"):
            fmt = "JPEG"
        else:
            fmt = "PNG"
        extension = _EXTENSION_FOR_FORMAT[fmt]
        if document.save_path is not None:
            directory = document.save_path.parent
            filename = document.save_path.with_suffix(extension).name
        else:
            directory = document.origin_path.parent
            filename = self._loader.unique_output_path(
                directory, document.origin_path.stem, extension
            ).name
        return SaveSuggestion(directory=directory, filename=filename, format=fmt)

    # ---- trabajo pesado (hilo de trabajo, vía DesignController.run_task) ----
    def open(self, path: Path) -> OpenResult:
        """Abre ``path`` en el motor. Si falla, el documento actual no cambia."""
        path = Path(path)
        snapshot = self._processing.open_image(path)
        document = DocumentState(
            display_name=path.name,
            origin_path=path,
            saved_operations=snapshot.operations,
        )
        return OpenResult(snapshot=snapshot, document=document)

    def write(self, path: Path, *, flatten: bool = False) -> SaveResult:
        """Escribe la imagen de trabajo en ``path`` (formato = extensión).

        No modifica ningún ``DocumentState``. Con ``flatten`` se guarda una
        copia compuesta sobre blanco; la imagen de trabajo no se toca.
        """
        snapshot = self._processing.snapshot()
        fmt = self._loader.format_for_path(path)
        saved = self._loader.save(snapshot.image, path, flatten_alpha=flatten)
        return SaveResult(path=saved, format=fmt, operations=snapshot.operations)
