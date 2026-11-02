"""tools/image_loader.py

Responsabilidad:
    - Entrada/salida de imágenes: validar extensiones, listar imágenes de
      una carpeta, cargar (corrige la orientación EXIF y convierte a RGBA),
      guardar en el formato real que indica la extensión (PNG o JPG/JPEG)
      y generar un nombre de salida único (nunca sobrescribe).
    - Guardado seguro: se escribe primero un archivo temporal en la misma
      carpeta y solo al terminar bien se sustituye el destino
      (``os.replace``), así un fallo nunca deja un archivo final a medias.
    - Transparencia: ``has_transparency`` la detecta mirando el canal alfa
      (no solo el modo de color) y ``flatten_on_white`` compone una COPIA
      sobre blanco para JPG; la imagen de trabajo nunca se modifica.

No conoce:
    - GUI, documentos, diálogos ni algoritmos de procesamiento.

Notas:
    - PNG conserva el alfa. JPG no admite transparencia: si la imagen
      tiene píxeles transparentes, ``save`` exige ``flatten_alpha=True``
      (quien llama decide, normalmente tras preguntar al usuario) y falla
      con ``ImageSaveError`` si no se pidió, para no perderla en silencio.
    - Metadatos: se conservan el DPI y el perfil ICC cuando es posible
      (solo perfiles RGB: tras convertir a RGBA un perfil CMYK o de grises
      ya no describiría los colores). El resto de metadatos del original
      (EXIF, XMP, comentarios, miniaturas) NO se conserva al guardar.
    - Pillow no escribe el DPI ni el perfil ICC de ``image.info`` en JPG a
      menos que se le pasen explícitamente a ``save()``; por eso se
      reenvían aquí. En PNG el DPI se guarda como píxeles/metro y puede
      releerse con una deriva mínima (300 → 299.9994).
"""
from __future__ import annotations

import io
import os
import shutil
import uuid
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from core.exceptions import ImageLoadError, ImageSaveError, UnsupportedFormatError

#: Extensión de destino -> formato real de Pillow. Única fuente de verdad
#: de "qué se puede guardar" (la extensión decide el formato, nunca al revés).
SAVE_FORMATS: dict[str, str] = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG"}

#: Calidad JPG inicial (explícita: el valor por defecto de Pillow es 75).
DEFAULT_JPEG_QUALITY = 95

_WHITE = (255, 255, 255, 255)


def has_transparency(image: Image.Image) -> bool:
    """True si la imagen tiene al menos un píxel no totalmente opaco.

    Se comprueba el canal alfa real: una imagen RGBA con alfa 255 en todos
    sus píxeles (p. ej. un JPG abierto, que el motor trabaja como RGBA) NO
    tiene transparencia.
    """
    if image.mode not in ("RGBA", "LA", "PA") and "transparency" not in image.info:
        return False
    return image.convert("RGBA").getchannel("A").getextrema()[0] < 255


def flatten_on_white(image: Image.Image) -> Image.Image:
    """Copia RGB de ``image`` compuesta sobre blanco (no modifica la original).

    Se compone con el alfa; ``convert("RGB")`` a secas descartaría el alfa
    sin componer y los píxeles transparentes conservarían su color
    residual (p. ej. rojo, negro) en vez de verse blancos.
    """
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, _WHITE)
    return Image.alpha_composite(background, rgba).convert("RGB")


def _is_rgb_profile(icc_profile: bytes) -> bool:
    """True si el perfil ICC describe colores RGB (y se puede parsear)."""
    try:
        profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
        return profile.profile.xcolor_space.strip() == "RGB"
    except Exception:  # noqa: BLE001 - bytes no confiables: cualquier fallo = descartar
        return False


