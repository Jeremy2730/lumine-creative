"""Fase 1 de Remove: calcular (preview) y confirmar (commit) son pasos separados."""
import pytest
from PIL import Image

from app.services.processing_service import ProcessingService
from app.services.tool_registry import ToolRegistry
from core.design_engine import DesignEngine
from core.exceptions import NoImageLoadedError, StalePreviewError
from core.image_pipeline import ImagePipeline
from core.models import PreviewResult, ProcessingStatus
from core.operation import ImageOperation


class Paint(ImageOperation):
    name = "paint"

    def __init__(self, color="red"):
        self.color = color

    @property
    def label(self):
        return f"pintar {self.color}"

    def apply(self, image):
        return Image.new("RGBA", image.size, self.color)


class Identity(ImageOperation):
    """Devuelve LA MISMA imagen: cambia el historial pero no la identidad de ``current``."""

    name = "identity"

    def apply(self, image):
        return image


class Boom(ImageOperation):
    name = "boom"

    def apply(self, image):
        raise RuntimeError("fallo técnico")


class FakeIO:
    def load(self, path):
        return Image.new("RGBA", (6, 4), "white")

    def save(self, image, path):
        return path

    def unique_output_path(self, directory, stem):
        return directory / stem


@pytest.fixture
def engine(tmp_path):
    e = DesignEngine(FakeIO())
    e.open_image(tmp_path / "a.png")
    return e


def _state(engine):
    s = engine.snapshot()
    return s.image, s.operations, engine._state.revision, engine._state.status


def pipe(*ops):
    return ImagePipeline(ops)


def test_preview_does_not_modify_the_document(engine):
    before = _state(engine)
    result = engine.preview(pipe(Paint()))
    assert isinstance(result, PreviewResult)
    assert result.image.getpixel((0, 0)) == (255, 0, 0, 255)
    image, ops, rev, status = _state(engine)
    assert image is before[0] and ops == before[1] and rev == before[2] and status == before[3]
    assert engine.snapshot().image.getpixel((0, 0)) == (255, 255, 255, 255)


def test_preview_does_not_touch_status_even_on_failure(engine):
    with pytest.raises(Exception):
        engine.preview(pipe(Boom()))
    assert engine._state.status is ProcessingStatus.IDLE
    assert engine.snapshot().operations == ()


def test_preview_without_image_raises():
    with pytest.raises(NoImageLoadedError):
        DesignEngine(FakeIO()).preview(pipe(Paint()))


def test_commit_confirms_the_result(engine):
    result = engine.preview(pipe(Paint("blue")))
    snap = engine.commit(result)
    assert snap.image is result.image
    assert [o.name for o in snap.operations] == ["paint"]
    assert snap.status is ProcessingStatus.IDLE


def test_commit_confirms_only_once(engine):
    result = engine.preview(pipe(Paint()))
    engine.commit(result)
    with pytest.raises(StalePreviewError):
        engine.commit(result)
    assert len(engine.snapshot().operations) == 1


def test_stale_result_is_rejected_after_another_commit(engine):
    first = engine.preview(pipe(Paint("red")))
    engine.apply(Paint("green"))
    with pytest.raises(StalePreviewError):
        engine.commit(first)
    snap = engine.snapshot()
    assert [o.label for o in snap.operations] == ["pintar green"]
    assert snap.image.getpixel((0, 0)) == (0, 128, 0, 255)


def test_stale_result_is_rejected_after_opening_another_image(engine, tmp_path):
    result = engine.preview(pipe(Paint()))
    engine.open_image(tmp_path / "b.png")
    with pytest.raises(StalePreviewError):
        engine.commit(result)
    assert engine.snapshot().operations == ()


def test_stale_detected_even_when_the_image_object_is_the_same(engine):
    """Por qué no basta ``preview.base is current``: una operación puede devolver la misma imagen."""
    current = engine.snapshot().image
    stale = engine.preview(pipe(Paint()))
    engine.apply(Identity())  # ``current`` sigue siendo el mismo objeto, pero el documento cambió
    assert engine.snapshot().image is current
    with pytest.raises(StalePreviewError):
        engine.commit(stale)


def test_discarding_a_preview_leaves_the_state_untouched(engine):
    before = _state(engine)
    result = engine.preview(pipe(Paint()))
    del result  # descartar = soltarlo
    assert _state(engine) == before


def test_commit_without_image_raises():
    e = DesignEngine(FakeIO())
    with pytest.raises(NoImageLoadedError):
        e.commit(PreviewResult(0, Image.new("RGBA", (1, 1)), ()))


def test_stale_error_has_a_user_message():
    assert "ya no es aplicable" in StalePreviewError().display_message("x")


# ---- compatibilidad: run_pipeline / apply conservan su comportamiento ----
def test_apply_still_commits_and_is_cumulative(engine):
    engine.apply(Paint("red"))
    snap = engine.apply(Identity())
    assert [o.name for o in snap.operations] == ["paint", "identity"]
    assert snap.status is ProcessingStatus.IDLE


def test_run_pipeline_failure_sets_error_and_keeps_document(engine):
    before_image = engine.snapshot().image
    with pytest.raises(Exception):
        engine.run_pipeline(pipe(Paint(), Boom()))
    assert engine._state.status is ProcessingStatus.ERROR
    assert engine.snapshot().image is before_image and engine.snapshot().operations == ()


def test_run_pipeline_sets_processing_during_execution(engine):
    seen = []
    engine.run_pipeline(pipe(Paint()), on_step=lambda op: seen.append(engine._state.status))
    assert seen == [ProcessingStatus.PROCESSING]


def test_revision_increases_on_load_and_commit(engine, tmp_path):
    r0 = engine._state.revision
    engine.apply(Paint())
    assert engine._state.revision == r0 + 1
    engine.open_image(tmp_path / "b.png")
    assert engine._state.revision == r0 + 2


# ---- servicio ----
@pytest.fixture
def service(engine, tmp_path):
    registry = ToolRegistry()
    registry.register("paint", lambda color="red": Paint(color))
    registry.register("boom", lambda: Boom())
    return ProcessingService(engine, registry, tmp_path)


def test_service_preview_then_commit(service):
    result = service.preview_tool("paint", color="blue")
    assert service.snapshot().operations == ()  # aún sin confirmar
    snap = service.commit_preview(result)
    assert snap.operations[0].name == "paint"


def test_service_preview_discard_keeps_document(service):
    before = service.snapshot()
    service.preview_tool("paint")
    after = service.snapshot()
    assert after.image is before.image and after.operations == before.operations


def test_service_apply_tool_unchanged(service):
    snap = service.apply_tool("paint", color="green")
    assert snap.operations[0].label == "pintar green"


def test_service_stale_preview_rejected(service):
    result = service.preview_tool("paint")
    service.apply_tool("paint", color="green")
    with pytest.raises(StalePreviewError):
        service.commit_preview(result)


def test_service_preview_forwards_progress(service):
    class Op(Paint):
        def apply_with_progress(self, image, reporter):
            reporter.report("x", 0.5, "m")
            return self.apply(image)

    service._registry.register("prog", lambda: Op())
    events = []

    class R:
        def report(self, *a):
            events.append(a)

    service.preview_tool("prog", progress=R())
    assert events == [("x", 0.5, "m")]
