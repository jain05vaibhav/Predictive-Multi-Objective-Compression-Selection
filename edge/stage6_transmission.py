"""
Stage 6 Transmission Adapter (Backwards Compatibility Module)

Re-exports RadioTransmissionStage from edge.stage7_radio as TransmissionStage
to maintain 100% compatibility with existing test suites and imports.
"""

from edge.stage7_radio import (
    RadioTransmissionStage,
    TransmissionStage
)

__all__ = ["TransmissionStage", "RadioTransmissionStage"]
