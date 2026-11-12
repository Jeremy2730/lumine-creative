"""scripts/benchmark_rmbg.py

Mide la eliminación de fondo por etapas (carga del modelo, preparación, inferencia,
composición, total) y la memoria del proceso. Dos modos:

  python scripts/benchmark_rmbg.py            # SIN modelo: mide solo lo que rodea a la inferencia
                                              # (codificar PNG / decodificar y pasar a RGBA) con una
                                              # función que devuelve la imagen tal cual. No dice nada
                                              # del coste del modelo.
  python scripts/benchmark_rmbg.py --real     # CON rembg y el modelo real (necesita rembg instalado y
                                              # el modelo descargado, o red para descargarlo).

En modo --real compara, para cada tamaño:
  - antes:   rembg.remove(datos) SIN sesión (rembg crea una sesión nueva en cada llamada: el
             comportamiento anterior de la aplicación),
  - después: sesión compartida (RembgSessionManager): ejecución 1 (fría), 2 y 3 (reutilizada).

Opciones: --sizes 640x480,1920x1080,4000x3000   --runs N (repeticiones "antes", por defecto 3)
"""
from __future__ import annotations

import argparse
import io
import os
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from tools.background_remover import BackgroundRemover, RembgSessionManager  # noqa: E402

DEFAULT_SIZES = "640x480,1920x1080,4000x3000"


def rss_mb() -> float | None:
    """Memoria residente del proceso (MB) o None si no se puede leer."""
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / 1e6
    except Exception:  # noqa: BLE001
        pass
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1e3
    except OSError:
        pass
    return None


def fmt_mb(value: float | None) -> str:
    return "n/d" if value is None else f"{value:.0f}"


def synthetic_photo(size: tuple[int, int]) -> Image.Image:
    """Degradado con ruido y un disco: contenido de tipo fotográfico para codificar/decodificar."""
    w, h = size
    rng = np.random.default_rng(0)
    x = np.linspace(0, 255, w, dtype=np.float32)[None, :, None]
    y = np.linspace(0, 255, h, dtype=np.float32)[:, None, None]
    base = np.concatenate([np.broadcast_to(x, (h, w, 1)), np.broadcast_to(y, (h, w, 1)),
                           np.broadcast_to((x + y) / 2, (h, w, 1))], axis=2)
    noise = rng.normal(0, 6, (h, w, 3)).astype(np.float32)
    array = np.clip(base + noise, 0, 255).astype(np.uint8)
    yy, xx = np.ogrid[:h, :w]
    array[(yy - h / 2) ** 2 + (xx - w / 2) ** 2 < (min(w, h) / 3) ** 2] = (210, 60, 50)
    return Image.fromarray(array, "RGB")


def parse_sizes(text: str) -> list[tuple[int, int]]:
    return [tuple(int(v) for v in item.lower().split("x")) for item in text.split(",")]  # type: ignore[misc]


def row(label: str, t, rss: float | None) -> str:
    load = f"{t.model_load_ms:8.0f}" if t.model_load_ms else "       –"
    return (
        f"| {label:<22} | {load} | {t.prepare_ms:8.0f} | {t.inference_ms:9.0f} | "
        f"{t.compose_ms:8.0f} | {t.total_ms:8.0f} | {fmt_mb(rss):>8} |"
    )


HEADER = (
    "| Ejecución              | Carga ms | Prepar. ms | Inferencia ms | Compos. ms | Total ms | RSS MB |\n"
    "|------------------------|---------:|-----------:|--------------:|-----------:|---------:|-------:|"
)


def run_overhead(sizes) -> None:
    print("MODO SIN MODELO: la 'inferencia' es una función que devuelve los bytes sin tocarlos.")
    print("Solo mide el coste de codificar/decodificar; NO es el coste de RMBG.\n")

    class _Session:
        pass

    manager = RembgSessionManager(session_factory=lambda name: _Session())
    for size in sizes:
        image = synthetic_photo(size)
        remover = BackgroundRemover(session_manager=manager)
        BackgroundRemover._load_rembg = staticmethod(lambda: (lambda data, session=None: data))  # type: ignore[method-assign]
        print(f"### Entrada {size[0]}×{size[1]} ({size[0] * size[1] / 1e6:.1f} MP)\n{HEADER}")
        for n in (1, 2, 3):
            remover.apply(image)
            print(row(f"{n} (sin modelo)", remover.last_timings, rss_mb()))
        print()


def run_real(sizes, runs: int) -> None:
    try:
        import rembg
        from rembg import remove
    except ImportError as exc:
        sys.exit(f"rembg no está instalado ({exc}). Instala requirements.txt para usar --real.")
    import onnxruntime as ort

    print(f"rembg {getattr(rembg, '__version__', '?')} · onnxruntime {ort.__version__} · "
          f"disponibles: {ort.get_available_providers()} · {platform.platform()} · CPUs: {os.cpu_count()}")
    print(f"RSS al empezar (sin modelo): {fmt_mb(rss_mb())} MB\n")
    for size in sizes:
        image = synthetic_photo(size)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        data = buffer.getvalue()
        print(f"### Entrada {size[0]}×{size[1]} ({size[0] * size[1] / 1e6:.1f} MP)")
        print("Antes: rembg.remove(datos) sin sesión (sesión nueva en cada llamada)")
        for n in range(1, runs + 1):
            started = time.perf_counter()
            remove(data)
            print(f"  llamada {n}: {(time.perf_counter() - started) * 1000:8.0f} ms   RSS {fmt_mb(rss_mb())} MB")
        print("Después: sesión compartida\n" + HEADER)
        manager = RembgSessionManager()  # sesión nueva: la ejecución 1 es fría
        remover = BackgroundRemover(session_manager=manager)
        for n, label in enumerate(("1 (fría)", "2 (caliente)", "3 (reutilizada)"), start=1):
            remover.apply(image)
            t = remover.last_timings
            print(row(label, t, rss_mb()))
        print(f"modelo={t.model} providers={t.providers}\n")
        manager.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--sizes", default=DEFAULT_SIZES)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    print(f"Python {platform.python_version()} · {platform.platform()} · CPUs: {os.cpu_count()}\n")
    sizes = parse_sizes(args.sizes)
    run_real(sizes, args.runs) if args.real else run_overhead(sizes)


if __name__ == "__main__":
    main()
