"""core/design_engine.py

Responsabilidad:
    - Mantener el estado de trabajo (ProcessingState) y ejecutar pipelines
      sobre la imagen actual: abrir, aplicar una operación, ejecutar un
      pipeline completo, guardar.
    - Garantizar que un fallo a mitad de pipeline no deje el estado a
      medias (solo se actualiza si todo el pipeline tuvo éxito).

No conoce:
    - GUI, threads, ni algoritmos concretos de imagen (solo ImageOperation).

Notas:
    - No es thread-safe por diseño; BackgroundTaskRunner garantiza una sola
      llamada a la vez.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from PIL import Image

from core.exceptions import NoImageLoadedError
from core.image_pipeline import ImagePipeline
from core.models import ImageSnapshot, ProcessingState, ProcessingStatus
from core.operation import ImageOperation
from core.progress import ProgressReporter


class ImageIO(Protocol):
    """Puerto de entrada/salida que el motor necesita (lo implementa ``tools.ImageLoader``)."""

    def load(self, path: Path) -> Image.Image: ...

    def save(self, image: Image.Image, path: Path) -> Path: ...

    def unique_output_path(self, directory: Path, stem: str) -> Path: ...


class DesignEngine:
    """Corazón del procesamiento.

    Uso mínimo desde consola::

        engine = DesignEngine(ImageLoader(...))
        engine.open_image(Path("foto.jpg"))
        engine.apply(ImageSharpener())
        engine.save(Path.home() / "Downloads")

    No es thread-safe por diseño: quien lo use desde hilos (ver ``BackgroundTaskRunner``)
    debe garantizar una sola operación a la vez.
    """

    def __init__(self, image_io: ImageIO) -> None:
        self._io = image_io
        self._state = ProcessingState()

    @property
    def has_image(self) -> bool:
        return self._state.has_image

    def snapshot(self) -> ImageSnapshot:
        return self._state.snapshot()

    def open_image(self, path: Path) -> ImageSnapshot:
        """Carga una imagen y reinicia el historial."""
        path = Path(path)
        self._state.load(path, self._io.load(path))
        return self._state.snapshot()

    def apply(
        self, operation: ImageOperation, progress: ProgressReporter | None = None
    ) -> ImageSnapshot:
        """Aplica una única operación sobre la imagen actual (acumulativo)."""
        return self.run_pipeline(ImagePipeline([operation]), progress=progress)

    def run_pipeline(
        self,
        pipeline: ImagePipeline,
        on_step: Callable[[ImageOperation], None] | None = None,
        progress: ProgressReporter | None = None,
    ) -> ImageSnapshot:
        """Ejecuta un pipeline sobre la imagen actual. Si falla, el estado no cambia."""
        state = self._state
        if state.current is None:
            raise NoImageLoadedError()
        state.status = ProcessingStatus.PROCESSING
        try:
            result = pipeline.run(state.current, on_step=on_step, progress=progress)
        except Exception:
            state.status = ProcessingStatus.ERROR
            raise
        state.commit(result.image, result.applied)
        state.status = ProcessingStatus.IDLE
        return state.snapshot()

    def save(self, output_dir: Path) -> Path:
        """Guarda la imagen actual sin sobrescribir archivos existentes."""
        state = self._state
        if state.current is None or state.source_path is None:
            raise NoImageLoadedError()
        target = self._io.unique_output_path(Path(output_dir), state.source_path.stem)
        return self._io.save(state.current, target)
