import pytest
from PIL import Image

from core.design_engine import DesignEngine
from core.exceptions import DesignToolError, NoImageLoadedError, ProcessingError
from core.image_pipeline import ImagePipeline
from core.operation import ImageOperation
from tools.background_remover import BackgroundRemover
from tools.image_loader import ImageLoader
from tools.size_resolution import SizeResolutionAdjuster
from tools.image_sharpener import ImageSharpener


class Recorder(ImageOperation):
    name = "recorder"

    def __init__(self, tag, log):
        self.tag, self.log = tag, log

    @property
    def label(self):
        return self.tag

    def apply(self, image):
        self.log.append(self.tag)
        return image.copy()


class Boom(ImageOperation):
    name = "boom"

    def apply(self, image):
        raise RuntimeError("fallo técnico")


class Controlled(ImageOperation):
    name = "controlled"

    def apply(self, image):
        raise DesignToolError("⚠️ mensaje propio")


def test_pipeline_runs_in_order_and_supports_adding_steps():
    log = []
    pipe = ImagePipeline([Recorder("a", log)]).add(Recorder("b", log)).add(Recorder("c", log))
    result = pipe.run(Image.new("RGBA", (4, 4)))
    assert log == ["a", "b", "c"] and len(pipe) == 3
    assert [op.label for op in result.applied] == ["a", "b", "c"]


def test_empty_pipeline_returns_image_unchanged():
    img = Image.new("RGBA", (4, 4))
    assert ImagePipeline().run(img).image is img


def test_unexpected_errors_are_wrapped_and_controlled_errors_pass_through():
    img = Image.new("RGBA", (4, 4))
    with pytest.raises(ProcessingError) as info:
        ImagePipeline([Boom()]).run(img)
    assert info.value.user_message is None  # el orquestador decide el texto
    with pytest.raises(DesignToolError) as info2:
        ImagePipeline([Controlled()]).run(img)
    assert info2.value.user_message == "⚠️ mensaje propio"


@pytest.fixture
def engine(tmp_path):
    src = tmp_path / "foto.png"
    Image.new("RGB", (400, 200), "blue").save(src)
    eng = DesignEngine(ImageLoader({".png"}))
    eng.open_image(src)
    return eng


def test_engine_accumulates_operations(engine):
    engine.apply(BackgroundRemover(remove_fn=lambda data: data))
    engine.apply(SizeResolutionAdjuster(10, 5, 300, resample=True))
    snap = engine.apply(ImageSharpener())
    assert snap.size == (1181, 591)
    assert [op.name for op in snap.operations] == [
        "remove_background",
        "size_resolution",
        "sharpen",
    ]


def test_engine_state_unchanged_when_operation_fails(engine):
    before = engine.snapshot()
    with pytest.raises(ProcessingError):
        engine.run_pipeline(ImagePipeline([ImageSharpener(), Boom()]))
    after = engine.snapshot()
    assert after.image is before.image and after.operations == ()


def test_engine_requires_image_and_saves_without_overwriting(engine, tmp_path):
    empty = DesignEngine(ImageLoader({".png"}))
    with pytest.raises(NoImageLoadedError):
        empty.apply(ImageSharpener())
    out = tmp_path / "resultado"
    assert engine.save(out).name == "foto_editada.png"
    assert engine.save(out).name == "foto_editada_2.png"
