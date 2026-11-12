"""Prueba el controlador con una vista falsa: no requiere GUI ni rembg."""
import time

import pytest
from PIL import Image

from app.controllers.design_controller import DesignController, StatusLevel
from app.services.processing_service import ProcessingService
from app.services.task_runner import BackgroundTaskRunner
from app.services.tool_registry import ToolRegistry
from core.design_engine import DesignEngine
from core.exceptions import ValidationError
from tools.background_remover import BackgroundRemover
from tools.comic_effect import ComicEffect
from tools.image_loader import ImageLoader
from tools.image_sharpener import ImageSharpener
from tools.size_resolution import SizeResolutionAdjuster, SizeResolutionController


class FakeView:
    def __init__(self):
        self.statuses, self.snapshots, self.busy_calls = [], [], []

    def show_snapshot(self, snapshot):
        self.snapshots.append(snapshot)

    def show_status(self, message, level):
        self.statuses.append((message, level))

    def set_busy(self, busy):
        self.busy_calls.append(busy)


def _failing_remover():
    def remove(_data):
        raise RuntimeError("modelo caído")

    return BackgroundRemover(remove_fn=remove)


@pytest.fixture
def setup(tmp_path):
    registry = ToolRegistry()
    registry.register("remove_background", _failing_remover)
    registry.register("comic_effect", ComicEffect)
    registry.register(
        "size_resolution",
        lambda width_cm, height_cm, dpi, resample, method="LANCZOS": SizeResolutionAdjuster(
            width_cm, height_cm, dpi, resample=resample, method=method
        ),
    )
    registry.register("sharpen", ImageSharpener)
    service = ProcessingService(DesignEngine(ImageLoader({".png"})), registry, tmp_path / "resultado")
    controller = DesignController(service, BackgroundTaskRunner())
    view = FakeView()
    controller.attach_view(view)
    src = tmp_path / "foto.png"
    Image.new("RGB", (400, 200), "green").save(src)
    return controller, view, src


def wait(controller):
    deadline = time.time() + 5
    while time.time() < deadline:
        controller.process_pending()
        if not controller.is_busy:
            return
        time.sleep(0.01)
    raise AssertionError("timeout")


def test_full_flow_open_size_resolution_sharpen_save(setup, tmp_path):
    controller, view, src = setup
    size_resolution = SizeResolutionController(controller)
    controller.open_image(src)
    wait(controller)
    size_resolution.apply(10, 5, 300, resample=True)
    wait(controller)
    controller.sharpen()
    wait(controller)
    controller.save()
    wait(controller)
    assert view.snapshots[-1].size == (1181, 591)
    assert (tmp_path / "resultado" / "foto_editada.png").exists()
    assert view.busy_calls == [True, False] * 4


def test_actions_without_image_only_warn(setup):
    controller, view, _ = setup
    controller.sharpen()
    controller.save()
    assert all(level is StatusLevel.WARNING for _, level in view.statuses)
    assert not controller.is_busy


def test_comic_effect_is_independent_from_remove_background(setup):
    controller, view, src = setup
    controller.open_image(src)
    wait(controller)
    controller.comic_effect()
    wait(controller)
    message, level = view.statuses[-1]
    assert level is StatusLevel.SUCCESS
    assert view.snapshots[-1].operations[-1].label == "Semitono"


def test_tool_failure_shows_friendly_message_not_traceback(setup):
    controller, view, src = setup
    controller.open_image(src)
    wait(controller)
    controller.remove_background()
    wait(controller)
    message, level = view.statuses[-1]
    assert message == "❌ No se pudo eliminar el fondo." and level is StatusLevel.ERROR
    assert "Traceback" not in message and "modelo" not in message


def test_size_resolution_resample_on_changes_pixels_and_saves_dpi(setup, tmp_path):
    controller, view, src = setup
    size_resolution = SizeResolutionController(controller)
    controller.open_image(src)
    wait(controller)
    size_resolution.apply(10, 10, 300, resample=True)
    wait(controller)
    snap = view.snapshots[-1]
    assert snap.size == (1181, 1181)
    assert snap.dpi == 300.0
    controller.save()
    wait(controller)
    saved = next((tmp_path / "resultado").iterdir())
    reopened = Image.open(saved)
    assert reopened.info["dpi"][0] == pytest.approx(300, abs=0.01)


def test_size_resolution_resample_off_keeps_pixels(setup):
    controller, view, src = setup
    size_resolution = SizeResolutionController(controller)
    controller.open_image(src)
    wait(controller)
    original_size = view.snapshots[-1].size
    size_resolution.apply(50, 25, 150, resample=False)
    wait(controller)
    snap = view.snapshots[-1]
    assert snap.size == original_size  # los píxeles no cambian
    assert snap.dpi == 150.0


def test_size_resolution_rejects_invalid_values_without_dispatching(setup):
    controller, view, src = setup
    size_resolution = SizeResolutionController(controller)
    controller.open_image(src)
    wait(controller)
    for width, height, dpi in [(0, 10, 300), (10, -1, 300), (10, 10, 0)]:
        size_resolution.apply(width, height, dpi, resample=True)
        assert not controller.is_busy
        assert view.statuses[-1][1] is StatusLevel.WARNING


def test_size_resolution_without_image_only_warns(setup):
    controller, view, _ = setup
    SizeResolutionController(controller).apply(10, 10, 300, resample=True)
    assert view.statuses[-1][1] is StatusLevel.WARNING
    assert not controller.is_busy


def test_resample_methods_includes_lanczos(setup):
    controller, _, _ = setup
    assert "LANCZOS" in SizeResolutionController(controller).resample_methods


def test_size_resolution_preview_helpers_do_not_touch_the_image_or_busy_state(setup):
    controller, view, src = setup
    controller.open_image(src)
    wait(controller)
    size_resolution = SizeResolutionController(controller)
    assert size_resolution.preview_size_px(10, 10, 300) == (1181, 1181)
    assert size_resolution.paired_dimension_cm((736, 1104), 10, "width") == pytest.approx(15.0)
    assert size_resolution.effective_dpi_from_cm(736, 10) == pytest.approx(186.94, abs=0.01)
    assert size_resolution.cm_from_dpi(736, 300) == pytest.approx(6.23, abs=0.01)
    # ninguna de estas llamadas debió abrir un hilo ni cambiar la imagen
    assert not controller.is_busy
    assert len(view.snapshots) == 1


def test_check_positive_and_parse_positive_are_generic_validators(setup):
    controller, _, _ = setup
    assert controller.check_positive(5.0, "La medida") == 5.0
    assert controller.parse_positive(" 12,5 ", "La medida") == 12.5
    for bad in ["", "abc", "0", "-1"]:
        with pytest.raises(ValidationError):
            controller.parse_positive(bad, "La medida")
