"""Backend de máscaras basado en rembg."""
from __future__ import annotations

import io
from collections.abc import Callable
from typing import Any

import numpy as np
from PIL import Image

from core.exceptions import ProcessingError
from imaging.matte.types import Matte

RemoveFn = Callable[..., bytes]
SessionFactory = Callable[..., Any]


class RembgBackend:
    """Adapta rembg a la interfaz imagen -> Matte."""

    def __init__(
        self,
        model_name: str = "u2net",
        *,
        remove_fn: RemoveFn | None = None,
        session_factory: SessionFactory | None = None,
    ) -> None:
        self._model_name = model_name
        self._remove_fn = remove_fn
        self._session_factory = session_factory
        self._session: Any | None = None

    def generate(self, image: Image.Image) -> Matte:
        try:
            remove = self._get_remove()
            session = self._get_session()

            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="PNG")

            output = remove(
                buffer.getvalue(),
                session=session,
                only_mask=True,
            )

            with Image.open(io.BytesIO(output)) as mask_image:
                mask = mask_image.convert("L")

                if mask.size != image.size:
                    mask = mask.resize(
                        image.size,
                        Image.Resampling.LANCZOS,
                    )

                alpha = np.array(mask, dtype=np.uint8, copy=True)

            return Matte(alpha)

        except ProcessingError:
            raise
        except Exception as exc:
            raise ProcessingError(
                user_message="❌ No se pudo extraer la máscara con rembg.",
                detail=f"{type(exc).__name__}: {exc}",
            ) from exc

    def _get_remove(self) -> RemoveFn:
        if self._remove_fn is None:
            try:
                from rembg import remove
            except ImportError as exc:
                raise ProcessingError(
                    user_message=(
                        "❌ rembg no está instalado. "
                        "Ejecuta: pip install -r requirements.txt"
                    ),
                    detail=str(exc),
                ) from exc

            self._remove_fn = remove

        return self._remove_fn

    def _get_session(self) -> Any:
        if self._session is None:
            if self._session_factory is None:
                try:
                    from rembg import new_session
                except ImportError as exc:
                    raise ProcessingError(
                        user_message=(
                            "❌ No se pudo cargar rembg. "
                            "Comprueba las dependencias instaladas."
                        ),
                        detail=str(exc),
                    ) from exc

                self._session_factory = new_session

            self._session = self._session_factory(self._model_name)

        return self._session