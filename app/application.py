"""app/application.py

Responsabilidad:
    - Raíz de composición: crear las dependencias (settings, herramientas,
      motor, servicio, controladores de diseño y de archivos) y conectarlas.
    - Registrar en un único lugar (build_tool_registry) las herramientas
      disponibles para la aplicación.
    - Crear UNA vez el ``RembgSessionManager`` (sesión ONNX de rembg) y
      compartirlo explícitamente con la fábrica de "Quitar fondo", para que
      el modelo se cargue una sola vez durante la vida de la aplicación; y
      liberarlo al cerrar (``DesignApplication.run``).
    - Arrancar la ventana principal (DesignApplication.run).

No conoce:
    - Algoritmos de imagen (delega en tools/); no importa CustomTkinter a
      nivel de módulo, solo dentro de run(), para que build_processing_service
      y build_controller se puedan usar desde consola/tests sin tkinter.
"""
from __future__ import annotations

import logging

from app.controllers.design_controller import DesignController
from app.controllers.file_controller import FileController
from app.services.file_service import FileService
from app.services.processing_service import ProcessingService
from app.services.task_runner import BackgroundTaskRunner
from app.services.tool_registry import ToolRegistry
from config.logging_config import setup_logging
from config.settings import Settings, get_settings
from core.design_engine import DesignEngine
from tools.background_remover import BackgroundRemover, RembgSessionManager
from tools.comic_effect import ComicEffect
from tools.image_loader import ImageLoader
from tools.image_sharpener import ImageSharpener
from tools.size_resolution import SizeResolutionAdjuster

logger = logging.getLogger(__name__)


def build_tool_registry(
    settings: Settings, session_manager: RembgSessionManager | None = None
) -> ToolRegistry:
    """Punto único donde se registran las herramientas disponibles.

    ``session_manager`` es la sesión de rembg COMPARTIDA por todas las operaciones de
    quitar fondo de este registro (se crea una por registro si no se pasa).
    """
    sessions = session_manager or RembgSessionManager()
    registry = ToolRegistry()
    registry.register("remove_background", lambda: BackgroundRemover(session_manager=sessions))
    registry.register(
        "comic_effect",
        lambda: ComicEffect(
            black_threshold=settings.comic_black_threshold,
            pattern_contrast=settings.comic_pattern_contrast,
            blend_alpha=settings.comic_blend_alpha,
        ),
    )
    registry.register(
        "size_resolution",
        lambda width_cm, height_cm, dpi, resample, method: SizeResolutionAdjuster(
            width_cm, height_cm, dpi, resample=resample, method=method
        ),
    )
    registry.register(
        "sharpen",
        lambda: ImageSharpener(
            radius=settings.sharpen_radius,
            percent=settings.sharpen_percent,
            threshold=settings.sharpen_threshold,
        ),
    )
    return registry


def build_image_loader(settings: Settings) -> ImageLoader:
    return ImageLoader(
        settings.allowed_extensions, settings.output_suffix, jpeg_quality=settings.jpg_quality
    )


def build_processing_service(
    settings: Settings | None = None,
    loader: ImageLoader | None = None,
    session_manager: RembgSessionManager | None = None,
) -> ProcessingService:
    """Servicio listo para usar desde consola, tests u otra aplicación."""
    settings = settings or get_settings()
    engine = DesignEngine(loader or build_image_loader(settings))
    return ProcessingService(
        engine, build_tool_registry(settings, session_manager), settings.output_dir
    )


def build_controller(settings: Settings | None = None) -> DesignController:
    settings = settings or get_settings()
    return DesignController(
        service=build_processing_service(settings),
        runner=BackgroundTaskRunner(),
    )


def build_controllers(
    settings: Settings | None = None,
    session_manager: RembgSessionManager | None = None,
) -> tuple[DesignController, FileController]:
    """Controlador de diseño + controlador de archivos sobre el MISMO servicio.

    Comparten cargador, servicio y la compuerta de tareas del
    ``DesignController`` (no hay un segundo runner ni otra bandera de ocupado).
    """
    settings = settings or get_settings()
    loader = build_image_loader(settings)
    service = build_processing_service(settings, loader, session_manager)
    design = DesignController(service=service, runner=BackgroundTaskRunner())
    files = FileController(design, FileService(loader, service), settings.app_title)
    return design, files


class DesignApplication:
    """Ensambla la aplicación de escritorio y la ejecuta."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def run(self) -> None:
        setup_logging(self._settings.log_dir)
        logger.info("Iniciando %s", self._settings.app_title)
        sessions = RembgSessionManager()  # se carga en la primera operación, nunca al arrancar
        controller, file_controller = build_controllers(self._settings, sessions)

        from gui.main_window import MainWindow  # import diferido: solo aquí se toca la GUI

        window = MainWindow(
            controller=controller, settings=self._settings, file_controller=file_controller
        )
        controller.attach_view(window)
        file_controller.attach_view(window)
        try:
            window.mainloop()
        finally:
            sessions.close()
