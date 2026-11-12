"""tools/__init__.py

Responsabilidad:
    - Exponer las herramientas concretas de uso directo: BackgroundRemover,
      ComicEffect, ImageLoader, ImageSharpener.

No conoce:
    - GUI; ninguna herramienta importa CustomTkinter.

Notas:
    - "Tamaño y resolución" vive en su propio subpaquete
      (tools/size_resolution/) con su propia API pública (ver
      tools/size_resolution/__init__.py); no se reexporta aquí para no
      acoplar este archivo a cada herramienta nueva.
    - "Redimensionar" (antes tools/image_resizer.py) se eliminó: su
      responsabilidad ya la cubre "Tamaño y resolución".
"""
from tools.background_remover import BackgroundRemover
from tools.comic_effect import ComicEffect
from tools.image_loader import ImageLoader
from tools.image_sharpener import ImageSharpener

__all__ = [
    "BackgroundRemover",
    "ComicEffect",
    "ImageLoader",
    "ImageSharpener",
]
