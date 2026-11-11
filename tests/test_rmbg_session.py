"""tests/test_rmbg_session.py

Responsabilidad:
    - Sesión reutilizable de rembg (RembgSessionManager + BackgroundRemover):
      una sola inicialización, reutilización entre operaciones, exclusión
      mutua, errores de inicialización, liberación, inyección de ``remove_fn``,
      salida RGBA y tamaño conservado, tiempos registrados.
    - Progreso por etapas: ProgressReporter (monotónico), etapas del
      remover, entrega en el hilo principal por BackgroundTaskRunner,
      DesignController (eventos, vistas sin ``show_progress``, tareas
      terminadas), documento intacto ante fallos, el resto de herramientas
      y que la interfaz (el hilo principal) no se bloquee durante la inferencia.

No conoce:
    - rembg real ni modelos: todo usa sesiones y funciones falsas, sin descargas.
      (La prueba con el modelo real es opcional: tests/test_rmbg_real_model.py.)
"""
import io
import sys
import threading
import time

import pytest
from PIL import Image

import tools.background_remover as bg
from app.application import build_tool_registry
from app.controllers.design_controller import DesignController, StatusLevel
from app.services.processing_service import ProcessingService
from app.services.task_runner import BackgroundTaskRunner
from app.services.tool_registry import ToolRegistry
from config.settings import Settings
from core.design_engine import DesignEngine
from core.exceptions import ProcessingError
from core.progress import NULL_REPORTER, ProgressEvent, ProgressReporter
from tools.background_remover import BackgroundRemover, RembgSessionManager
from tools.comic_effect import ComicEffect
from tools.image_loader import ImageLoader
from tools.image_sharpener import ImageSharpener

STAGE_ORDER = ["Preparación", "Modelo", "Imagen", "Inferencia", "Composición", "Validación", "Listo"]


class FakeSession:
    class inner_session:  # noqa: N801 - imita session.inner_session de rembg
        @staticmethod
        def get_providers():
            return ["CPUExecutionProvider"]


class Factory:
    """Fábrica de sesiones falsas que cuenta cuántas creó."""

    def __init__(self, delay=0.0, fail_times=0):
        self.calls, self.delay, self.fail_times = 0, delay, fail_times

    def __call__(self, model_name):
        self.calls += 1
        if self.fail_times:
            self.fail_times -= 1
            raise OSError("no se pudo leer el modelo")
        time.sleep(self.delay)
        return FakeSession()


def passthrough(data, session=None):
    assert session is not None, "debió recibir la sesión compartida"
    return data


@pytest.fixture
def use_fake_rembg(monkeypatch):
    monkeypatch.setattr(BackgroundRemover, "_load_rembg", staticmethod(lambda: passthrough))


def make_image(size=(40, 30), mode="RGBA"):
    image = Image.new(mode, size, (200, 30, 30, 128) if mode == "RGBA" else (200, 30, 30))
    image.info["dpi"] = (300.0, 300.0)
    return image


class Collector:
    def __init__(self):
        self.events = []
        self.reporter = ProgressReporter(self.events.append)

    @property
    def stages(self):
        seen = []
        for e in self.events:
            if not seen or seen[-1] != e.stage:
                seen.append(e.stage)
        return seen


# ------------------------------------------------------------ ProgressReporter
def test_reporter_clamps_never_goes_back_and_skips_duplicates():
    c = Collector()
    r = c.reporter
    r.report("A", -1, "x")
    r.report("A", 0.5, "x")
    r.report("A", 0.2, "y")  # retroceso: se conserva 0.5
    r.report("A", 0.2, "y")  # idéntico tras corregir: no se repite
    r.report("B", 7, "z")
    assert [e.fraction for e in c.events] == [0.0, 0.5, 0.5, 1.0]
    assert [e.message for e in c.events] == ["x", "x", "y", "z"]
    assert all(0.0 <= e.fraction <= 1.0 for e in c.events)
    assert r.last == c.events[-1]


@pytest.mark.parametrize("bad", [float("nan"), "0.5", None, True])
def test_reporter_rejects_non_numbers(bad):
    with pytest.raises(ValueError):
        ProgressReporter(lambda e: None).report("A", bad, "x")


def test_null_reporter_delivers_nothing():
    NULL_REPORTER.report("A", 0.3, "x")
    assert NULL_REPORTER.last is None


