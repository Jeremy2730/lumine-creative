"""tests/test_viewport_renderer.py

Responsabilidad:
    - Pruebas de gui/viewport_renderer.py: que los píxeles que produce
      correspondan a la geometría del ViewportModel (sin deformar, voltear
      ni recortar por error), que no modifique la imagen de entrada, que
      reutilice resultados y niveles reducidos en vez de repetir trabajo y
      que no invente halos en los bordes semitransparentes.

No conoce:
    - Ventanas ni widgets; no requiere display (solo Pillow).
"""
import pytest
from PIL import Image

from gui.viewport import ViewportModel
from gui.viewport_renderer import ViewportRenderer

RED, GREEN, BLUE, YELLOW = (255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)


def quadrants(size):
    """Imagen con 4 cuadrantes de color: rojo (arriba-izq), verde (arriba-der), azul (abajo-izq), amarillo."""
    w, h = size
    image = Image.new("RGBA", size)
    image.paste(RED, (0, 0, w // 2, h // 2))
    image.paste(GREEN, (w // 2, 0, w, h // 2))
    image.paste(BLUE, (0, h // 2, w // 2, h))
    image.paste(YELLOW, (w // 2, h // 2, w, h))
    return image


def render(image, viewport, setup=None):
    model = ViewportModel(image.size, viewport)
    if setup:
        setup(model)
    renderer = ViewportRenderer()
    renderer.set_image(image)
    return renderer, model, renderer.render(model)


def corners(view, inset=3):
    w, h = view.image.size
    return (
        view.image.getpixel((inset, inset)),
        view.image.getpixel((w - 1 - inset, inset)),
        view.image.getpixel((inset, h - 1 - inset)),
        view.image.getpixel((w - 1 - inset, h - 1 - inset)),
    )


@pytest.mark.parametrize("size", [(400, 200), (200, 400), (300, 300)])
@pytest.mark.parametrize("viewport", [(936, 466), (300, 700), (500, 500), (90, 60)])
def test_fitted_image_keeps_content_orientation_and_proportions(size, viewport):
    image = quadrants(size)
    _, model, view = render(image, viewport)
    assert corners(view) == (RED, GREEN, BLUE, YELLOW)  # ni volteado ni recortado
    w, h = view.image.size
    assert abs(w / h - size[0] / size[1]) < 0.06  # proporción original (redondeo a píxeles enteros)
    assert (w, h) == model.rendered_size_px
    assert (view.x, view.y) == model.visible_area().destination[:2]


def test_fitted_image_is_centred_in_the_viewport():
    _, _, view = render(quadrants((400, 200)), (936, 600))
    w, h = view.image.size
    assert abs(view.x - (936 - (view.x + w))) <= 1
    assert abs(view.y - (600 - (view.y + h))) <= 1


def test_small_image_is_enlarged_to_use_the_space():
    image = quadrants((40, 20))
    _, model, view = render(image, (936, 466))
    assert model.zoom > 1
    assert view.image.size[0] == 936 or view.image.size[1] == 466  # llena una dimensión
    assert corners(view) == (RED, GREEN, BLUE, YELLOW)


def test_hundred_percent_is_an_exact_copy_of_the_pixels():
    image = Image.effect_noise((300, 200), 60).convert("RGBA")

    def setup(model):
        model.set_zoom(1.0)
        model.pan_to(-100, -60)

    _, model, view = render(image, (100, 80), setup)
    x0, y0, x1, y1 = (round(v) for v in model.visible_area().source)
    assert (x0, y0, x1, y1) == (100, 60, 200, 140)
    assert view.image.tobytes() == image.crop((100, 60, 200, 140)).tobytes()


@pytest.mark.parametrize(
    "pan,expected",
    [((0, 0), RED), ((-200, 0), GREEN), ((0, -100), BLUE), ((-200, -100), YELLOW)],
)
def test_cropped_view_maps_the_viewport_to_the_right_part_of_the_image(pan, expected):
    image = quadrants((400, 200))

    def setup(model):
        model.set_zoom(1.0)
        model.pan_to(*pan)

    _, _, view = render(image, (200, 100), setup)
    assert view.image.size == (200, 100) and (view.x, view.y) == (0, 0)
    assert corners(view) == (expected,) * 4


def test_zoomed_in_view_shows_the_enlarged_region_without_distortion():
    image = quadrants((400, 200))

    def setup(model):
        model.set_zoom(2.0, (0, 0))  # ancla en la esquina: queda arriba a la izquierda
        model.pan_to(0, 0)

    _, _, view = render(image, (200, 100), setup)
    assert view.image.size == (200, 100)
    assert corners(view, 4) == (RED,) * 4  # 200×100 px de pantalla = 100×50 de imagen: solo el rojo


def test_rendering_never_modifies_the_source_image_or_its_metadata():
    image = quadrants((400, 200))
    image.info["dpi"] = (300.0, 300.0)
    before_bytes, before_info = image.tobytes(), dict(image.info)
    renderer = ViewportRenderer()
    renderer.set_image(image)
    model = ViewportModel(image.size, (936, 466))
    for viewport in ((936, 466), (300, 200), (50, 40), (2000, 1500)):
        model.set_viewport_size(*viewport)
        view = renderer.render(model)
        assert view.image is not image  # siempre una imagen nueva
    model.set_zoom(3.0, (10, 10))
    renderer.render(model)
    assert image.tobytes() == before_bytes and dict(image.info) == before_info
    assert image.mode == "RGBA" and image.size == (400, 200)
    assert renderer.source is image


def test_render_returns_the_cached_result_when_nothing_changed():
    renderer, model, first = render(quadrants((400, 200)), (500, 300))
    assert renderer.render(model) is first
    assert renderer.render(model) is first
    model.set_viewport_size(520, 300)
    assert renderer.render(model) is not first


def test_setting_the_same_image_keeps_the_cache_and_a_new_image_clears_it():
    image = quadrants((400, 200))
    renderer, model, first = render(image, (500, 300))
    renderer.set_image(image)
    assert renderer.render(model) is first
    other = quadrants((400, 200))
    renderer.set_image(other)
    assert renderer.render(model) is not first
    assert renderer.source is other and renderer.level_factors == (1,)


def test_model_and_image_must_describe_the_same_size():
    renderer = ViewportRenderer()
    renderer.set_image(quadrants((400, 200)))
    with pytest.raises(ValueError):
        renderer.render(ViewportModel((401, 200), (500, 300)))


def test_nothing_to_render_without_image_or_viewport_area():
    assert ViewportRenderer().render(ViewportModel((10, 10), (100, 100))) is None
    renderer = ViewportRenderer()
    renderer.set_image(quadrants((40, 20)))
    assert renderer.render(ViewportModel((40, 20), (0, 0))) is None


# ----------------------------------------------------------- niveles reducidos

@pytest.fixture
def spies(monkeypatch):
    """Registra sobre qué imagen se llama a reduce() y a resize().

    Pillow, con RGBA, se vuelve a llamar a sí mismo sobre una copia en modo "RGBa"
    (alfa premultiplicado): esas llamadas internas no son del renderizador y se ignoran.
    """
    calls = {"reduce": [], "resize": []}
    real_reduce, real_resize = Image.Image.reduce, Image.Image.resize

    def reduce(self, factor, *args, **kwargs):
        if self.mode != "RGBa":
            calls["reduce"].append((id(self), factor))
        return real_reduce(self, factor, *args, **kwargs)

    def resize(self, size, *args, **kwargs):
        if self.mode != "RGBa":
            calls["resize"].append(id(self))
        return real_resize(self, size, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "reduce", reduce)
    monkeypatch.setattr(Image.Image, "resize", resize)
    return calls


def test_zoomed_out_view_draws_from_a_reduced_level_built_once(spies):
    image = quadrants((4000, 3000))
    renderer = ViewportRenderer()
    renderer.set_image(image)
    model = ViewportModel(image.size, (500, 375))  # zoom 0,125 → nivel 1/8
    renderer.render(model)
    assert renderer.level_factors == (1, 8)
    assert spies["reduce"] == [(id(image), 8)]
    assert id(image) not in spies["resize"]  # la original no se redimensiona
    for viewport in ((450, 340), (480, 360), (300, 225), (400, 300)):  # arrastrar el borde: zoom entre 0,0625 y 0,125
        model.set_viewport_size(*viewport)
        renderer.render(model)
    assert len(spies["reduce"]) == 1  # el nivel se reutilizó
    assert id(image) not in spies["resize"]


def test_levels_are_built_from_the_closest_existing_level(spies):
    image = quadrants((4000, 3000))
    renderer = ViewportRenderer()
    renderer.set_image(image)
    model = ViewportModel(image.size, (2000, 1500), min_zoom=0.01)  # zoom 0,5 → nivel 1/2
    renderer.render(model)
    level2 = renderer._levels[2]
    model.set_viewport_size(500, 375)  # zoom 0,125 → nivel 1/8, a partir del 1/2
    renderer.render(model)
    assert spies["reduce"] == [(id(image), 2), (id(level2), 4)]
    assert renderer.level_factors == (1, 2, 8)


@pytest.mark.parametrize("zoom,factor", [(0.99, 1), (0.5, 2), (0.26, 2), (0.24, 4), (0.125, 8), (0.05, 16)])
def test_level_factor_keeps_the_remaining_scale_between_half_and_one(zoom, factor):
    image = quadrants((4000, 3000))
    renderer = ViewportRenderer()
    renderer.set_image(image)
    model = ViewportModel(image.size, (800, 600), min_zoom=0.01)
    model.set_zoom(zoom)
    renderer.render(model)
    assert max(renderer.level_factors) == factor
    assert 0.5 < model.zoom * factor <= 1.0 + 1e-9


def test_zoom_at_or_above_one_uses_the_original_without_building_levels(spies):
    image = quadrants((400, 200))
    renderer = ViewportRenderer()
    renderer.set_image(image)
    model = ViewportModel(image.size, (936, 466))
    assert model.zoom > 1
    renderer.render(model)
    assert renderer.level_factors == (1,) and spies["reduce"] == []


def test_tiny_images_do_not_build_levels_smaller_than_one_pixel():
    image = quadrants((2, 2))
    renderer = ViewportRenderer()
    renderer.set_image(image)
    model = ViewportModel(image.size, (1, 1), min_zoom=0.001)
    assert model.zoom < 1
    view = renderer.render(model)
    assert view.image.size == (1, 1) and min(renderer._levels[max(renderer.level_factors)].size) >= 1


def test_reducing_does_not_invent_halos_on_semitransparent_edges():
    """Blanco opaco | rojo totalmente transparente: ningún píxel con alfa debe volverse rosado."""
    image = Image.new("RGBA", (800, 400), (255, 0, 0, 0))
    image.paste((255, 255, 255, 255), (0, 0, 403, 400))  # el borde corta un bloque de 8 px
    _, _, view = render(image, (100, 50))
    row = [view.image.getpixel((x, view.image.height // 2)) for x in range(view.image.width)]
    visible = [px for px in row if px[3] > 0]
    assert visible and all(min(px[:3]) >= 250 for px in visible)
    assert any(0 < px[3] < 255 for px in row)  # hay borde suave, y aun así es blanco
