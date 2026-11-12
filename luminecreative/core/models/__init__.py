"""core/models/__init__.py

Responsabilidad:
    - Exponer los modelos de estado: AppliedOperation, ImageSnapshot,
      ProcessingState, ProcessingStatus.
"""
from core.models.processing_state import (
    AppliedOperation,
    ImageSnapshot,
    PreviewResult,
    ProcessingState,
    ProcessingStatus,
)

__all__ = ["AppliedOperation", "ImageSnapshot", "PreviewResult", "ProcessingState", "ProcessingStatus"]
