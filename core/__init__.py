"""Core domain API; capability registration is controlled by the gateway."""

from .event_kernel import (
    ALLOWED_TRANSITIONS,
    DIMENSIONS,
    OUTCOME_ALLOWED_TRANSITIONS,
    OUTCOME_STATUSES,
    OUTCOME_TYPES,
    EVENT_SOURCE_TYPES,
    EVENT_STATUSES,
    EVENT_TYPES,
    SEVERITIES,
    EventKernelError,
    build_state_vector,
    build_outcome_vector,
    compute_value_leaks,
    distill_local_data,
    distill_text,
    evaluate_event_rules,
    evaluate_audit_gates,
    fuse_distillations,
    new_event,
    new_outcome_track,
    ensure_outcome_track,
    record_outcome_snapshot,
    run_cross_check,
    transition_event,
    transition_outcome,
    validate_event,
)
from .gateway import CapabilityGateway
from .models import Evidence, Project, SourceDocument
from .provenance import sha256_bytes
from .runtime import Runtime
from .version import APP_VERSION, current_version, normalize_version

__all__ = [
    "ALLOWED_TRANSITIONS", "APP_VERSION", "CapabilityGateway", "DIMENSIONS", "EVENT_SOURCE_TYPES", "EVENT_STATUSES",
    "EVENT_TYPES", "OUTCOME_ALLOWED_TRANSITIONS", "OUTCOME_STATUSES", "OUTCOME_TYPES", "SEVERITIES",
    "EventKernelError", "Evidence", "Project", "Runtime", "SourceDocument",
    "build_state_vector", "build_outcome_vector", "compute_value_leaks", "distill_local_data", "distill_text",
    "ensure_outcome_track", "evaluate_event_rules", "evaluate_audit_gates", "fuse_distillations", "new_event", "new_outcome_track",
    "record_outcome_snapshot", "run_cross_check", "sha256_bytes", "transition_event", "transition_outcome", "validate_event",
    "current_version", "normalize_version",
]

