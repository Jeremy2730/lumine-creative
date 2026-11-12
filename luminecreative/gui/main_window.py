"""gui/main_window.py

Responsabilidad:
    - Ventana principal: arma los paneles (imagen, herramientas, estado),
      la barra de menús y los atajos; implementa DesignView y FileView y
      traduce los eventos de la GUI en llamadas a los controladores.
    - Mostrar los diálogos que le pide FileController (abrir, guardar como,
      cambios pendientes, aplanar para JPG), el título de la ventana y el
      cierre; no decide cuándo preguntar ni qué hacer con la respuesta.
    - Sondear (poll) al controlador cada 50 ms para procesar resultados de
      hilos en segundo plano.

No conoce:
    - Algoritmos de imagen, el motor ni las reglas de Guardar/Guardar como;
      todo pasa por DesignController y FileController.

Notas:
    - ``file_controller`` es opcional: sin él la ventana funciona como antes
      (sin acciones de archivo), lo que mantiene compatibles las pruebas que
      la construyen solo con ``controller`` y ``settings``.
    - El panel "Pipeline / procesos aplicados" está OCULTO (``grid_remove``)
      pero sigue creado y alimentado con ``set_operations``: el historial
      de operaciones y su funcionamiento interno no cambian, y volver a
      mostrarlo es una sola llamada a ``grid()``.
    - Cada ``show_snapshot`` indica al visor si la imagen continúa el mismo
      documento (``_continues_document``: mismo origen y una operación más
      que antes) para conservar zoom y encuadre, o si es una imagen nueva
      para ajustarla al área. Se decide aquí porque solo la ventana ve
      ambos snapshots.
    - ``_poll`` re-programa el sondeo en un ``finally``: si un callback de
      resultado lanzara una excepción, el sondeo seguiría vivo (antes se
      detenía para siempre y la aplicación quedaba "ocupada").
"""
from __future__ import annotations

import customtkinter as ctk

from app.controllers.design_controller import DesignController, StatusLevel
from app.controllers.file_controller import FileController, UnsavedChoice
from app.interaction import Action
from app.services.file_service import SaveSuggestion
from config.settings import Settings
from core.models import ImageSnapshot
from core.progress import ProgressEvent
from gui.components.dialogs import (
    ask_exit_while_processing,
    ask_flatten_to_jpg,
    ask_image_path,
    ask_save_path,
    ask_unsaved_changes,
)
from gui.components.menu_bar import MenuBar, MenuCallbacks, bind_file_shortcuts
from gui.panels.image_panel import ImagePanel
from gui.panels.status_panel import StatusPanel
from gui.panels.tools_panel import ToolsPanel
from tools.size_resolution import SizeResolutionController
from tools.size_resolution.dialog import SizeResolutionDialog

_POLL_MS = 50


def _continues_document(previous: ImageSnapshot | None, current: ImageSnapshot) -> bool:
    """True si ``current`` es el resultado de aplicar herramientas sobre ``previous``.

    Abrir una imagen (aunque sea el mismo archivo) deja ``operations`` vacío o
    con el origen distinto, así que cuenta como documento nuevo.
    """
    return (
        previous is not None
        and bool(current.operations)
        and current.source_path == previous.source_path
        and len(current.operations) > len(previous.operations)
    )


