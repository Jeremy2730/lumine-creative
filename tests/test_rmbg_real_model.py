"""tests/test_rmbg_real_model.py

Responsabilidad:
    - Pruebas OPCIONALES con rembg y el modelo real (u2net): la sesión real se
      crea una sola vez, se reutiliza, y la salida conserva tamaño y RGBA.

No conoce:
    - Nada que no sea rembg real. Se omiten salvo que se pida expresamente,
      porque necesitan rembg instalado y el modelo (~170 MB) descargado:

          LUMINE_REAL_RMBG=1 pytest tests/test_rmbg_real_model.py -s

Notas:
    - No comparan tiempos entre ejecuciones (dependen de la máquina y serían
      inestables); los tiempos reales se obtienen con scripts/benchmark_rmbg.py --real.
"""
import importlib.util
import os

import pytest
from PIL import Image

from tools.background_remover import BackgroundRemover, RembgSessionManager

pytestmark = pytest.mark.skipif(
    os.environ.get("LUMINE_REAL_RMBG") != "1" or importlib.util.find_spec("rembg") is None,
    reason="opcional: define LUMINE_REAL_RMBG=1 y ten rembg instalado (descarga el modelo)",
)


@pytest.fixture(scope="module")
def manager():
    m = RembgSessionManager()
    yield m
    m.close()


def photo(size=(256, 192)):
    image = Image.new("RGB", size, (30, 120, 200))
    image.paste((220, 60, 50), (size[0] // 4, size[1] // 4, size[0] * 3 // 4, size[1] * 3 // 4))
    image.info["dpi"] = (300.0, 300.0)
    return image


def test_real_session_is_created_once_and_reused(manager):
    remover = BackgroundRemover(session_manager=manager)
    for _ in range(3):
        remover.apply(photo())
    assert manager.load_count == 1 and manager.is_loaded
    assert manager.providers, "debería informar el Execution Provider activo"
    assert remover.last_timings.session_reused


def test_real_output_is_rgba_with_the_input_size_and_the_input_is_untouched(manager):
    src = photo((320, 200))
    before = (src.tobytes(), src.size, src.mode, dict(src.info))
    out = BackgroundRemover(session_manager=manager).apply(src)
    assert out.mode == "RGBA" and out.size == (320, 200)
    assert (src.tobytes(), src.size, src.mode, dict(src.info)) == before