# ---------------------------------------------------------------- la sesión
def test_session_is_created_once_and_reused_across_calls(use_fake_rembg):
    factory = Factory()
    manager = RembgSessionManager(session_factory=factory)
    remover = BackgroundRemover(session_manager=manager)
    for _ in range(3):
        remover.apply(make_image())
    assert factory.calls == 1 and manager.load_count == 1 and manager.is_loaded


def test_session_is_shared_by_every_operation_the_registry_creates(use_fake_rembg):
    factory = Factory()
    manager = RembgSessionManager(session_factory=factory)
    registry = build_tool_registry(Settings(), manager)
    a, b = registry.create("remove_background"), registry.create("remove_background")
    assert a is not b and a._sessions is manager and b._sessions is manager
    a.apply(make_image())
    b.apply(make_image())
    assert factory.calls == 1


def test_default_registry_shares_one_manager_between_operations():
    registry = build_tool_registry(Settings())
    a, b = registry.create("remove_background"), registry.create("remove_background")
    assert a._sessions is not None and a._sessions is b._sessions


def test_the_model_is_not_loaded_when_building_the_registry_or_the_remover():
    factory = Factory()
    manager = RembgSessionManager(session_factory=factory)
    build_tool_registry(Settings(), manager).create("remove_background")
    assert factory.calls == 0 and not manager.is_loaded  # carga diferida


def test_concurrent_first_use_creates_the_session_only_once():
    factory = Factory(delay=0.1)
    manager = RembgSessionManager(session_factory=factory)
    barrier = threading.Barrier(4)

    def worker():
        barrier.wait()
        manager.ensure_loaded()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert factory.calls == 1


