"""tools/background_remover.py

Responsabilidad:
    - Ejecutar rembg sobre una imagen y devolver RGBA, informando de su
      avance por etapas y midiendo cada una.
    - ``RembgSessionManager``: dueño de la sesión ONNX de rembg. La carga
      una sola vez (diferida, bajo bloqueo), la reutiliza y la libera.

No conoce:
    - GUI, threading (salvo el ``Lock`` que protege la sesión), ni el resto
      del pipeline. Tampoco conoce el efecto semitono (ver
      tools/comic_effect.py): son operaciones independientes.

Notas:
    - Causa de la lentitud (por verificar con el modelo real, ver
      docs/rendimiento_rmbg.md): antes, ``build_tool_registry`` creaba un
      ``BackgroundRemover`` NUEVO por operación y llamaba a ``rembg.remove``
      sin sesión, con lo que rembg crea (y carga desde disco) una sesión
      ONNX nueva en cada clic.
    - Quién comparte la sesión: ``app/application.py`` crea UN
      ``RembgSessionManager`` y lo inyecta en las fábricas del registro. No
      hay singleton global: sin gestor (o con ``remove_fn``) el comportamiento
      es el de siempre.
    - Modelo: ``u2net`` (el que rembg usa por omisión, ahora explícito en
      ``DEFAULT_MODEL``). No se cambia. Execution Provider: se deja el que
      elige rembg/ONNX Runtime (no se activa GPU); el realmente activo se
      consulta tras crear la sesión (``providers``) y se registra.
    - ``_load_rembg`` sigue siendo el punto que devuelve la función
      ``remove`` (las pruebas lo sustituyen). Solo se crea sesión si esa
      función acepta ``session``; una función de sustitución sin ese
      parámetro se llama como antes.
    - La sesión se usa bajo un único ``Lock``: una inferencia a la vez y una
      sola inicialización, aunque dos hilos coincidan.
    - Etapas y fracciones: son marcas de avance CONFIRMADO al comenzar cada
      etapa (``_STAGES``), no estimaciones de tiempo; las proporciones son
      provisionales hasta medir con el modelo real. Durante la inferencia no
      hay avance real que informar: la fracción no cambia.
    - Tiempos: ``prepare`` = codificar PNG; ``inference`` = la llamada a
      ``remove`` completa (incluye la decodificación, el preproceso, la
      inferencia ONNX y la codificación que hace rembg por dentro, no
      separables desde aquí); ``compose`` = decodificar y pasar a RGBA.
"""
from __future__ import annotations

import inspect
import io
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PIL import Image

from core.exceptions import ProcessingError
from core.operation import ImageOperation
from core.progress import NULL_REPORTER, ProgressReporter

logger = logging.getLogger(__name__)

RemoveFn = Callable[[bytes], bytes]
SessionFactory = Callable[[str], Any]

DEFAULT_MODEL = "u2net"  # el modelo que rembg usa por omisión

_SESSION_ERROR = "❌ No se pudo cargar el modelo de eliminación de fondo."
_CLOSE_TIMEOUT_S = 2.0
_PRESERVED_INFO = ("dpi", "icc_profile")  # lo que el guardado escribe y el resto de herramientas respeta

# (id, nombre mostrado, fracción confirmada al comenzar la etapa)
_STAGES = {
    "operation": ("Preparación", 0.00),
    "session": ("Modelo", 0.05),
    "image": ("Imagen", 0.25),
    "inference": ("Inferencia", 0.35),
    "compose": ("Composición", 0.85),
    "validate": ("Validación", 0.95),
}


@dataclass(frozen=True)
class RemovalTimings:
    """Tiempos (ms) de una eliminación de fondo."""

    input_size: tuple[int, int]
    model: str
    providers: tuple[str, ...]
    session_reused: bool
    model_load_ms: float  # 0 si la sesión ya estaba cargada
    prepare_ms: float
    inference_ms: float
    compose_ms: float
    total_ms: float


class RembgSessionManager:
    """Sesión ONNX de rembg: carga diferida, reutilizada, protegida con un bloqueo, liberable."""

    def __init__(
        self, model_name: str = DEFAULT_MODEL, session_factory: SessionFactory | None = None
    ) -> None:
        self._model_name = model_name
        self._factory = session_factory or self._rembg_session_factory
        self._lock = threading.Lock()
        self._session: Any | None = None
        self._providers: tuple[str, ...] = ()
        self._loads = 0
        self.last_load_ms = 0.0

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def is_loaded(self) -> bool:
        return self._session is not None

    @property
    def load_count(self) -> int:
        """Cuántas veces se ha creado la sesión (debe ser 1 mientras no se cierre)."""
        return self._loads

    @property
    def providers(self) -> tuple[str, ...]:
        """Execution Providers realmente activos de la sesión ((), si no está cargada)."""
        return self._providers

    def ensure_loaded(self) -> bool:
        """Carga la sesión si hace falta. Devuelve True si la creó ahora, False si ya existía."""
        with self._lock:
            return self._ensure()

    def run(self, work: Callable[[Any], Any]) -> Any:
        """Ejecuta ``work(sesión)`` con la sesión (cargándola si hace falta) y el bloqueo tomados."""
        with self._lock:
            self._ensure()
            return work(self._session)

    def close(self) -> None:
        """Libera la sesión. Espera un tiempo limitado a una inferencia en curso."""
        if not self._lock.acquire(timeout=_CLOSE_TIMEOUT_S):
            logger.warning("No se pudo liberar la sesión de rembg: hay una inferencia en curso.")
            return
        try:
            self._session = None
            self._providers = ()
        finally:
            self._lock.release()

    # ---- internos (con el bloqueo tomado) ----
    def _ensure(self) -> bool:
        if self._session is not None:
            return False
        started = time.perf_counter()
        try:
            session = self._factory(self._model_name)
        except ProcessingError:
            raise
        except Exception as exc:  # descarga, archivo corrupto, ONNX Runtime...
            raise ProcessingError(
                user_message=_SESSION_ERROR,
                detail=f"No se pudo crear la sesión '{self._model_name}': {exc}",
            ) from exc
        self.last_load_ms = (time.perf_counter() - started) * 1000.0
        self._session = session
        self._providers = _active_providers(session)
        self._loads += 1
        logger.info(
            "Sesión rembg '%s' cargada en %.0f ms (providers: %s)",
            self._model_name, self.last_load_ms, ", ".join(self._providers) or "desconocidos",
        )
        return True

    @staticmethod
    def _rembg_session_factory(model_name: str) -> Any:
        # Import diferido: rembg (onnxruntime) es pesado y no debe frenar el arranque.
        try:
            from rembg import new_session
        except ImportError as exc:
            raise ProcessingError(
                user_message="❌ rembg no está instalado. Ejecuta: pip install -r requirements.txt",
                detail=str(exc),
            ) from exc
        return new_session(model_name)


