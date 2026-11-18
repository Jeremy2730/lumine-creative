"""core/image_metadata.py

Responsabilidad:
    - Definir QUÉ propiedades de una imagen viajan con ella a través de las herramientas y
      restituirlas: la resolución (``dpi``, par horizontal/vertical) y el perfil de color
      (``icc_profile``). Es la política de conservación de la aplicación.

No conoce:
    - Herramientas concretas, GUI ni formatos de archivo.

Notas:
    - FUENTE DE VERDAD: ``image.info`` de la imagen del documento (``ProcessingState.current``).
      Es lo que el guardado escribe (``tools/image_loader.py``) y lo que lee la interfaz
      (``ImageSnapshot.dpi``). El tamaño físico NO se guarda: es derivado (px / PPI), de modo que
      se conserva si se conservan los píxeles y el PPI; no se pueden dar valores inconsistentes.
    - Pillow crea imágenes nuevas SIN ``info`` en muchas operaciones (``Image.fromarray``,
      ``Image.new``, un PNG devuelto por otro proceso...), así que no se puede confiar en que cada
      herramienta lo traspase. Por eso ``ImagePipeline`` llama a ``restore_metadata`` tras cada
      operación que no declare que modifica la resolución (``ImageOperation.changes_resolution``).
    - Nunca se inventa un valor: si la entrada no tenía ``dpi``, la salida tampoco (se retira el que
      pudiera haber puesto la herramienta, p. ej. un 72 o 96 por omisión).
"""
from __future__ import annotations

from PIL import Image

#: Claves de ``Image.info`` que deben sobrevivir a cualquier operación que no las modifique a propósito.
PRESERVED_INFO_KEYS: tuple[str, ...] = ("dpi", "icc_profile")


def capture_metadata(image: Image.Image) -> dict[str, object]:
    """Copia de las propiedades protegidas de ``image`` (solo las que tiene)."""
    return {key: image.info[key] for key in PRESERVED_INFO_KEYS if key in image.info}


def restore_metadata(source: Image.Image, result: Image.Image) -> Image.Image:
    """Hace que ``result`` tenga exactamente las propiedades protegidas de ``source``.

    Devuelve ``result`` (misma imagen, con su ``info`` actualizado). No toca la imagen ``source`` ni
    el resto de las claves de ``info`` de ``result``.
    """
    if result is source:
        return result
    info = dict(result.info)
    wanted = capture_metadata(source)
    for key in PRESERVED_INFO_KEYS:
        if key in wanted:
            info[key] = wanted[key]
        else:
            info.pop(key, None)
    result.info = info
    return result
