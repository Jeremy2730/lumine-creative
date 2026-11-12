"""config/settings.py

Responsabilidad:
    - Reunir todos los valores configurables en un único lugar: rutas de
      E/S, DPI, nitidez, parámetros del modo semitono y opciones de GUI.
    - Resolver la carpeta de Descargas del sistema (default_downloads_dir)
      para que el resultado se guarde ahí y no en una carpeta del proyecto.

No conoce:
    - GUI, procesamiento de imágenes ni herramientas concretas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def default_downloads_dir() -> Path:
    """Carpeta de Descargas del sistema del usuario.

    Comprueba las variantes de nombre más comunes ("Downloads", "Descargas");
    si ninguna existe, crea "Downloads" en el home del usuario.
    """
    home = Path.home()
    for name in ("Downloads", "Descargas"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    fallback = home / "Downloads"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


@dataclass(frozen=True)
class Settings:
    """Configuración inmutable. Se inyecta; nadie la lee como global."""

    # Identidad
    app_title: str = "Herramienta para Diseño"
    author: str = "by Gerson Moncada"

    # Entrada / salida
    allowed_extensions: frozenset[str] = frozenset(
        {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
    )
    output_dir: Path = field(default_factory=default_downloads_dir)
    output_suffix: str = "_editada"
    jpg_quality: int = 95  # calidad JPG explícita (el valor por defecto de Pillow es 75)

    # Tamaño y resolución (herramienta aparte, ancho+alto+PPI independientes)
    resolution_default_ppi: int = 300
    resolution_dpi_fallback: int = 72  # solo para cálculos si la imagen no trae DPI
    resolution_max_recommended_px: int = 20_000  # advertencia, no bloquea

    # Nitidez (mismos valores del script original)
    sharpen_radius: float = 2
    sharpen_percent: int = 150
    sharpen_threshold: int = 3

    # Fondo semitono (mismos valores del script original)
    comic_black_threshold: int = 22
    comic_pattern_contrast: float = 3.0
    comic_blend_alpha: float = 0.18

    # Logging (esto es un registro técnico interno, no una descarga del usuario)
    log_dir: Path = BASE_DIR / "logs"

    # GUI
    window_size: str = "1000x760"
    appearance_mode: str = "dark"  # "dark" | "light" | "system"
    color_theme: str = "blue"


def get_settings() -> Settings:
    """Devuelve la configuración por defecto."""
    return Settings()
