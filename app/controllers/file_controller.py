"""app/controllers/file_controller.py

Responsabilidad:
    - Flujos de usuario de archivo: Abrir, Guardar, Guardar como y Salir,
      con el tratamiento de cambios pendientes (Guardar / Descartar /
      Cancelar), el aviso de transparencia al guardar JPG y el título de
      la ventana.
    - Decidir CUÁNDO preguntar al usuario; la GUI solo sabe CÓMO (la vista
      implementa ``FileView``). Así ``main_window.py`` y el menú no
      contienen lógica de negocio.
    - Ser el dueño del ``DocumentState`` actual y actualizarlo únicamente
      en el hilo principal y solo tras una operación correcta.

No conoce:
    - Widgets, diálogos concretos ni algoritmos de imagen.
    - Su propio hilo ni su propia bandera de "ocupado": usa
      ``DesignController.run_task``, la misma compuerta que las
      herramientas, de modo que abrir, guardar y procesar nunca se
      solapan.

Notas:
    - Un archivo recién abierto no tiene destino de guardado: el primer
      Guardar abre "Guardar como" (el original nunca se sobrescribe en
      silencio).
    - Cancelar un diálogo, o un fallo de escritura, no cambian el destino
      ni el estado de guardado, y cortan la acción encadenada (abrir otro
      archivo o cerrar la aplicación).
    - Los diálogos se abren en el hilo principal ANTES de despachar el
      trabajo; el hilo de trabajo nunca toca la GUI.
    - ``DesignController.open_image``/``save`` siguen existiendo (código
      heredado, la GUI ya no los usa); pendiente retirarlos cuando se
      migren las pruebas que dependen de ellos.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol

from app.controllers.design_controller import DesignController, StatusLevel
from app.services.document_state import DocumentState
from app.services.file_service import FileService, OpenResult, SaveResult, SaveSuggestion
from core.exceptions import DesignToolError, NoImageLoadedError
from core.models import ImageSnapshot

logger = logging.getLogger(__name__)

UnsavedChoice = Literal["save", "discard", "cancel"]


class FileView(Protocol):
    """Lo que la ventana debe ofrecer al controlador de archivos."""

    def show_snapshot(self, snapshot: ImageSnapshot) -> None: ...

    def show_status(self, message: str, level: StatusLevel) -> None: ...

    def ask_open_path(self) -> str | None:
        """Selector de archivo. ``None`` si el usuario cancela."""

    def ask_save_path(self, suggestion: SaveSuggestion) -> str | None:
        """Diálogo Guardar como. ``None`` si el usuario cancela."""

    def ask_unsaved_changes(self, name: str) -> UnsavedChoice:
        """Pregunta qué hacer con los cambios pendientes."""

    def ask_flatten_to_jpg(self) -> bool:
        """True si acepta aplanar sobre blanco; False si cancela."""

    def set_window_title(self, title: str) -> None: ...

    def exit_application(self) -> None: ...


class FileController:
    def __init__(
        self, design: DesignController, service: FileService, app_title: str
    ) -> None:
        self._design = design
        self._service = service
        self._app_title = app_title
        self._document: DocumentState | None = None
        self._view: FileView | None = None

    # ---- ciclo de vida ----
    def attach_view(self, view: FileView) -> None:
        self._view = view

    @property
    def document(self) -> DocumentState | None:
        return self._document

    @property
    def has_document(self) -> bool:
        return self._document is not None

    def has_unsaved_changes(self) -> bool:
        snapshot = self._service.current_snapshot()
        if self._document is None or snapshot is None:
            return False
        return self._document.has_unsaved_changes(snapshot.operations)

    def window_title(self) -> str:
        document = self._document
        if document is None:
            return self._app_title
        marker = " *" if self.has_unsaved_changes() else ""
        return f"{document.title_name}{marker} — {self._app_title}"

    def on_snapshot(self, snapshot: ImageSnapshot) -> None:
        """La ventana lo llama tras cada ``show_snapshot`` (abrir o aplicar una herramienta)."""
        if self._document is not None and snapshot.source_path != self._document.origin_path:
            self._document = None  # la imagen se abrió por otra vía: la ficha quedó obsoleta
        self._refresh_title()

    # ---- acciones públicas (menú, atajos, cierre) ----
    def open_dialog(self) -> None:
        """Abrir…: pide el archivo y converge en ``open_path``."""
        if self._design.is_busy:
            self._warn_busy()
            return
        path = self._view_or_fail().ask_open_path()
        if path:
            self.open_path(path)

    def open_path(self, path: str | Path) -> None:
        """Único punto de entrada para abrir un archivo (menú, atajo, futuras vías)."""
        if self._design.is_busy:
            self._warn_busy()
            return
        self._confirm_discard(lambda: self._start_open(Path(path)))

    def save(self) -> None:
        self._save_flow(on_saved=None)

    def save_as(self) -> None:
        self._save_as_flow(on_saved=None)

    def request_exit(self) -> None:
        """Salir / cerrar la ventana: respeta los cambios pendientes."""
        if self._design.is_busy:
            self._design.warn("⏳ Espera a que termine el proceso actual antes de cerrar.")
            return
        self._confirm_discard(self._view_or_fail().exit_application)

    # ---- cambios pendientes ----
    def _confirm_discard(self, proceed: Callable[[], None]) -> None:
        """Ejecuta ``proceed`` si no hay cambios, o tras Guardar/Descartar. Cancelar corta."""
        if not self.has_unsaved_changes():
            proceed()
            return
        assert self._document is not None
        choice = self._view_or_fail().ask_unsaved_changes(self._document.title_name)
        if choice == "discard":
            proceed()
        elif choice == "save":
            self._save_flow(on_saved=proceed)  # si se cancela o falla, no continúa
        # "cancel": no pasa nada

    # ---- abrir ----
    def _start_open(self, path: Path) -> None:
        view = self._view_or_fail()

        def work() -> OpenResult:
            return self._service.open(path)

        def done(result: OpenResult) -> None:
            self._document = result.document  # solo tras abrir bien
            view.show_snapshot(result.snapshot)
            width, height = result.snapshot.size
            view.show_status(
                f"✅ Imagen cargada: {path.name} ({width} × {height} px)", StatusLevel.SUCCESS
            )
            self._refresh_title()

        self._design.run_task(
            start="📂 Abriendo imagen...",
            work=work,
            on_success=done,
            error="❌ No se pudo abrir la imagen.",
        )

    # ---- guardar ----
    def _can_save(self) -> bool:
        if self._design.is_busy:
            self._warn_busy()
            return False
        if self._document is None or self._service.current_snapshot() is None:
            self._design.warn(NoImageLoadedError.default_user_message or "")
            return False
        return True

    def _save_flow(self, on_saved: Callable[[], None] | None) -> None:
        if not self._can_save():
            return
        assert self._document is not None
        if self._document.is_untitled:
            self._save_as_flow(on_saved)  # sin destino: Guardar equivale a Guardar como
        else:
            assert self._document.save_path is not None
            self._write(self._document.save_path, on_saved)

    def _save_as_flow(self, on_saved: Callable[[], None] | None) -> None:
        if not self._can_save():
            return
        assert self._document is not None
        snapshot = self._service.current_snapshot()
        assert snapshot is not None
        suggestion = self._service.suggest_save_target(self._document, snapshot)
        chosen = self._view_or_fail().ask_save_path(suggestion)
        if not chosen:
            return  # cancelado: nada cambia
        self._write(Path(chosen), on_saved)

    def _write(self, path: Path, on_saved: Callable[[], None] | None) -> None:
        view = self._view_or_fail()
        document = self._document
        snapshot = self._service.current_snapshot()
        assert document is not None and snapshot is not None
        try:
            fmt = self._service.format_for_path(path)
        except DesignToolError as exc:
            view.show_status(exc.display_message("⚠️ Extensión no válida."), StatusLevel.WARNING)
            return
        flatten = False
        if self._service.needs_flatten(snapshot, fmt):
            if not view.ask_flatten_to_jpg():
                return  # cancelado: no se escribe nada ni cambia el estado
            flatten = True

        def work() -> SaveResult:
            return self._service.write(path, flatten=flatten)

        def done(result: SaveResult) -> None:
            if self._document is document:  # sigue siendo el mismo documento
                document.mark_saved(result.path, result.format, result.operations)
            view.show_status(f"💾 Imagen guardada en: {result.path}", StatusLevel.SUCCESS)
            self._refresh_title()
            if on_saved is not None:
                on_saved()

        self._design.run_task(
            start="💾 Guardando...",
            work=work,
            on_success=done,
            error="❌ No se pudo guardar la imagen.",
        )

    # ---- internos ----
    def _refresh_title(self) -> None:
        if self._view is not None:
            self._view.set_window_title(self.window_title())

    def _warn_busy(self) -> None:
        self._design.warn("⏳ Espera a que termine el proceso actual.")

    def _view_or_fail(self) -> FileView:
        if self._view is None:
            raise RuntimeError("FileController: no hay vista asociada (attach_view).")
        return self._view
