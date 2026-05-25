"""AutoPaper2 — Spiral core package.

Provides:
    - PipelineState: project state management
    - SurveyMemory: M1 domain survey persistent memory
    - ProjectManager: project creation and lifecycle
    - Conductor: stage orchestration and Gate review
"""

from .state import PipelineState
from .survey_memory import SurveyMemory, SurveyMemoryManager
from .project import ProjectManager, MODULE_STAGES, GATE_STAGES, AGENT_FOR_STAGE
from .conductor import Conductor

__all__ = [
    "PipelineState",
    "SurveyMemory",
    "SurveyMemoryManager",
    "ProjectManager",
    "MODULE_STAGES",
    "GATE_STAGES",
    "AGENT_FOR_STAGE",
    "Conductor",
]