def test_two_operations_never_use_the_session_at_the_same_time():
    manager = RembgSessionManager(session_factory=Factory())
    inside, overlaps, lock = [0], [], threading.Lock()

    def unsafe_inference(session):
        with lock:
            inside[0] += 1
            if inside[0] > 1:
                overlaps.append(1)
        time.sleep(0.05)
        with lock:
            inside[0] -= 1

    threads = [threading.Thread(target=lambda: manager.run(unsafe_inference)) for _ in range(5)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert overlaps == []


def test_initialisation_errors_are_reported_and_not_cached(use_fake_rembg):
    factory = Factory(fail_times=1)
    manager = RembgSessionManager(session_factory=factory)
    remover = BackgroundRemover(session_manager=manager)
    with pytest.raises(ProcessingError) as info:
        remover.apply(make_image())
    assert "modelo" in info.value.display_message("x") and "no se pudo leer" in str(info.value)
    assert not manager.is_loaded
    remover.apply(make_image())  # el siguiente intento vuelve a intentarlo y funciona
    assert factory.calls == 2 and manager.is_loaded


def test_missing_rembg_gives_a_clear_message(monkeypatch):
    monkeypatch.setitem(sys.modules, "rembg", None)  # fuerza ImportError
    with pytest.raises(ProcessingError) as info:
        RembgSessionManager().ensure_loaded()
    assert "rembg no está instalado" in info.value.display_message("x")


def test_close_releases_the_session_and_a_later_use_reloads_it(use_fake_rembg):
    factory = Factory()
    manager = RembgSessionManager(session_factory=factory)
    BackgroundRemover(session_manager=manager).apply(make_image())
    manager.close()
    assert not manager.is_loaded and manager.providers == ()
    BackgroundRemover(session_manager=manager).apply(make_image())
    assert factory.calls == 2


def test_close_does_not_hang_if_an_inference_is_running(monkeypatch):
    monkeypatch.setattr(bg, "_CLOSE_TIMEOUT_S", 0.05)
    manager = RembgSessionManager(session_factory=Factory())
    started, release = threading.Event(), threading.Event()

    def long_inference(session):
        started.set()
        release.wait(2)

    thread = threading.Thread(target=lambda: manager.run(long_inference))
    thread.start()
    started.wait(1)
    t0 = time.time()
    manager.close()  # no puede tomar el bloqueo: vuelve pronto sin liberar
    assert time.time() - t0 < 1 and manager.is_loaded
    release.set()
    thread.join()


# ---------------------------------------------- compatibilidad y propiedades
def test_remove_fn_injection_still_works_and_never_touches_the_session():
    factory = Factory()
    manager = RembgSessionManager(session_factory=factory)
    out = BackgroundRemover(remove_fn=lambda data: data, session_manager=manager).apply(make_image())
    assert out.mode == "RGBA" and factory.calls == 0


def test_a_remove_function_without_session_parameter_does_not_create_a_session(monkeypatch):
    monkeypatch.setattr(BackgroundRemover, "_load_rembg", staticmethod(lambda: (lambda data: data)))
    factory = Factory()
    BackgroundRemover(session_manager=RembgSessionManager(session_factory=factory)).apply(make_image())
    assert factory.calls == 0


@pytest.mark.parametrize("mode, size", [("RGBA", (40, 30)), ("RGB", (17, 51)), ("RGBA", (1, 1))])
def test_output_is_rgba_with_the_input_size_and_the_input_is_untouched(use_fake_rembg, mode, size):
    src = make_image(size, mode)
    before = (src.tobytes(), src.size, src.mode, dict(src.info))
    out = BackgroundRemover(session_manager=RembgSessionManager(session_factory=Factory())).apply(src)
    assert out.mode == "RGBA" and out.size == size and out is not src
    assert (src.tobytes(), src.size, src.mode, dict(src.info)) == before
    if mode == "RGBA":
        assert out.getpixel((0, 0)) == (200, 30, 30, 128)  # la transparencia se conserva


def test_a_result_with_a_different_size_is_rejected(monkeypatch):
    def shrinking(data, session=None):
        small = Image.open(io.BytesIO(data)).resize((5, 5))
        out = io.BytesIO()
        small.save(out, "PNG")
        return out.getvalue()

    monkeypatch.setattr(BackgroundRemover, "_load_rembg", staticmethod(lambda: shrinking))
    with pytest.raises(ProcessingError):
        BackgroundRemover(session_manager=RembgSessionManager(session_factory=Factory())).apply(make_image())


def test_timings_distinguish_cold_and_reused_sessions(use_fake_rembg):
    manager = RembgSessionManager(session_factory=Factory(delay=0.05))
    remover = BackgroundRemover(session_manager=manager)
    remover.apply(make_image((64, 48)))
    cold = remover.last_timings
    remover.apply(make_image((64, 48)))
    warm = remover.last_timings
    assert not cold.session_reused and cold.model_load_ms >= 50
    assert warm.session_reused and warm.model_load_ms == 0
    assert cold.input_size == (64, 48) and cold.model == "u2net"
    assert cold.providers == ("CPUExecutionProvider",)
    for t in (cold, warm):
        assert t.total_ms >= t.prepare_ms + t.inference_ms + t.compose_ms - 1e-6 and min(
            t.prepare_ms, t.inference_ms, t.compose_ms
        ) >= 0


# -------------------------------------------------------------- etapas
def test_all_stages_are_reported_in_order_and_progress_never_goes_back(use_fake_rembg):
    c = Collector()
    manager = RembgSessionManager(session_factory=Factory())
    BackgroundRemover(session_manager=manager).apply_with_progress(make_image(), c.reporter)
    assert c.stages == STAGE_ORDER
    fractions = [e.fraction for e in c.events]
    assert fractions == sorted(fractions) and fractions[0] == 0.0 and fractions[-1] == 1.0
    assert all(0.0 <= f <= 1.0 for f in fractions)


def test_inference_does_not_invent_progress(use_fake_rembg):
    c = Collector()
    BackgroundRemover(session_manager=RembgSessionManager(session_factory=Factory())).apply_with_progress(
        make_image(), c.reporter
    )
    inference = [e for e in c.events if e.stage == "Inferencia"]
    assert len(inference) == 1  # un solo evento: sin porcentajes falsos mientras dura
    assert "IA" in inference[0].message


def test_reused_session_is_announced_instead_of_loading(use_fake_rembg):
    manager = RembgSessionManager(session_factory=Factory())
    remover = BackgroundRemover(session_manager=manager)
    cold, warm = Collector(), Collector()
    remover.apply_with_progress(make_image(), cold.reporter)
    remover.apply_with_progress(make_image(), warm.reporter)
    message = lambda c: next(e.message for e in c.events if e.stage == "Modelo")  # noqa: E731
    assert "Cargando" in message(cold) and "Reutilizando" in message(warm)


# ------------------------------------------- runner / hilos / controlador
def test_progress_events_are_delivered_on_the_draining_thread_and_before_the_result():
    runner = BackgroundTaskRunner()
    main = threading.get_ident()
    seen, worker_threads = [], []

    def work(reporter):
        worker_threads.append(threading.get_ident())
        for i in range(5):
            reporter.report("E", i / 4, f"paso {i}")
        return "ok"

    runner.submit(
        work,
        lambda r: seen.append(("result", threading.get_ident())),
        lambda e: seen.append(("error", e)),
        on_progress=lambda ev: seen.append(("progress", threading.get_ident(), ev.fraction)),
    )
    deadline = time.time() + 3
    while not any(s[0] == "result" for s in seen) and time.time() < deadline:
        runner.drain()
        time.sleep(0.005)
    assert worker_threads and worker_threads[0] != main
    assert all(s[1] == main for s in seen if s[0] != "error")
    kinds = [s[0] for s in seen]
    assert kinds == ["progress"] * 5 + ["result"]  # el resultado nunca antecede a su progreso
    assert [s[2] for s in seen if s[0] == "progress"] == sorted(s[2] for s in seen if s[0] == "progress")


def test_runner_without_on_progress_calls_work_with_no_arguments():
    runner = BackgroundTaskRunner()
    got = []
    runner.submit(lambda: 7, got.append, lambda e: got.append(e))
    deadline = time.time() + 3
    while not got and time.time() < deadline:
        runner.drain()
        time.sleep(0.005)
    assert got == [7]


def test_closed_runner_discards_pending_callbacks():
    runner = BackgroundTaskRunner()
    got = []
    runner.submit(lambda: 1, got.append, got.append)
    time.sleep(0.1)
    runner.close()
    runner.drain()
    assert got == []


class View:
    def __init__(self, with_progress=True):
        self.statuses, self.snapshots, self.busy, self.progress = [], [], [], []
        if with_progress:
            self.show_progress = self.progress.append

    def show_snapshot(self, snapshot):
        self.snapshots.append(snapshot)

    def show_status(self, message, level):
        self.statuses.append((message, level))

    def set_busy(self, busy):
        self.busy.append(busy)


def build(tmp_path, remover_factory, with_progress=True):
    registry = ToolRegistry()
    registry.register("remove_background", remover_factory)
    registry.register("comic_effect", ComicEffect)
    registry.register("sharpen", ImageSharpener)
    service = ProcessingService(DesignEngine(ImageLoader({".png"})), registry, tmp_path / "out")
    controller = DesignController(service, BackgroundTaskRunner())
    view = View(with_progress)
    controller.attach_view(view)
    src = tmp_path / "foto.png"
    Image.new("RGBA", (120, 80), (10, 200, 30, 255)).save(src)
    controller.open_image(src)
    wait(controller)
    return controller, view, service


def wait(controller, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        controller.process_pending()
        if not controller.is_busy:
            return
        time.sleep(0.005)
    raise AssertionError("timeout")


def test_controller_forwards_stage_progress_to_the_view_end_to_end(tmp_path, use_fake_rembg):
    manager = RembgSessionManager(session_factory=Factory())
    controller, view, service = build(tmp_path, lambda: BackgroundRemover(session_manager=manager))
    view.progress.clear()
    controller.remove_background()
    wait(controller)
    stages = []
    for e in view.progress:
        if not stages or stages[-1] != e.stage:
            stages.append(e.stage)
    assert stages == STAGE_ORDER
    fractions = [e.fraction for e in view.progress]
    assert fractions == sorted(fractions) and fractions[-1] == 1.0
    assert view.busy[-2:] == [True, False]  # (la apertura previa también alternó)
    snap = service.snapshot()
    assert snap.image.mode == "RGBA" and snap.size == (120, 80)
    assert view.statuses[-1][1] is StatusLevel.SUCCESS


def test_view_without_show_progress_still_works(tmp_path, use_fake_rembg):
    manager = RembgSessionManager(session_factory=Factory())
    controller, view, service = build(
        tmp_path, lambda: BackgroundRemover(session_manager=manager), with_progress=False
    )
    controller.remove_background()
    wait(controller)
    assert view.statuses[-1][1] is StatusLevel.SUCCESS


def test_late_progress_events_are_ignored_once_the_task_finished(tmp_path):
    controller, view, _ = build(tmp_path, lambda: BackgroundRemover(remove_fn=lambda d: d))
    assert not controller.is_busy
    controller._on_progress(ProgressEvent("X", 0.5, "tarde"))
    assert view.progress == []


def test_a_failed_initialisation_is_reported_and_leaves_the_document_untouched(tmp_path, use_fake_rembg):
    factory = Factory(fail_times=1)
    manager = RembgSessionManager(session_factory=factory)
    controller, view, service = build(tmp_path, lambda: BackgroundRemover(session_manager=manager))
    before = service.snapshot()
    before_bytes = before.image.tobytes()
    controller.remove_background()
    wait(controller)
    message, level = view.statuses[-1]
    assert level is StatusLevel.ERROR and "modelo" in message
    after = service.snapshot()
    assert after.image is before.image and after.image.tobytes() == before_bytes
    assert after.operations == before.operations and not controller.is_busy
    assert view.busy[-1] is False


def test_a_failure_during_inference_leaves_the_document_untouched(tmp_path, monkeypatch):
    def boom(data, session=None):
        raise RuntimeError("onnx falló")

    monkeypatch.setattr(BackgroundRemover, "_load_rembg", staticmethod(lambda: boom))
    manager = RembgSessionManager(session_factory=Factory())
    controller, view, service = build(tmp_path, lambda: BackgroundRemover(session_manager=manager))
    before = service.snapshot()
    controller.remove_background()
    wait(controller)
    assert view.statuses[-1][1] is StatusLevel.ERROR
    assert service.snapshot().image is before.image and service.snapshot().operations == before.operations


def test_the_other_tools_still_work_and_emit_no_progress(tmp_path):
    controller, view, service = build(tmp_path, lambda: BackgroundRemover(remove_fn=lambda d: d))
    view.progress.clear()
    controller.comic_effect()
    wait(controller)
    controller.sharpen()
    wait(controller)
    assert [op.label for op in service.snapshot().operations] == ["Semitono", "Nitidez"]
    assert view.progress == []  # sin etapas reales: la vista mantiene su barra indeterminada
    assert view.statuses[-1][1] is StatusLevel.SUCCESS


def test_interface_thread_stays_responsive_during_inference(tmp_path, monkeypatch):
    def slow(data, session=None):
        time.sleep(0.4)
        return data

    monkeypatch.setattr(BackgroundRemover, "_load_rembg", staticmethod(lambda: slow))
    manager = RembgSessionManager(session_factory=Factory(delay=0.1))
    controller, view, _ = build(tmp_path, lambda: BackgroundRemover(session_manager=manager))
    view.progress.clear()
    controller.remove_background()
    ticks, progress_while_busy = 0, 0
    deadline = time.time() + 5
    while controller.is_busy and time.time() < deadline:
        before = len(view.progress)
        controller.process_pending()  # lo que hace el sondeo de 50 ms de MainWindow
        if controller.is_busy:
            progress_while_busy += len(view.progress) - before
        ticks += 1
        time.sleep(0.01)
    assert not controller.is_busy
    assert ticks >= 20  # el hilo principal siguió girando durante ~0,5 s de trabajo
    assert progress_while_busy >= 3  # y recibió etapas MIENTRAS la tarea seguía en curso


def test_ppi_and_icc_profile_are_carried_over_to_the_result(use_fake_rembg):
    src = make_image((40, 30), "RGB")
    src.info["dpi"] = (300.0, 300.0)
    src.info["icc_profile"] = b"perfil-de-prueba"
    out = BackgroundRemover(session_manager=RembgSessionManager(session_factory=Factory())).apply(src)
    assert out.info["dpi"] == (300.0, 300.0) and out.info["icc_profile"] == b"perfil-de-prueba"
    assert src.info["dpi"] == (300.0, 300.0)  # la entrada no se toca


def test_an_image_without_ppi_gets_none_invented(use_fake_rembg):
    out = BackgroundRemover(session_manager=RembgSessionManager(session_factory=Factory())).apply(
        Image.new("RGB", (10, 10), "red")
    )
    assert "dpi" not in out.info
