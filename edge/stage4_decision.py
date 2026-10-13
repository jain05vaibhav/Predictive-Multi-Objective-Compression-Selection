"""
Stage 4 Decision Adapter (Backwards Compatibility Module)

Re-exports HierarchicalDecisionEngine from edge.stage5_decision to preserve
full compatibility with existing test suites and previous imports while adhering
to the PDF system architecture (Stage 4: Profiler, Stage 5: Decision Engine).
"""

from edge.stage5_decision import (
    HierarchicalDecisionEngine,
    DecisionStage
)

__all__ = ["DecisionStage", "HierarchicalDecisionEngine"]
