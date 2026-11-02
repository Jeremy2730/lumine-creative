"""Orquestación independiente de la generación de máscaras."""
from __future__ import annotations

from PIL import Image

from core.exceptions import ProcessingError
from imaging.matte.ports import MatteBackend
from imaging.matte.types import Matte


class MatteEngine:
    """Genera y valida máscaras sin componer ni modificar la imagen."""

    def __init__(self, backend: MatteBackend) -> None:
        self._backend = backend

    def generate(self, image: Image.Image) -> Matte:
        if image.width <= 0 or image.height <= 0:
            raise ProcessingError(
                user_message="⚠️ La imagen no tiene dimensiones válidas.",
                detail=f"Dimensiones recibidas: {image.size}",
            )

        try:
            matte = self._backend.generate(image)
        except ProcessingError:
            raise
        except Exception as exc:
            raise ProcessingError(
                user_message="❌ No se pudo generar la máscara de la imagen.",
                detail=str(exc),
            ) from exc

        if not isinstance(matte, Matte):
            raise ProcessingError(
                user_message="❌ El motor produjo una máscara inválida.",
                detail=f"Tipo recibido: {type(matte).__name__}",
            )

        if matte.size != image.size:
            raise ProcessingError(
                user_message="❌ La máscara generada tiene un tamaño incorrecto.",
                detail=f"Imagen: {image.size}; máscara: {matte.size}",
            )

        return matte