class MainWindow(ctk.CTk):
    """Implementa ``DesignView`` (herramientas) y ``FileView`` (archivos)."""

    def __init__(
        self,
        controller: DesignController,
        settings: Settings,
        file_controller: FileController | None = None,
    ) -> None:
        ctk.set_appearance_mode(settings.appearance_mode)
        ctk.set_default_color_theme(settings.color_theme)
        super().__init__()

        self._controller = controller
        self._file_controller = file_controller
        self._closed = False
        self._size_resolution = SizeResolutionController(controller)
        self._settings = settings
        self._snapshot: ImageSnapshot | None = None

        self.title(settings.app_title)
        self.geometry(settings.window_size)
        self.minsize(820, 640)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_header()
        self._image_panel = ImagePanel(self)
        self._image_panel.grid(row=1, column=0, padx=16, pady=8, sticky="nsew")

        self._tools_panel = ToolsPanel(self)
        self._tools_panel.grid(row=2, column=0, padx=16, pady=8, sticky="ew")
        self._tools_panel.grid_remove()  # oculto por ahora; se sigue alimentando en show_snapshot

        self._status_panel = StatusPanel(self)
        self._status_panel.grid(row=3, column=0, padx=16, pady=(8, 16), sticky="ew")

        self._build_menu()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        controller.interaction.subscribe(lambda _state: self._refresh_controls())
        self._refresh_controls()
        self.after(_POLL_MS, self._poll)

    def _build_menu(self) -> None:
        files = self._file_controller
        noop = lambda: None  # noqa: E731 - sin FileController las acciones de archivo no hacen nada
        open_action = files.open_dialog if files else noop
        save_action = files.save if files else noop
        save_as_action = files.save_as if files else noop
        self._menu = MenuBar(
            self,
            MenuCallbacks(
                open=open_action,
                save=save_action,
                save_as=save_as_action,
                exit=self._on_close,
                tools=(
                    ("Quitar fondo", self._controller.remove_background),
                    ("Semitono", self._controller.comic_effect),
                    ("Tamaño y resolución…", self._on_size_resolution),
                    ("Dar nitidez", self._controller.sharpen),
                ),
            ),
        )
        if files:
            bind_file_shortcuts(
                self, on_open=open_action, on_save=save_action, on_save_as=save_as_action
            )

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=16, pady=(16, 4), sticky="ew")
        header.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text=self._settings.app_title.upper(),
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0)
        ctk.CTkLabel(
            header, text=self._settings.author, text_color=("gray40", "gray60")
        ).grid(row=1, column=0)

    # ---- DesignView (lo que llama el controlador) ----
    def show_snapshot(self, snapshot: ImageSnapshot) -> None:
        keep_view = _continues_document(self._snapshot, snapshot)
        self._snapshot = snapshot
        self._image_panel.show(snapshot.image, keep_view=keep_view)
        self._tools_panel.set_operations([op.label for op in snapshot.operations])
        if self._file_controller is not None:
            self._file_controller.on_snapshot(snapshot)  # título y estado de cambios
        self._refresh_controls()

    def show_status(self, message: str, level: StatusLevel) -> None:
        self._status_panel.set_message(message, level)

    def show_progress(self, event: ProgressEvent) -> None:
        if self._closed:
            return  # un evento tardío no debe tocar widgets de una ventana destruida
        self._status_panel.set_progress(event)

    def set_busy(self, busy: bool) -> None:
        self._status_panel.set_busy(busy)  # barra de progreso; los permisos los da InteractionState

    # ---- FileView (lo que pide FileController) ----
    def ask_open_path(self) -> str | None:
        return ask_image_path(self._settings.allowed_extensions, parent=self)

    def ask_save_path(self, suggestion: SaveSuggestion) -> str | None:
        return ask_save_path(suggestion, parent=self)

    def ask_unsaved_changes(self, name: str) -> UnsavedChoice:
        return ask_unsaved_changes(name, parent=self)

    def ask_flatten_to_jpg(self) -> bool:
        return ask_flatten_to_jpg(parent=self)

    def set_window_title(self, title: str) -> None:
        self.title(title)

    def ask_exit_while_processing(self, has_unsaved_changes: bool) -> bool:
        return ask_exit_while_processing(has_unsaved_changes, parent=self)

    def exit_application(self) -> None:
        self._closed = True
        self.destroy()

    # ---- eventos de la GUI ----
    def _on_close(self) -> None:
        """Cerrar con la X y "Salir" convergen aquí (respeta cambios pendientes)."""
        if self._file_controller is not None:
            self._file_controller.request_exit()
        else:
            self.exit_application()

    def _on_size_resolution(self) -> None:
        if self._snapshot is None:
            return
        size_px = self._snapshot.size
        dpi_is_reliable = self._snapshot.dpi is not None
        reference_dpi = self._snapshot.dpi or self._settings.resolution_dpi_fallback
        width_cm = self._size_resolution.cm_from_dpi(size_px[0], reference_dpi)
        height_cm = self._size_resolution.cm_from_dpi(size_px[1], reference_dpi)
        SizeResolutionDialog(
            self,
            controller=self._size_resolution,
            current_size_px=size_px,
            initial_width_cm=width_cm,
            initial_height_cm=height_cm,
            original_dpi=reference_dpi,
            dpi_is_reliable=dpi_is_reliable,
            default_dpi=reference_dpi,
            max_recommended_px=self._settings.resolution_max_recommended_px,
            on_accept=lambda w, h, d, resample, method: self._size_resolution.apply(
                w, h, d, resample=resample, method=method
            ),
        )

    def _refresh_controls(self) -> None:
        """Lleva a la GUI lo que dice ``InteractionState``: menú y navegación del visor."""
        can = self._controller.can
        has_image = self._snapshot is not None
        files = self._file_controller
        self._menu.set_state(
            can_open=files is not None and can(Action.OPEN_IMAGE),
            can_save=files is not None and files.has_document and can(Action.SAVE),
            can_use_tools=has_image and can(Action.OPEN_TOOL),
        )
        self._image_panel.set_navigation_enabled(zoom=can(Action.ZOOM), pan=can(Action.PAN))

    def _poll(self) -> None:
        try:
            self._controller.process_pending()
        finally:
            if not self._closed:
                self.after(_POLL_MS, self._poll)
