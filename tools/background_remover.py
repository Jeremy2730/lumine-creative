"""tools/background_remover.py

Responsabilidad:
    - Ejecutar rembg sobre una imagen y devolver RGBA. Nada más.

No conoce:
    - GUI, threading, ni el resto del pipeline. Tampoco conoce el efecto
      semitono (ver tools/comic_effect.py): son operaciones independientes,
      combinables o no en el pipeline.
"""
from __future__ import annotations

import io
from collections.abc import Callable

from PIL import Image

from core.exceptions import ProcessingError
from core.operation import ImageOperation

RemoveFn = Callable[[bytes], bytes]


class BackgroundRemover(ImageOperation):
    """Recibe una imagen, ejecuta rembg y devuelve una imagen RGBA."""

    name = "remove_background"

    def __init__(self, remove_fn: RemoveFn | None = None) -> None:
        # ``remove_fn`` permite inyectar un reemplazo (tests) sin cargar rembg.
        self._remove_fn = remove_fn

    @property
    def label(self) -> str:
        return "Fondo"

    def apply(self, image: Image.Image) -> Image.Image:
        remove = self._remove_fn or self._load_rembg()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        output = remove(buffer.getvalue())
        return Image.open(io.BytesIO(output)).convert("RGBA")

    @staticmethod
    def _load_rembg() -> RemoveFn:
        # Import diferido: rembg (onnxruntime) es pesado y no debe frenar el arranque
        # ni ser necesario para importar el resto del motor.
        try:
            from rembg import remove
        except ImportError as exc:
            raise ProcessingError(
                user_message="❌ rembg no está instalado. Ejecuta: pip install -r requirements.txt",
                detail=str(exc),
            ) from exc
        return remove
