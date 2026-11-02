"""app/services/task_runner.py

Responsabilidad:
    - Único punto del proyecto que usa threads: ejecuta una función pesada
      en un hilo y entrega su resultado mediante una cola.
    - Garantizar que los callbacks corran en el hilo que llama a drain()
      (en la práctica, el hilo de la GUI), nunca en el hilo de trabajo.

No conoce:
    - Qué hace el trabajo que ejecuta ni qué es un ImageOperation.
"""
from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from typing import Any


class BackgroundTaskRunner:
    def __init__(self) -> None:
        self._results: queue.Queue[tuple[Callable[[Any], None], Any]] = queue.Queue()

    def submit(
        self,
        work: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        """Ejecuta ``work`` en un hilo; el callback se entrega en ``drain()``."""

        def target() -> None:
            try:
                result = work()
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
            callback(argument)
