"""gui/components/menu_bar.py

Responsabilidad:
    - Barra de menús superior (Archivos / Herramientas) construida con
      ``tkinter.Menu`` nativo y coloreada con el tema claro/oscuro actual.
    - Atajos de teclado REALES (Ctrl+O, Ctrl+S, Ctrl+Mayús+S): el texto
      ``accelerator`` de un menú es solo una etiqueta, así que además se
      enlazan las teclas con ``bind`` en la ventana principal.
    - Habilitar/deshabilitar las entradas según el estado que le indica la
      ventana.

No conoce:
    - Lógica de negocio: solo recibe callbacks ya armados (``MenuCallbacks``).
      No sabe qué es un documento, un controlador ni una herramienta.

Notas (decisión de diseño):
    - Se eligió ``tkinter.Menu`` nativo. CustomTkinter 5.2.2 no incluye
      ningún widget de menú (solo ``CTkOptionMenu``). Alternativas
      consideradas: (a) ``CTkMenuBar`` 0.9 de terceros: añade una
      dependencia y un mantenimiento externo para algo que Tk ya hace;
      (b) una barra propia de botones CTk que abren ``tk.Menu`` emergentes:
      se vería más "de tema" en Windows pero se pierden la navegación con
      teclado (Alt+letra) y el comportamiento estándar de la barra.
    - Tema: sin colores, la barra nativa queda gris claro sobre una
      ventana oscura (comprobado con capturas en X11). Se le pasan los
      colores del tema. En Windows la barra superior es nativa y sus
      colores los decide el sistema: esos colores allí NO están
      verificados (la limitación es visual, no funcional).
    - La barra se crea con ``tearoff=0``: con el valor por defecto Tk añade
      una entrada "tear-off" en el índice 0 que desplaza todos los índices.
    - Los atajos se enlazan con ``window.bind`` y NO con ``bind_all``: así
      no se disparan mientras hay un diálogo (``Toplevel``) con el foco.
      Se enlazan mayúscula y minúscula para que Bloq Mayús no los rompa.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import customtkinter as ctk

# Colores del tema por defecto de CustomTkinter (ventana, texto, acento).
_PALETTES = {
    "dark": {"bg": "#2b2b2b", "fg": "#dce4ee", "active_bg": "#1f538d", "active_fg": "#ffffff", "disabled": "#777777"},
    "light": {"bg": "#ebebeb", "fg": "#1a1a1a", "active_bg": "#3b8ed0", "active_fg": "#ffffff", "disabled": "#9a9a9a"},
}

# Posiciones de las entradas del menú Archivos (el separador ocupa la 3).
_FILE_ENTRY = {"open": 0, "save": 1, "save_as": 2, "exit": 4}


@dataclass(frozen=True)
class MenuCallbacks:
    open: Callable[[], None]
    save: Callable[[], None]
    save_as: Callable[[], None]
    exit: Callable[[], None]
    tools: Sequence[tuple[str, Callable[[], None]]]  # (etiqueta, acción)


def _theme_options() -> dict[str, object]:
    mode = "dark" if ctk.get_appearance_mode().lower() == "dark" else "light"
    p = _PALETTES[mode]
    return {
        "bg": p["bg"],
        "fg": p["fg"],
        "activebackground": p["active_bg"],
        "activeforeground": p["active_fg"],
        "disabledforeground": p["disabled"],
        "bd": 0,
        "relief": "flat",
    }


class MenuBar:
    def __init__(self, window: tk.Misc, callbacks: MenuCallbacks) -> None:
        options = _theme_options()
        self.bar = tk.Menu(window, tearoff=0, **options)

        self.files_menu = tk.Menu(self.bar, tearoff=0, **options)
        self.files_menu.add_command(label="Abrir…", accelerator="Ctrl+O", command=callbacks.open)
        self.files_menu.add_command(label="Guardar", accelerator="Ctrl+S", command=callbacks.save)
        self.files_menu.add_command(
            label="Guardar como…", accelerator="Ctrl+Mayús+S", command=callbacks.save_as
        )
        self.files_menu.add_separator()
        self.files_menu.add_command(label="Salir", command=callbacks.exit)

        self.tools_menu = tk.Menu(self.bar, tearoff=0, **options)
        for label, action in callbacks.tools:
            self.tools_menu.add_command(label=label, command=action)

        self.bar.add_cascade(label="Archivos", menu=self.files_menu, underline=0)
        self.bar.add_cascade(label="Herramientas", menu=self.tools_menu, underline=0)
        window.configure(menu=self.bar)

    def set_state(self, *, can_open: bool, can_save: bool, can_use_tools: bool) -> None:
        """Habilita o deshabilita entradas. "Salir" siempre queda habilitada."""
        def state(enabled: bool) -> str:
            return "normal" if enabled else "disabled"

        self.files_menu.entryconfigure(_FILE_ENTRY["open"], state=state(can_open))
        self.files_menu.entryconfigure(_FILE_ENTRY["save"], state=state(can_save))
        self.files_menu.entryconfigure(_FILE_ENTRY["save_as"], state=state(can_save))
        last = self.tools_menu.index("end")  # None si el menú está vacío
        for index in range(0 if last is None else last + 1):
            self.tools_menu.entryconfigure(index, state=state(can_use_tools))


def bind_file_shortcuts(
    window: tk.Misc,
    *,
    on_open: Callable[[], None],
    on_save: Callable[[], None],
    on_save_as: Callable[[], None],
) -> None:
    """Enlaza Ctrl+O, Ctrl+S y Ctrl+Mayús+S a las mismas acciones del menú.

    Con Mayús pulsada, Tk elige el patrón más específico (``Control-Shift``)
    sobre ``Control-S``, así que Guardar como no se confunde con Guardar.
    """

    def wrap(callback: Callable[[], None]) -> Callable[[tk.Event], str]:
        def run(_event: tk.Event) -> str:
            callback()
            return "break"  # no propagar la tecla a otros enlaces

        return run

    for sequence in ("<Control-o>", "<Control-O>"):
        window.bind(sequence, wrap(on_open))
    for sequence in ("<Control-s>", "<Control-S>"):
        window.bind(sequence, wrap(on_save))
    for sequence in ("<Control-Shift-s>", "<Control-Shift-S>"):
        window.bind(sequence, wrap(on_save_as))
