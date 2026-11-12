"""tests/test_file_controller.py

Responsabilidad:
    - Pruebas de los flujos de FileController sobre la pila real
      (build_controllers) con una vista falsa: abrir, Guardar, Guardar
      como, cancelaciones, errores, aviso de transparencia, cambios
      pendientes al abrir/cerrar y exclusión de tareas.

No conoce:
    - Widgets ni diálogos reales (no requiere display).
"""
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.application import build_controllers
from app.controllers.design_controller import StatusLevel
from config.settings import Settings
from core.exceptions import ImageSaveError
from tools.image_loader import has_transparency

TITLE = "Herramienta para Diseño"


class FakeView:
    """Implementa DesignView + FileView y registra todo lo que se le pregunta."""

    def __init__(self):
        self.statuses, self.snapshots, self.titles, self.busy_calls = [], [], [], []
        self.open_answer: str | None = None
        self.save_answers: list[str | None] = []
        self.unsaved_answer = "cancel"
        self.flatten_answer = True
        self.exit_while_busy_answer = False
        self.exit_while_busy_asked: list[bool] = []
        self.asked = {"open": 0, "save": 0, "unsaved": 0, "flatten": 0}
        self.suggestions = []
        self.exited = 0
        self.on_snapshot = None  # imita a MainWindow.show_snapshot → FileController.on_snapshot

    # DesignView
    def show_snapshot(self, snapshot):
        self.snapshots.append(snapshot)
        if self.on_snapshot:
            self.on_snapshot(snapshot)

    def show_status(self, message, level):
        self.statuses.append((message, level))

    def set_busy(self, busy):
        self.busy_calls.append(busy)

    # FileView
    def ask_open_path(self):
        self.asked["open"] += 1
        return self.open_answer

    def ask_save_path(self, suggestion):
        self.asked["save"] += 1
        self.suggestions.append(suggestion)
        return self.save_answers.pop(0) if self.save_answers else None

    def ask_unsaved_changes(self, name):
        self.asked["unsaved"] += 1
        return self.unsaved_answer

    def ask_flatten_to_jpg(self):
        self.asked["flatten"] += 1
        return self.flatten_answer

    def ask_exit_while_processing(self, has_unsaved_changes):
        self.exit_while_busy_asked.append(has_unsaved_changes)
        return self.exit_while_busy_answer

    def set_window_title(self, title):
        self.titles.append(title)

    def exit_application(self):
        self.exited += 1


def wait(design):
    deadline = time.time() + 5
    while time.time() < deadline:
        design.process_pending()
        if not design.is_busy:
            return
        time.sleep(0.005)
    raise AssertionError("timeout esperando la tarea")


@pytest.fixture
def app(tmp_path):
    settings = Settings(output_dir=tmp_path / "descargas", app_title=TITLE)
    design, files = build_controllers(settings)
    view = FakeView()
    design.attach_view(view)
    files.attach_view(view)
    view.on_snapshot = files.on_snapshot
    src = tmp_path / "origen"
    src.mkdir()
    out = tmp_path / "salida"
    return SimpleNamespace(design=design, files=files, view=view, src=src, out=out, tmp=tmp_path)


