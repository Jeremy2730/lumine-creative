"""core/progress.py

Responsabilidad:
    - Definir el contrato de progreso por etapas: ``ProgressEvent`` (etapa,
      fracción 0-1, mensaje) y ``ProgressReporter``, que garantiza que lo
      que se entrega es válido (fracción en [0, 1]) y MONOTÓNICO (nunca
      retrocede) y no repite eventos idénticos.

No conoce:
    - Hilos, colas, GUI ni qué operación reporta; el reporter solo entrega
      cada evento al ``sink`` que recibió (la cola del runner, un test...).

Notas:
    - Es el equivalente Python del progreso 0-1 + mensaje de
      ``crates/engine/src/jobs.rs`` (PhotoCraft). La cancelación cooperativa
      de ese diseño NO se implementa aquí (no hay botón de cancelar).
    - Una fracción es el avance CONFIRMADO al empezar una etapa, no una
      estimación de tiempo: una etapa de duración desconocida (inferencia)
      mantiene la fracción de la última etapa confirmada y solo cambia el
      mensaje.
    - Un reporter se usa desde UN solo hilo (el de trabajo).
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

__all__ = ["ProgressEvent", "ProgressReporter", "NULL_REPORTER"]


@dataclass(frozen=True)
class ProgressEvent:
    stage: str  # nombre de la etapa, para mostrar
    fraction: float  # 0.0 - 1.0, monotónica dentro de una operación
    message: str  # qué está pasando ahora


class ProgressReporter:
    """Valida y entrega eventos de progreso a ``sink``."""

    def __init__(self, sink: Callable[[ProgressEvent], None]) -> None:
        self._sink = sink
        self._last: ProgressEvent | None = None

    @property
    def last(self) -> ProgressEvent | None:
        return self._last

    def report(self, stage: str, fraction: float, message: str) -> None:
        if not isinstance(fraction, (int, float)) or isinstance(fraction, bool) or math.isnan(fraction):
            raise ValueError(f"La fracción de progreso debe ser un número, no {fraction!r}.")
        value = min(1.0, max(0.0, float(fraction)))
        if self._last is not None:
            value = max(value, self._last.fraction)  # nunca retrocede
        event = ProgressEvent(stage, value, message)
        if event == self._last:
            return  # sin cambios: no se entrega
        self._last = event
        self._sink(event)


class _NullReporter(ProgressReporter):
    """No entrega nada (operaciones ejecutadas sin interesado en el progreso)."""

    def __init__(self) -> None:
        super().__init__(lambda _event: None)

    def report(self, stage: str, fraction: float, message: str) -> None:
        return


NULL_REPORTER: ProgressReporter = _NullReporter()
