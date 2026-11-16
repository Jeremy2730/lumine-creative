"""Tablero de transparencia del renderizador (solo visual). Pillow puro, sin Tk."""
import hashlib

import pytest
from PIL import Image

from gui.viewport import ViewportModel
from gui.viewport_renderer import CHECKER_CELL_PX, CHECKER_DARK, CHECKER_LIGHT, ViewportRenderer

DARK, LIGHT = CHECKER_DARK[:3], CHECKER_LIGHT[:3]
CELL = CHECKER_CELL_PX


def digest(image):
    return hashlib.sha256(image.mode.encode() + image.tobytes()).hexdigest()


def transparent(size=(64, 64)):
    return Image.new("RGBA", size, (0, 0, 0, 0))


def setup(image, viewport=None, *, checker=True, **kw):
    renderer = ViewportRenderer()
    renderer.set_checkerboard(checker, **kw)
    renderer.set_image(image)
    model = ViewportModel(image.size, viewport or image.size)
    return renderer, model


def px(view, x, y):
    return view.image.getpixel((x, y))[:3]


def test_disabled_by_default_and_rgba_is_returned_untouched():
    image = transparent()
    renderer = ViewportRenderer()
    assert renderer.checkerboard is False
    renderer.set_image(image)
    view = renderer.render(ViewportModel(image.size, image.size))
    assert view.image.mode == "RGBA" and view.image.getpixel((3, 3)) == (0, 0, 0, 0)


def test_fully_transparent_pixels_show_the_two_neutral_tones_as_a_checkerboard():
    renderer, model = setup(transparent())
    view = renderer.render(model)
    assert view.image.mode == "RGB" and view.image.size == (64, 64)
    assert px(view, 0, 0) == DARK and px(view, CELL - 1, CELL - 1) == DARK
    assert px(view, CELL, 0) == LIGHT and px(view, 0, CELL) == LIGHT
    assert px(view, CELL, CELL) == DARK and px(view, 2 * CELL, 0) == DARK
    assert DARK[0] == DARK[1] == DARK[2] and LIGHT[0] == LIGHT[1] == LIGHT[2]  # neutros


def test_semi_transparent_pixels_blend_with_the_pattern_underneath():
    image = Image.new("RGBA", (64, 64), (255, 0, 0, 128))
    renderer, model = setup(image)
    view = renderer.render(model)
    for (x, y), base in (((0, 0), 204), ((CELL, 0), 242)):
        r, g, b = px(view, x, y)
        a = 128 / 255
        assert r == pytest.approx(255 * a + base * (1 - a), abs=2)
        assert g == pytest.approx(base * (1 - a), abs=2) and b == pytest.approx(g, abs=1)


def test_opaque_pixels_are_not_altered_and_a_fully_opaque_view_is_returned_as_is():
    opaque = Image.new("RGBA", (64, 64), (10, 200, 30, 255))
    renderer, model = setup(opaque)
    view = renderer.render(model)
    assert view.image.mode == "RGBA" and view.image.getpixel((5, 5)) == (10, 200, 30, 255)

    mixed = Image.new("RGBA", (64, 64), (10, 200, 30, 255))
    mixed.paste((0, 0, 0, 0), (32, 0, 64, 64))
    renderer, model = setup(mixed)
    view = renderer.render(model)
    assert px(view, 5, 5) == (10, 200, 30)  # la parte opaca conserva su color exacto
    assert px(view, 32, 0) in (DARK, LIGHT) and px(view, 40, 0) in (DARK, LIGHT)  # la transparente, tablero


def test_the_source_image_and_its_levels_are_never_modified():
    image = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
    image.paste((255, 0, 0, 255), (0, 0, 200, 150))
    before = digest(image)
    renderer, model = setup(image, (100, 75))  # zoom < 1: se construyen niveles reducidos
    renderer.render(model)
    model.pan_by(-5, -5)
    renderer.render(model)
    assert renderer.source is image and image.mode == "RGBA" and digest(image) == before
    assert len(renderer.level_factors) > 1
    for factor in renderer.level_factors:
        level = renderer._levels[factor]
        assert level.mode == "RGBA" and level.getchannel("A").getextrema()[0] == 0  # sigue habiendo alfa


def test_the_rendered_image_is_a_new_object_not_the_source():
    image = transparent()
    renderer, model = setup(image)
    assert renderer.render(model).image is not image
    renderer2, model2 = setup(image, checker=False)
    assert renderer2.render(model2).image is not image  # incluso la copia exacta al 100 %