def make_png(folder: Path, name="foto.png", transparent=False, size=(40, 20)) -> Path:
    if transparent:
        img = Image.new("RGBA", size, (255, 0, 0, 0))
        for x in range(size[0] // 2, size[0]):
            for y in range(size[1]):
                img.putpixel((x, y), (0, 0, 255, 255))
    else:
        img = Image.new("RGB", size, "teal")
        for x in range(size[0] // 2, size[0]):  # borde nítido: el enfoque SÍ cambia la imagen
            for y in range(size[1]):
                img.putpixel((x, y), (255, 140, 0))
    path = folder / name
    img.save(path)
    return path


def open_ok(app, path):
    app.files.open_path(path)
    wait(app.design)


def edit(app):
    app.design.sharpen()
    wait(app.design)


def last_status(app):
    return app.view.statuses[-1]


# ---------------- abrir ----------------

@pytest.mark.parametrize("name,fmt", [("a.png", "PNG"), ("a.jpg", "JPEG"), ("a.jpeg", "JPEG")])
def test_opening_png_jpg_jpeg_leaves_a_clean_document_and_sets_the_title(app, name, fmt):
    path = app.src / name
    Image.new("RGB", (40, 20), "teal").save(path, fmt)
    open_ok(app, path)
    assert app.files.document is not None and not app.files.has_unsaved_changes()
    assert app.view.titles[-1] == f"{name} — {TITLE}"
    assert app.view.snapshots[-1].size == (40, 20)
    assert "Imagen cargada" in last_status(app)[0]


def test_title_before_opening_anything_is_the_app_title(app):
    assert app.files.window_title() == TITLE


def test_a_failed_open_keeps_the_current_document_and_shows_a_clear_error(app):
    good = make_png(app.src, "buena.png")
    open_ok(app, good)
    title_before = app.view.titles[-1]
    bad = app.src / "rota.png"
    bad.write_bytes(b"esto no es una imagen")
    open_ok(app, bad)
    message, level = last_status(app)
    assert level is StatusLevel.ERROR and "No se pudo abrir" in message
    assert app.files.document.origin_path == good
    assert app.view.titles[-1] == title_before
    assert app.design._service.snapshot().size == (40, 20)


def test_open_dialog_cancel_does_nothing_and_a_chosen_path_opens(app):
    app.view.open_answer = None
    app.files.open_dialog()
    assert app.files.document is None and app.view.snapshots == []
    app.view.open_answer = str(make_png(app.src))
    app.files.open_dialog()
    wait(app.design)
    assert app.files.document is not None


# ---------------- cambios pendientes ----------------

def test_an_edit_marks_the_document_dirty_and_saving_cleans_it(app):
    open_ok(app, make_png(app.src))
    assert not app.files.has_unsaved_changes()
    edit(app)
    assert app.files.has_unsaved_changes() and app.view.titles[-1] == f"foto.png * — {TITLE}"
    app.view.save_answers = [str(app.out / "final.png")]
    app.files.save()
    wait(app.design)
    assert not app.files.has_unsaved_changes() and app.view.titles[-1] == f"final.png — {TITLE}"


def test_a_stale_document_is_dropped_if_the_image_was_opened_another_way(app):
    open_ok(app, make_png(app.src, "a.png"))
    app.design.open_image(make_png(app.src, "b.png"))  # vía heredada, sin FileController
    wait(app.design)
    assert app.files.document is None and app.view.titles[-1] == TITLE


# ---------------- guardar / guardar como ----------------

def test_first_save_asks_for_a_destination_and_never_overwrites_the_original(app):
    original = make_png(app.src)
    before_bytes, before_mtime = original.read_bytes(), original.stat().st_mtime_ns
    open_ok(app, original)
    edit(app)
    target = app.out / "resultado.png"
    app.view.save_answers = [str(target)]
    app.files.save()
    wait(app.design)
    assert app.view.asked["save"] == 1
    suggestion = app.view.suggestions[0]
    assert suggestion.filename == "foto_editada.png" and suggestion.directory == app.src
    assert target.exists()
    assert original.read_bytes() == before_bytes and original.stat().st_mtime_ns == before_mtime
    assert app.files.document.save_path == target and not app.files.document.is_untitled


def test_save_without_a_destination_but_cancelling_changes_nothing(app):
    open_ok(app, make_png(app.src))
    edit(app)
    busy_before = list(app.view.busy_calls)
    app.view.save_answers = []  # el usuario cancela el diálogo
    app.files.save()
    wait(app.design)
    assert app.view.asked["save"] == 1
    assert app.files.document.is_untitled and app.files.has_unsaved_changes()
    assert not app.out.exists() and list(app.src.glob("*editada*")) == []
    assert app.view.busy_calls == busy_before  # el guardado cancelado ni se despachó


def test_second_save_writes_to_the_same_destination_without_asking(app):
    open_ok(app, make_png(app.src))
    target = app.out / "doc.png"
    app.view.save_answers = [str(target)]
    app.files.save()
    wait(app.design)
    first = target.read_bytes()
    edit(app)
    app.files.save()
    wait(app.design)
    assert app.view.asked["save"] == 1  # no volvió a preguntar
    assert target.read_bytes() != first and not app.files.has_unsaved_changes()


def test_save_as_changes_the_destination_and_cancelling_keeps_the_old_one(app):
    open_ok(app, make_png(app.src))
    first, second = app.out / "uno.png", app.out / "dos.png"
    app.view.save_answers = [str(first)]
    app.files.save()
    wait(app.design)
    app.view.save_answers = []  # cancela Guardar como
    app.files.save_as()
    assert app.files.document.save_path == first
    app.view.save_answers = [str(second)]
    app.files.save_as()
    wait(app.design)
    assert app.files.document.save_path == second and second.exists()


def test_a_failed_write_keeps_state_and_destination_and_can_be_retried(app, monkeypatch):
    open_ok(app, make_png(app.src))
    edit(app)
    real_write = app.files._service.write

    def broken(*args, **kwargs):
        raise ImageSaveError(detail="disco lleno")

    monkeypatch.setattr(app.files._service, "write", broken)
    app.view.save_answers = [str(app.out / "x.png")]
    app.files.save()
    wait(app.design)
    message, level = last_status(app)
    assert level is StatusLevel.ERROR and "No se pudo guardar" in message
    assert app.files.document.is_untitled and app.files.has_unsaved_changes()
    assert not (app.out / "x.png").exists()
    monkeypatch.setattr(app.files._service, "write", real_write)  # reintento
    app.view.save_answers = [str(app.out / "x.png")]
    app.files.save()
    wait(app.design)
    assert (app.out / "x.png").exists() and not app.files.has_unsaved_changes()


def test_a_real_write_error_leaves_no_partial_final_file(app, monkeypatch):
    open_ok(app, make_png(app.src))
    edit(app)

    def partial(self, fp, *args, **kwargs):
        Path(fp).write_bytes(b"PARCIAL")
        raise OSError("disco lleno")

    monkeypatch.setattr(Image.Image, "save", partial)
    target = app.out / "x.png"
    app.view.save_answers = [str(target)]
    app.files.save()
    wait(app.design)
    assert not target.exists() and list(app.out.iterdir()) == []
    assert app.files.document.is_untitled and app.files.has_unsaved_changes()


def test_an_unsupported_extension_is_refused_without_writing_or_changing_state(app):
    open_ok(app, make_png(app.src))
    app.view.save_answers = [str(app.out / "x.bmp")]
    app.files.save()
    wait(app.design)
    message, level = last_status(app)
    assert level is StatusLevel.WARNING and ".png" in message
    assert app.files.document.is_untitled and not app.out.exists()


# ---------------- transparencia / JPG ----------------

def test_saving_png_keeps_transparency_without_asking_to_flatten(app):
    open_ok(app, make_png(app.src, "t.png", transparent=True))
    app.view.save_answers = [str(app.out / "t.png")]
    app.files.save()
    wait(app.design)
    assert app.view.asked["flatten"] == 0
    with Image.open(app.out / "t.png") as saved:
        assert saved.mode == "RGBA" and saved.getchannel("A").getextrema() == (0, 255)


def test_jpg_with_transparency_cancelled_writes_nothing_and_changes_no_state(app):
    open_ok(app, make_png(app.src, "t.png", transparent=True))
    busy_before = list(app.view.busy_calls)
    app.view.flatten_answer = False
    app.view.save_answers = [str(app.out / "t.jpg")]
    app.files.save()
    wait(app.design)
    assert app.view.asked["flatten"] == 1
    assert not (app.out / "t.jpg").exists()
    assert app.files.document.is_untitled and app.view.busy_calls == busy_before


def test_jpg_with_transparency_accepted_saves_a_white_copy_and_keeps_the_work_image(app):
    open_ok(app, make_png(app.src, "t.png", transparent=True))
    app.view.flatten_answer = True
    app.view.save_answers = [str(app.out / "t.jpg")]
    app.files.save()
    wait(app.design)
    with Image.open(app.out / "t.jpg") as saved:
        assert saved.format == "JPEG" and min(saved.getpixel((2, 10))) >= 250
    assert has_transparency(app.design._service.snapshot().image)  # imagen de trabajo intacta
    assert app.files.document.save_format == "JPEG"


def test_opaque_image_saved_as_jpg_does_not_ask_to_flatten(app):
    open_ok(app, make_png(app.src))
    app.view.save_answers = [str(app.out / "o.jpg")]
    app.files.save()
    wait(app.design)
    assert app.view.asked["flatten"] == 0 and (app.out / "o.jpg").exists()


# ---------------- abrir otro archivo con cambios pendientes ----------------

def _dirty_doc(app):
    open_ok(app, make_png(app.src, "a.png"))
    edit(app)
    return make_png(app.src, "b.png", size=(10, 10))


def test_clean_document_opens_another_file_without_any_prompt(app):
    open_ok(app, make_png(app.src, "a.png"))
    open_ok(app, make_png(app.src, "b.png", size=(10, 10)))
    assert app.view.asked["unsaved"] == 0 and app.files.document.origin_path.name == "b.png"


def test_pending_changes_cancel_keeps_the_current_document(app):
    other = _dirty_doc(app)
    app.view.unsaved_answer = "cancel"
    app.files.open_path(other)
    wait(app.design)
    assert app.view.asked["unsaved"] == 1 and app.files.document.origin_path.name == "a.png"
    assert app.files.has_unsaved_changes()


def test_pending_changes_discard_opens_the_other_file(app):
    other = _dirty_doc(app)
    app.view.unsaved_answer = "discard"
    app.files.open_path(other)
    wait(app.design)
    assert app.files.document.origin_path == other and not app.files.has_unsaved_changes()
    assert not app.out.exists()  # no se guardó nada


def test_pending_changes_save_then_opens_the_other_file(app):
    other = _dirty_doc(app)
    app.view.unsaved_answer = "save"
    app.view.save_answers = [str(app.out / "a_final.png")]
    app.files.open_path(other)
    wait(app.design)
    wait(app.design)
    assert (app.out / "a_final.png").exists()
    assert app.files.document.origin_path == other


def test_pending_changes_save_cancelled_does_not_open_the_other_file(app):
    other = _dirty_doc(app)
    app.view.unsaved_answer = "save"
    app.view.save_answers = []  # cancela Guardar como
    app.files.open_path(other)
    wait(app.design)
    assert app.files.document.origin_path.name == "a.png" and app.files.has_unsaved_changes()


def test_pending_changes_save_failing_does_not_open_the_other_file(app, monkeypatch):
    other = _dirty_doc(app)

    def broken(*args, **kwargs):
        raise ImageSaveError(detail="disco lleno")

    monkeypatch.setattr(app.files._service, "write", broken)
    app.view.unsaved_answer = "save"
    app.view.save_answers = [str(app.out / "a.png")]
    app.files.open_path(other)
    wait(app.design)
    assert app.files.document.origin_path.name == "a.png" and app.files.has_unsaved_changes()


# ---------------- cerrar la aplicación ----------------

def test_exit_with_a_clean_document_closes_without_asking(app):
    open_ok(app, make_png(app.src))
    app.files.request_exit()
    assert app.view.exited == 1 and app.view.asked["unsaved"] == 0


def test_exit_with_no_document_closes(app):
    app.files.request_exit()
    assert app.view.exited == 1


def test_exit_pending_changes_cancel_discard_and_save(app):
    open_ok(app, make_png(app.src))
    edit(app)
    app.view.unsaved_answer = "cancel"
    app.files.request_exit()
    assert app.view.exited == 0
    app.view.unsaved_answer = "discard"
    app.files.request_exit()
    assert app.view.exited == 1
    app.view.unsaved_answer = "save"
    app.view.save_answers = [str(app.out / "cierre.png")]
    app.files.request_exit()
    wait(app.design)
    assert (app.out / "cierre.png").exists() and app.view.exited == 2


def test_exit_does_not_close_if_save_is_cancelled_or_fails(app, monkeypatch):
    open_ok(app, make_png(app.src))
    edit(app)
    app.view.unsaved_answer = "save"
    app.view.save_answers = []
    app.files.request_exit()
    wait(app.design)
    assert app.view.exited == 0

    def broken(*args, **kwargs):
        raise ImageSaveError(detail="disco lleno")

    monkeypatch.setattr(app.files._service, "write", broken)
    app.view.save_answers = [str(app.out / "x.png")]
    app.files.request_exit()
    wait(app.design)
    assert app.view.exited == 0 and app.files.has_unsaved_changes()


# ---------------- exclusión de tareas (una sola compuerta) ----------------

def _hold_gate(app, seconds=0.3):
    """Ocupa la compuerta compartida con una tarea lenta."""
    assert app.design.run_task(
        start="lento", work=lambda: time.sleep(seconds), on_success=lambda _: None, error="x"
    )


def test_open_save_and_exit_are_refused_while_a_task_is_running(app):
    open_ok(app, make_png(app.src))
    edit(app)
    _hold_gate(app)
    assert app.design.is_busy
    other = make_png(app.src, "b.png")
    app.view.open_answer = str(other)
    app.files.open_dialog()
    app.files.open_path(other)
    app.files.save()
    app.files.save_as()
    assert app.view.asked == {"open": 0, "save": 0, "unsaved": 0, "flatten": 0}  # ni un diálogo
    assert app.view.exited == 0 and app.files.document.origin_path.name == "foto.png"
    wait(app.design)


def test_exit_while_a_task_is_running_asks_and_keeps_running_if_declined(app):
    open_ok(app, make_png(app.src))
    edit(app)  # hay cambios sin guardar
    _hold_gate(app)
    app.view.exit_while_busy_answer = False
    app.files.request_exit()
    assert app.view.exit_while_busy_asked == [True]  # avisa de que también se pierden cambios
    assert app.view.exited == 0 and app.view.asked["unsaved"] == 0
    wait(app.design)
    assert not app.design.is_busy  # la tarea terminó con normalidad


def test_exit_while_a_task_is_running_closes_and_discards_if_accepted(app):
    open_ok(app, make_png(app.src))
    _hold_gate(app)
    app.view.exit_while_busy_answer = True
    app.files.request_exit()
    assert app.view.exit_while_busy_asked == [False] and app.view.exited == 1
    n = len(app.view.statuses)
    time.sleep(0.45)
    app.design.process_pending()  # el resultado de la tarea abandonada no llega a la vista
    assert len(app.view.statuses) == n


def test_a_tool_cannot_start_while_a_file_task_is_running_and_vice_versa(app):
    open_ok(app, make_png(app.src))
    _hold_gate(app)
    assert app.design.run_task(
        start="otra", work=lambda: None, on_success=lambda _: None, error="x"
    ) is False
    n = len(app.view.snapshots)
    app.design.sharpen()  # rechazada por la misma compuerta
    wait(app.design)
    assert len(app.view.snapshots) == n


def test_shared_gate_is_a_single_flag_and_single_runner(app):
    assert app.files._design is app.design  # no hay un segundo controlador de tareas
    assert not hasattr(app.files, "_busy") and not hasattr(app.files, "_runner")
