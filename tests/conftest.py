"""Hace importable el proyecto al ejecutar ``pytest`` desde cualquier carpeta."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
