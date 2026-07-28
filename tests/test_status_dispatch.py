"""Regression tests for lifecycle statuses at the worker dispatch boundary."""

from oompah.orchestrator import _dispatch_active_state_names
from oompah.statuses import IN_PROGRESS, IN_VALIDATION, OPEN


def test_in_validation_is_excluded_from_configured_dispatch_states():
    assert _dispatch_active_state_names(
        [OPEN, IN_VALIDATION, IN_PROGRESS]
    ) == [OPEN, IN_PROGRESS]
