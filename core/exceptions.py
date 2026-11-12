"""core/exceptions.py

Responsabilidad:
    - Definir los errores "esperables" del dominio, cada uno con un mensaje
      para el usuario (display_message) separado del detalle técnico
      (str(exc)), que sí se registra en el log.

No conoce:
    - GUI; no formatea ventanas de error, solo produce el texto.
"""
from __future__ import annotations


class DesignToolError(Exception):
    """Base de los errores controlados."""

    default_user_message: str | None = None

    def __init__(self, user_message: str | None = None, detail: str | None = None) -> None:
        self.user_message = user_message or self.default_user_message
        super().__init__(detail or self.user_message or self.__class__.__name__)

    def display_message(self, fallback: str) -> str:
        """Mensaje para el usuario; usa ``fallback`` si el error no trae uno propio."""
        return self.user_message or fallback


class ValidationError(DesignToolError):
    default_user_message = "⚠️ Valor inválido."


class UnsupportedFormatError(DesignToolError):
    default_user_message = "⚠️ Formato de imagen no soportado."


class ImageLoadError(DesignToolError):
    default_user_message = "❌ No se pudo abrir la imagen."


class ImageSaveError(DesignToolError):
    default_user_message = "❌ No se pudo guardar la imagen."


class NoImageLoadedError(DesignToolError):
    default_user_message = "⚠️ Primero abre una imagen."


class ProcessingError(DesignToolError):
    """Fallo al aplicar una operación. Sin mensaje propio: lo decide quien orquesta."""


class StalePreviewError(DesignToolError):
    """La previsualización se calculó sobre una versión del documento que ya no es la actual."""

    default_user_message = "⚠️ La imagen cambió mientras se procesaba; el resultado ya no es aplicable."