def _active_providers(session: Any) -> tuple[str, ...]:
    """Providers activos de una sesión de rembg (``inner_session`` de ONNX Runtime), si se pueden leer."""
    try:
        return tuple(session.inner_session.get_providers())
    except Exception:  # noqa: BLE001 - dato informativo: una sesión falsa o distinta no debe fallar
        return ()


def _accepts_session(remove: Callable[..., Any]) -> bool:
    try:
        parameters = inspect.signature(remove).parameters
    except (TypeError, ValueError):
        return False
    return "session" in parameters or any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values()
    )


class BackgroundRemover(ImageOperation):
    """Recibe una imagen, ejecuta rembg y devuelve una imagen RGBA."""

    name = "remove_background"

    def __init__(
        self,
        remove_fn: RemoveFn | None = None,
        session_manager: RembgSessionManager | None = None,
    ) -> None:
        # ``remove_fn`` permite inyectar un reemplazo (tests) sin cargar rembg ni sesión.
        self._remove_fn = remove_fn
        self._sessions = session_manager
        self.last_timings: RemovalTimings | None = None

    @property
    def label(self) -> str:
        return "Fondo"

    def apply(self, image: Image.Image) -> Image.Image:
        return self.apply_with_progress(image, NULL_REPORTER)

    def apply_with_progress(self, image: Image.Image, reporter: ProgressReporter) -> Image.Image:
        started = time.perf_counter()

        def stage(key: str, message: str) -> None:
            label, fraction = _STAGES[key]
            reporter.report(label, fraction, message)

        stage("operation", "Preparando la operación…")
        remove = self._remove_fn or self._load_rembg()
        use_session = (
            self._remove_fn is None and self._sessions is not None and _accepts_session(remove)
        )

        reused, load_ms = True, 0.0
        if use_session:
            assert self._sessions is not None
            reused = self._sessions.is_loaded
            stage(
                "session",
                "Reutilizando el modelo ya cargado…"
                if reused
                else "Cargando el modelo de IA (la primera vez tarda más)…",
            )
            if self._sessions.ensure_loaded():
                reused, load_ms = False, self._sessions.last_load_ms
        else:
            stage("session", "Sin sesión persistente…")

        stage("image", "Preparando la imagen…")
        t = time.perf_counter()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        data = buffer.getvalue()
        prepare_ms = (time.perf_counter() - t) * 1000.0

        stage("inference", "La IA está procesando la imagen…")
        t = time.perf_counter()
        if use_session:
            assert self._sessions is not None
            output = self._sessions.run(lambda session: remove(data, session=session))
        else:
            output = remove(data)
        inference_ms = (time.perf_counter() - t) * 1000.0

        stage("compose", "Componiendo el resultado RGBA…")
        t = time.perf_counter()
        result = Image.open(io.BytesIO(output)).convert("RGBA")
        for key in _PRESERVED_INFO:  # el PNG de rembg no trae PPI ni perfil: se traspasan de la entrada
            if key in image.info:
                result.info[key] = image.info[key]
        compose_ms = (time.perf_counter() - t) * 1000.0

        stage("validate", "Validando el resultado…")
        if result.size != image.size:
            raise ProcessingError(
                detail=f"El resultado ({result.size}) no tiene el tamaño de la imagen ({image.size})."
            )
        reporter.report("Listo", 1.0, "Fondo eliminado.")

        self.last_timings = RemovalTimings(
            input_size=image.size,
            model=self._sessions.model_name if use_session and self._sessions else "(sin sesión)",
            providers=self._sessions.providers if use_session and self._sessions else (),
            session_reused=reused,
            model_load_ms=load_ms,
            prepare_ms=prepare_ms,
            inference_ms=inference_ms,
            compose_ms=compose_ms,
            total_ms=(time.perf_counter() - started) * 1000.0,
        )
        logger.info("RMBG %s", self.last_timings)
        return result

    @staticmethod
    def _load_rembg() -> Callable[..., bytes]:
        # Import diferido: rembg (onnxruntime) es pesado y no debe frenar el arranque
        # ni ser necesario para importar el resto del motor.
        try:
            from rembg import remove
        except ImportError as exc:
            raise ProcessingError(
                user_message="❌ rembg no está instalado. Ejecuta: pip install -r requirements.txt",
                detail=str(exc),
            ) from exc
        return remove
