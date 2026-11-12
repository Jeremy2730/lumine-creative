"""app/interaction.py

Responsabilidad:
    - Estado central de la aplicación (``AppState``: IDLE / PROCESSING / ERROR)
      y política de interacción: qué acciones del usuario están permitidas
      según el estado y la herramienta que se está ejecutando.
    - Declarar EN UN SOLO LUGAR (``TOOL_POLICIES``) qué bloquea cada
      herramienta mientras se procesa. Quien quiera saber si algo está
      permitido pregunta ``can(Action)``; nadie deshabilita widgets por su
      cuenta ni consulta banderas propias de "ocupado".

No conoce:
    - tkinter, Pillow, hilos ni el motor. Es lógica pura: se prueba sin ventana.

Notas:
    - Solo el hilo principal lo usa (``DesignController.run_task`` lo cambia
      al lanzar una tarea y en los callbacks que entrega ``drain()``).
    - IDLE y ERROR permiten todo: un error nunca deja la aplicación bloqueada.
      ERROR solo informa de que la última operación falló; el siguiente
      ``begin`` o ``recover`` lo devuelve al flujo normal. La imagen de
      trabajo no se toca al fallar (el motor es atómico).
    - ``LEGACY_LOCK`` es el comportamiento que ya tenían todas las
      herramientas: mientras se procesa no se abre otra imagen, no se guarda
      y no se lanzan otras herramientas, pero el visor sigue navegable.
      "Tamaño y resolución" lo conserva EXPLÍCITAMENTE; su diálogo, además,
      es modal (``grab_set``) mientras está abierto, algo propio del diálogo
      y ajeno a esta política.
    - ``FULL_LOCK`` (Remove): bloquea también zoom y paneo. Hoy Remove no
      tiene controles propios que mantener activos; cuando exista cancelación
      (fase de progreso y cancelación) será la primera acción que ``FULL_LOCK``
      deje disponible.
    - Una herramienta sin entrada en ``TOOL_POLICIES`` usa ``DEFAULT_POLICY``
      (el comportamiento heredado), de modo que añadir una herramienta no
      cambia el de las demás.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

__all__ = [
    "Action",
    "AppState",
    "InteractionPolicy",
    "InteractionState",
    "LEGACY_LOCK",
    "FULL_LOCK",
    "DEFAULT_POLICY",
    "TOOL_POLICIES",
]


class AppState(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"


class Action(str, Enum):
    """Acciones del usuario que la política puede permitir o bloquear."""

    OPEN_IMAGE = "open_image"  # abrir otra imagen (menú, atajo)
    SAVE = "save"  # guardar / guardar como
    OPEN_TOOL = "open_tool"  # lanzar o abrir otra herramienta
    ZOOM = "zoom"  # rueda, botones de zoom, ajustar, 100 %
    PAN = "pan"  # arrastre, espacio + clic, barras de desplazamiento


@dataclass(frozen=True)
class InteractionPolicy:
    """Acciones bloqueadas mientras una operación se está procesando."""

    name: str
    blocked: frozenset[Action]

    def allows(self, action: Action) -> bool:
        return action not in self.blocked


LEGACY_LOCK = InteractionPolicy(
    "legacy", frozenset({Action.OPEN_IMAGE, Action.SAVE, Action.OPEN_TOOL})
)
FULL_LOCK = InteractionPolicy("full_lock", frozenset(Action))
DEFAULT_POLICY = LEGACY_LOCK

#: Política por herramienta (clave = nombre en el ``ToolRegistry``).
TOOL_POLICIES: Mapping[str, InteractionPolicy] = {
    "remove_background": FULL_LOCK,
    "size_resolution": LEGACY_LOCK,  # conserva su comportamiento actual
}


class InteractionState:
    """Estado central + permisos. Notifica a los observadores cuando cambia."""

    def __init__(
        self,
        policies: Mapping[str, InteractionPolicy] | None = None,
        default: InteractionPolicy = DEFAULT_POLICY,
    ) -> None:
        self._policies = dict(TOOL_POLICIES if policies is None else policies)
        self._default = default
        self._state = AppState.IDLE
        self._tool: str | None = None
        self._observers: list[Callable[[InteractionState], None]] = []

    @property
    def state(self) -> AppState:
        return self._state

    @property
    def is_processing(self) -> bool:
        return self._state is AppState.PROCESSING

    @property
    def active_tool(self) -> str | None:
        """Herramienta en ejecución (``None`` si no hay tarea o no es una herramienta)."""
        return self._tool

    @property
    def policy(self) -> InteractionPolicy | None:
        """Política vigente; solo existe mientras se procesa."""
        if not self.is_processing:
            return None
        return self._policies.get(self._tool, self._default) if self._tool else self._default

    def can(self, action: Action) -> bool:
        policy = self.policy
        return True if policy is None else policy.allows(action)

    # ---- transiciones ----
    def begin(self, tool: str | None = None) -> bool:
        """IDLE/ERROR → PROCESSING. ``False`` (sin cambios) si ya se está procesando."""
        if self.is_processing:
            return False
        self._set(AppState.PROCESSING, tool)
        return True

    def end(self) -> None:
        """PROCESSING → IDLE (operación terminada con éxito)."""
        if self.is_processing:
            self._set(AppState.IDLE, None)

    def fail(self) -> None:
        """PROCESSING → ERROR (la operación falló; se liberan todos los bloqueos)."""
        if self.is_processing:
            self._set(AppState.ERROR, None)

    def recover(self) -> None:
        """ERROR → IDLE. No hace nada en otros estados."""
        if self._state is AppState.ERROR:
            self._set(AppState.IDLE, None)

    # ---- observadores ----
    def subscribe(self, observer: Callable[[InteractionState], None]) -> Callable[[], None]:
        """Registra ``observer`` (se llama en el hilo principal tras cada cambio). Devuelve la baja."""
        self._observers.append(observer)

        def unsubscribe() -> None:
            if observer in self._observers:
                self._observers.remove(observer)

        return unsubscribe

    def _set(self, state: AppState, tool: str | None) -> None:
        if (state, tool) == (self._state, self._tool):
            return
        self._state, self._tool = state, tool
        for observer in list(self._observers):
            try:
                observer(self)
            except Exception:  # noqa: BLE001 - un observador roto no debe dejar el estado a medias
                logger.exception("Un observador del estado de interacción falló")
