"""app/services/task_runner.py

Responsabilidad:
    - Único punto del proyecto que usa threads: ejecuta una función pesada
      en un hilo y entrega su resultado mediante una cola.
    - Garantizar que los callbacks corran en el hilo que llama a drain()
      (en la práctica, el hilo de la GUI), nunca en el hilo de trabajo.
    - Transportar los eventos de progreso del hilo de trabajo al hilo que
      llama a drain(), por la MISMA cola que los resultados (así un evento
      nunca llega después del resultado de su tarea).

No conoce:
    - Qué hace el trabajo que ejecuta ni qué es un ImageOperation.

Notas:
    - ``on_progress`` es opcional. Sin él, ``work`` se llama sin argumentos
      (compatibilidad total). Con él, ``work`` recibe un ``ProgressReporter``
      cuyos eventos se entregan a ``on_progress`` en ``drain()``.
    - Tras ``close()`` los callbacks pendientes se descartan en vez de
      ejecutarse (cierre de la aplicación).
"""
from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Any

from core.progress import ProgressEvent, ProgressReporter


class BackgroundTaskRunner:
    def __init__(self) -> None:
        self._results: queue.Queue[tuple[Callable[[Any], None], Any]] = queue.Queue()
        self._closed = False

    def submit(
        self,
        work: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ) -> None:
        """Ejecuta ``work`` en un hilo; el callback se entrega en ``drain()``.

        Con ``on_progress``, ``work`` se llama como ``work(reporter)``.
        """

        def target() -> None:
            try:
                if on_progress is None:
                    result = work()
                else:
                    reporter = ProgressReporter(lambda event: self._results.put((on_progress, event)))
                    result = work(reporter)  # type: ignore[call-arg]
            except Exception as exc:
                self._results.put((on_error, exc))
            else:
                self._results.put((on_success, result))

        threading.Thread(target=target, name="design-worker", daemon=True).start()

    def drain(self) -> None:
        """Ejecuta los callbacks pendientes. Llamar periódicamente desde el hilo principal."""
        while True:
            try:
                callback, argument = self._results.get_nowait()
            except queue.Empty:
                return
            if self._closed:
                continue  # cerrando: nada debe tocar una interfaz que ya no existe
            callback(argument)

    def close(self) -> None:
        """Descarta lo pendiente y no entrega nada más (cierre de la aplicación)."""
        self._closed = True
