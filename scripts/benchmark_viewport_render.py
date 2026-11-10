"""scripts/benchmark_viewport_render.py

Mide cuánto tarda ``ViewportRenderer.render`` (recorte + remuestreo, SIN Tk) para
imágenes grandes en escenarios típicos del visor. No mide ``ImageTk.PhotoImage`` ni el
canvas: eso lo registra ``ImagePanel.render_timings`` con la aplicación real.

Uso (desde la raíz del proyecto):  python scripts/benchmark_viewport_render.py [ancho alto]
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from gui.viewport import ViewportModel  # noqa: E402
from gui.viewport_renderer import ViewportRenderer  # noqa: E402

VIEWPORT = (1200, 700)


def timed(fn) -> float:
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000


def scenario_rows(size: tuple[int, int]):
    image = Image.new("RGBA", size, (30, 60, 90, 255))
    renderer = ViewportRenderer()
    renderer.set_image(image)
    model = ViewportModel(size, VIEWPORT)
    cursor = (600, 350)

    first = timed(lambda: renderer.render(model))
    yield "primer render (ajustado, construye niveles)", [first]

    def zoom_steps(factor, n):
        times = []
        for _ in range(n):
            model.zoom_by(factor, cursor)
            times.append(timed(lambda: renderer.render(model)))
        return times

    yield "rueda: 20 pasos de acercar ×1,1", zoom_steps(1.1, 20)
    model.set_zoom(1.0, cursor)
    renderer.render(model)
    times = []
    for i in range(60):
        model.pan_by(-7, -3)
        times.append(timed(lambda: renderer.render(model)))
    yield "paneo al 100 %: 60 pasos", times
    model.set_zoom(0.25, cursor)
    renderer.render(model)
    times = []
    for i in range(60):
        model.pan_by(-5, -2)
        times.append(timed(lambda: renderer.render(model)))
    yield "paneo al 25 %: 60 pasos", times
    model.set_zoom(6.0, cursor)
    renderer.render(model)
    times = []
    for i in range(60):
        model.pan_by(-9, -4)
        times.append(timed(lambda: renderer.render(model)))
    yield "paneo al 600 %: 60 pasos", times


def main() -> None:
    sizes = [(int(sys.argv[1]), int(sys.argv[2]))] if len(sys.argv) == 3 else [(4000, 3000), (8000, 6000), (12000, 9000)]
    for size in sizes:
        print(f"\nImagen {size[0]}×{size[1]} ({size[0] * size[1] / 1e6:.0f} MP), viewport {VIEWPORT[0]}×{VIEWPORT[1]}")
        for label, times in scenario_rows(size):
            ordered = sorted(times)
            p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
            print(f"  {label:<46} media {statistics.mean(times):7.1f} ms   p95 {p95:7.1f} ms   máx {max(times):7.1f} ms")


if __name__ == "__main__":
    main()