class ImageLoader:
    """Implementa el puerto ``ImageIO`` del motor."""

    def __init__(
        self,
        allowed_extensions: Iterable[str],
        output_suffix: str = "_editada",
        jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    ) -> None:
        self._extensions = frozenset(
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in allowed_extensions
        )
        self._suffix = output_suffix
        self._jpeg_quality = jpeg_quality

    @property
    def allowed_extensions(self) -> frozenset[str]:
        return self._extensions

    @property
    def jpeg_quality(self) -> int:
        return self._jpeg_quality

    def is_supported(self, path: Path) -> bool:
        return Path(path).suffix.lower() in self._extensions

    @staticmethod
    def format_for_path(path: Path) -> str:
        """Formato real (``"PNG"`` o ``"JPEG"``) que corresponde a la extensión."""
        suffix = Path(path).suffix.lower()
        try:
            return SAVE_FORMATS[suffix]
        except KeyError:
            raise UnsupportedFormatError(
                user_message="⚠️ Para guardar usa una extensión .png, .jpg o .jpeg.",
                detail=f"Extensión no soportada para guardar: '{suffix}' ({path})",
            ) from None

    def list_images(self, folder: Path) -> list[Path]:
        """Imágenes válidas de una carpeta, ordenadas por nombre (como el script original)."""
        return sorted(
            (p for p in Path(folder).iterdir() if p.is_file() and self.is_supported(p)),
            key=lambda p: p.name.lower(),
        )

    def load(self, path: Path) -> Image.Image:
        """Carga una imagen, corrige su orientación EXIF y la convierte a RGBA.

        La orientación EXIF se aplica ANTES de convertir (una foto de celular
        con orientación 6 se abre ya girada). El DPI y el perfil ICC RGB se
        conservan en ``image.info``; un perfil que no sea RGB se descarta
        porque tras ``convert("RGBA")`` ya no describiría los colores.
        """
        path = Path(path)
        if not self.is_supported(path):
            raise UnsupportedFormatError(
                detail=f"Extensión no permitida: '{path.suffix}' ({path})"
            )
        try:
            with Image.open(path) as img:
                rgba = ImageOps.exif_transpose(img).convert("RGBA")
        except (
            OSError,
            UnidentifiedImageError,
            Image.DecompressionBombError,
            ValueError,
            SyntaxError,
        ) as exc:
            raise ImageLoadError(detail=f"No se pudo abrir {path}: {exc}") from exc
        icc_profile = rgba.info.get("icc_profile")
        if icc_profile and not _is_rgb_profile(icc_profile):
            rgba.info.pop("icc_profile", None)
        return rgba

    def save(
        self, image: Image.Image, path: Path, *, flatten_alpha: bool = False
    ) -> Path:
        """Guarda en el formato real que indica la extensión de ``path``.

        - ``.png`` conserva el alfa; ``.jpg``/``.jpeg`` escribe JPEG.
        - JPG con transparencia real exige ``flatten_alpha=True`` (se guarda
          una copia compuesta sobre blanco; ``image`` no se modifica). Sin
          él falla con ``ImageSaveError`` en vez de perder la transparencia.
        - Escritura atómica: temporal en la misma carpeta + ``os.replace``.
        """
        path = Path(path)
        fmt = self.format_for_path(path)
        to_write, save_kwargs = self._prepare(image, fmt, flatten_alpha)
        self._atomic_save(to_write, path, fmt, save_kwargs)
        return path

    def _prepare(
        self, image: Image.Image, fmt: str, flatten_alpha: bool
    ) -> tuple[Image.Image, dict[str, object]]:
        kwargs: dict[str, object] = {}
        if "dpi" in image.info:
            kwargs["dpi"] = image.info["dpi"]
        icc_profile = image.info.get("icc_profile")
        if icc_profile:
            kwargs["icc_profile"] = icc_profile
        if fmt == "PNG":
            return image, kwargs
        # JPEG: sin alfa.
        kwargs["quality"] = self._jpeg_quality
        if has_transparency(image):
            if not flatten_alpha:
                raise ImageSaveError(
                    user_message="⚠️ El JPG no admite transparencia.",
                    detail="Imagen con transparencia real y flatten_alpha=False",
                )
            return flatten_on_white(image), kwargs
        return image.convert("RGB"), kwargs  # alfa 100 % opaco: nada que perder

    @staticmethod
    def _atomic_save(
        image: Image.Image, path: Path, fmt: str, save_kwargs: dict[str, object]
    ) -> None:
        tmp: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            image.save(tmp, format=fmt, **save_kwargs)
            if path.exists():
                with suppress(OSError):
                    shutil.copymode(path, tmp)  # no cambiar los permisos del destino
            os.replace(tmp, path)
            tmp = None  # sustitución hecha: nada que limpiar
        except (OSError, ValueError) as exc:
            raise ImageSaveError(detail=f"No se pudo guardar {path}: {exc}") from exc
        finally:
            if tmp is not None:
                with suppress(OSError):
                    tmp.unlink(missing_ok=True)

    def unique_output_path(
        self, directory: Path, stem: str, extension: str = ".png"
    ) -> Path:
        """``stem_editada.png``; si existe, ``stem_editada_2.png``, ``_3``...

        ``extension`` permite sugerir también nombres ``.jpg``/``.jpeg``.
        """
        directory = Path(directory)
        candidate = directory / f"{stem}{self._suffix}{extension}"
        counter = 2
        while candidate.exists():
            candidate = directory / f"{stem}{self._suffix}_{counter}{extension}"
            counter += 1
        return candidate
