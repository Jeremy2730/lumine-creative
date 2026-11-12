"""Hace importable el proyecto al ejecutar ``pytest`` desde cualquier carpeta.

También ofrece ``tk_gc_on_main_thread``, un fixture opcional para las pruebas con
ventana que lanzan tareas en segundo plano.
"""
import gc
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def tk_gc_on_main_thread():
    """Los objetos de Tk (Font, PhotoImage...) solo se finalizan en el hilo principal.

    El recolector de basura puede dispararse en cualquier hilo, también en el de
    trabajo de una herramienta. Si ahí finaliza un objeto de Tk, su ``__del__`` llama
    a Tk desde otro hilo: con ``mainloop()`` (la aplicación real) eso se resuelve al
    instante, pero las pruebas mueven la ventana con ``update()`` y la llamada espera
    1 s y falla con "main thread is not in main loop". Unas pocas bastan para agotar
    el tiempo de espera de la prueba. Este fixture limpia la basura pendiente antes de
    la prueba, desactiva el recolector mientras dura y lo ejecuta de nuevo al final
    (ya con la ventana destruida), siempre en el hilo principal.
    """
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        gc.collect()
        gc.enable()
