"""config/__init__.py

Responsabilidad:
    - Exponer Settings y get_settings del paquete de configuración.
"""
from config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