def test_only_the_visible_crop_is_composited():
    image = transparent((4000, 3000))
    renderer, _ = setup(image)
    model = ViewportModel(image.size, (120, 90))
    model.set_zoom(1.0)
    view = renderer.render(model)
    assert view.image.size == (120, 90)  # nunca la imagen entera


def test_the_pattern_follows_panning_because_it_is_anchored_to_the_image():
    image = transparent((400, 300))
    renderer, _ = setup(image)
    model = ViewportModel(image.size, (100, 80))
    model.set_zoom(1.0)
    model.pan_to(0, 0)
    assert px(renderer.render(model), 0, 0) == DARK
    model.pan_to(-CELL, 0)  # la imagen se desplazó una celda: lo que hay en (0,0) ahora es una celda clara
    assert px(renderer.render(model), 0, 0) == LIGHT
    model.pan_to(-CELL, -CELL)
    assert px(renderer.render(model), 0, 0) == DARK
    model.pan_to(-3, -5)  # un desplazamiento que no es múltiplo de la celda: el patrón sigue pegado a la imagen
    view = renderer.render(model)
    assert px(view, 0, 0) == DARK and px(view, CELL - 3, 0) == LIGHT and px(view, 0, CELL - 5) == LIGHT


@pytest.mark.parametrize("zoom", [0.7, 1.0, 2.0, 5.0, 16.0])
def test_cell_size_is_constant_on_screen_at_any_zoom(zoom):
    image = transparent((800, 600))
    renderer, _ = setup(image)
    model = ViewportModel(image.size, (200, 100))
    model.set_zoom(zoom)
    model.pan_to(0, 0)
    view = renderer.render(model)
    assert px(view, 0, 0) == DARK and px(view, CELL - 1, 0) == DARK
    assert px(view, CELL, 0) == LIGHT and px(view, 2 * CELL - 1, 0) == LIGHT and px(view, 2 * CELL, 0) == DARK


def test_pattern_accompanies_zoom_anchored_to_the_image_origin():
    image = transparent((800, 600))
    renderer, _ = setup(image)
    model = ViewportModel(image.size, (200, 100))
    model.set_zoom(1.0)
    model.pan_to(-50, -50)
    a = renderer.render(model)
    model.set_zoom(2.0, anchor=(0, 0))  # el origen de la imagen sigue fuera de pantalla: el patrón no salta
    b = renderer.render(model)
    assert a.image.size == b.image.size == (200, 100)
    assert px(b, 0, 0) in (DARK, LIGHT)


def test_toggling_invalidates_the_last_render():
    image = transparent()
    renderer, model = setup(image, checker=False)
    off = renderer.render(model)
    assert off.image.mode == "RGBA"
    renderer.set_checkerboard(True)
    on = renderer.render(model)
    assert on is not off and on.image.mode == "RGB"
    renderer.set_checkerboard(False)
    assert renderer.render(model).image.mode == "RGBA"


def test_repeated_renders_reuse_the_result_and_the_pattern():
    renderer, model = setup(transparent())
    first = renderer.render(model)
    assert renderer.render(model) is first
    cached = renderer._pattern
    model.pan_by(0, 0)
    renderer.render(model)
    assert renderer._pattern is cached


def test_custom_cell_size_and_validation():
    renderer, model = setup(transparent(), cell=4)
    view = renderer.render(model)
    assert px(view, 3, 0) == DARK and px(view, 4, 0) == LIGHT
    for bad in (0, -1, 2.5, True, "8"):
        with pytest.raises(ValueError):
            renderer.set_checkerboard(True, bad)


def test_other_modes_with_transparency_are_supported():
    la = Image.new("LA", (32, 32), (0, 0))
    renderer, model = setup(la)
    view = renderer.render(model)
    assert view.image.mode == "RGB" and px(view, 0, 0) == DARK
    opaque_rgb = Image.new("RGB", (32, 32), (1, 2, 3))
    renderer, model = setup(opaque_rgb)
    assert renderer.render(model).image.getpixel((0, 0)) == (1, 2, 3)  # sin alfa: nada que componer


def test_viewport_larger_than_image_only_paints_the_image_rectangle():
    image = transparent((50, 50))
    renderer, _ = setup(image)
    model = ViewportModel(image.size, (300, 200))
    model.set_zoom(1.0)
    view = renderer.render(model)
    assert view.image.size == (50, 50) and (view.x, view.y) == (125, 75)
    assert px(view, 0, 0) == DARK  # el patrón arranca en la esquina de la imagen
