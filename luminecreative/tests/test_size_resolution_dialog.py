"""Regresión: el campo Resolución debe precargarse con el DPI REAL de la
imagen (``original_dpi``), nunca con el valor recomendado (``default_dpi``,
300). Requiere un display real (tkinter); se omite si no hay uno.
"""
import pytest
from PIL import Image

ctk = pytest.importorskip("customtkinter")


def _make_root():
    try:
        root = ctk.CTk()
        root.withdraw()
        return root
    except Exception:
        pytest.skip("No hay display disponible para probar la GUI.")


@pytest.fixture
def root():
    r = _make_root()
    yield r
    r.destroy()


@pytest.mark.parametrize("real_dpi", [72, 150, 300])
def test_dialog_prefills_dpi_field_with_the_real_dpi_not_the_recommended_default(
    root, real_dpi
):
    from tools.size_resolution.dialog import SizeResolutionDialog

    dialog = SizeResolutionDialog(
        root,
        controller=_FakeController(),
        current_size_px=(736, 1104),
        initial_width_cm=10.0,
        initial_height_cm=15.0,
        original_dpi=real_dpi,
        dpi_is_reliable=True,
        default_dpi=300,  # deliberadamente distinto de real_dpi, salvo cuando real_dpi==300
        max_recommended_px=20_000,
        on_accept=lambda *args: None,
    )
    try:
        assert float(dialog._dpi_entry.get()) == pytest.approx(real_dpi)
    finally:
        dialog.destroy()


def test_changing_length_unit_converts_displayed_value_round_trip(root):
    """10 cm -> 100 mm -> 10 cm, sin alterar el tamaño/resolución reales
    (el ejemplo exacto del encargo)."""
    from tools.size_resolution import SizeResolutionController
    from tools.size_resolution.dialog import SizeResolutionDialog

    class _FakeDesignController:
        def check_positive(self, value, label):
            return value

        def parse_positive(self, text, label):
            from core.exceptions import ValidationError

            try:
                value = float(text.replace(",", "."))
            except ValueError:
                raise ValidationError(f"⚠️ {label}: número inválido.") from None
            if value <= 0:
                raise ValidationError(f"⚠️ {label} debe ser mayor que cero.")
            return value

        def run_tool(self, *args, **kwargs):
            pass

        def warn(self, message):
            pass

    controller = SizeResolutionController(_FakeDesignController())
    dialog = SizeResolutionDialog(
        root,
        controller=controller,
        current_size_px=(1181, 1772),
        initial_width_cm=10.0,
        initial_height_cm=15.0,
        original_dpi=300,
        dpi_is_reliable=True,
        default_dpi=300,
        max_recommended_px=20_000,
        on_accept=lambda *args: None,
    )
    try:
        assert dialog._width_entry.get() == "10"  # sin ceros decimales sobrantes
        dialog._on_length_unit_selected("Milímetros")
        assert dialog._width_entry.get() == "100"
        assert dialog._width_unit.get() == "Milímetros"
        assert dialog._height_unit.get() == "Milímetros"  # ambos desplegables sincronizados

        dialog._on_length_unit_selected("Centímetros")
        assert dialog._width_entry.get() == "10"

        # Resolución: 300 PPI -> 118.11 px/cm -> ~300 PPI (ejemplo del encargo)
        dialog._resolution_unit.set("px/cm")
        dialog._on_resolution_unit_changed("px/cm")
        assert dialog._dpi_entry.get() == "118.11"

        dialog._resolution_unit.set("PPI")
        dialog._on_resolution_unit_changed("PPI")
        assert float(dialog._dpi_entry.get()) == pytest.approx(300, abs=0.01)
    finally:
        dialog.destroy()


def test_switching_unit_does_not_change_resample_or_proportion_state(root):
    from tools.size_resolution.dialog import SizeResolutionDialog

    dialog = SizeResolutionDialog(
        root,
        controller=_FakeController(),
        current_size_px=(736, 1104),
        initial_width_cm=10.0,
        initial_height_cm=15.0,
        original_dpi=300,
        dpi_is_reliable=True,
        default_dpi=300,
        max_recommended_px=20_000,
        on_accept=lambda *args: None,
    )
    try:
        resample_before = bool(dialog._resample_checkbox.get())
        proportion_before = bool(dialog._proportion_checkbox.get())
        dialog._on_length_unit_selected("Pulgadas")
        dialog._resolution_unit.set("px/cm")
        dialog._on_resolution_unit_changed("px/cm")
        assert bool(dialog._resample_checkbox.get()) == resample_before
        assert bool(dialog._proportion_checkbox.get()) == proportion_before
    finally:
        dialog.destroy()


def test_opening_the_dialog_does_not_modify_the_image(root):
    from tools.size_resolution.dialog import SizeResolutionDialog

    image = Image.new("RGBA", (10, 10), (1, 2, 3, 255))
    before_bytes = image.tobytes()
    before_info = dict(image.info)

    dialog = SizeResolutionDialog(
        root,
        controller=_FakeController(),
        current_size_px=(736, 1104),
        initial_width_cm=10.0,
        initial_height_cm=15.0,
        original_dpi=72,
        dpi_is_reliable=True,
        default_dpi=300,
        max_recommended_px=20_000,
        on_accept=lambda *args: None,
    )
    try:
        assert image.tobytes() == before_bytes
        assert image.info == before_info
    finally:
        dialog.destroy()


class _FakeController:
    """Solo lo que el diálogo toca en __init__ (vista previa inicial)."""

    resample_methods = ("LANCZOS", "BICUBIC", "BILINEAR", "NEAREST")

    def parse_positive(self, text, label):
        from core.exceptions import ValidationError

        try:
            value = float(text)
        except ValueError:
            raise ValidationError(f"⚠️ {label}: introduce un número válido.") from None
        if value <= 0:
            raise ValidationError(f"⚠️ {label} debe ser mayor que cero.")
        return value

    def preview_size_px(self, width_cm, height_cm, dpi):
        return round(width_cm * dpi / 2.54), round(height_cm * dpi / 2.54)

    # ---- unidades: por defecto cm/PPI, igual que el comportamiento previo ----
    def length_to_cm(self, value, unit, dpi):
        if unit == "mm":
            return value / 10.0
        if unit == "px":
            return value * 2.54 / dpi
        if unit == "in":
            return value * 2.54
        return value

    def length_from_cm(self, value_cm, unit, dpi):
        if unit == "mm":
            return value_cm * 10.0
        if unit == "px":
            return value_cm * dpi / 2.54
        if unit == "in":
            return value_cm / 2.54
        return value_cm

    def resolution_to_ppi(self, value, unit):
        return value * 2.54 if unit == "px/cm" else value

    def resolution_from_ppi(self, dpi, unit):
        return dpi / 2.54 if unit == "px/cm" else dpi
