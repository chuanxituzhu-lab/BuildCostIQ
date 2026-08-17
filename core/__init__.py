"""Core domain API; P01-P08 capability registration remains frozen."""

from .event_kernel import (
    ALLOWED_TRANSITIONS,
    DIMENSIONS,
    EVENT_SOURCE_TYPES,
    EVENT_STATUSES,
    EVENT_TYPES,
    SEVERITIES,
    EventKernelError,
    build_state_vector,
    distill_local_data,
    distill_text,
    evaluate_event_rules,
    fuse_distillations,
    new_event,
    run_cross_check,
    transition_event,
    validate_event,
)
from .gateway import CapabilityGateway
from .models import Evidence, Project, SourceDocument
from .provenance import sha256_bytes
from .runtime import Runtime

__all__ = [
    "ALLOWED_TRANSITIONS", "CapabilityGateway", "DIMENSIONS", "EVENT_SOURCE_TYPES", "EVENT_STATUSES",
    "EVENT_TYPES", "SEVERITIES", "EventKernelError", "Evidence", "Project", "Runtime", "SourceDocument",
    "build_state_vector", "distill_local_data", "distill_text", "evaluate_event_rules", "fuse_distillations",
    "new_event", "run_cross_check", "sha256_bytes", "transition_event", "validate_event",
]

