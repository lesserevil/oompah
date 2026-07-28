---
id: OOMPAH-529
type: task
status: In Progress
priority: 2
title: Persist revision-aware duplicate-screening evidence
parent: OOMPAH-528
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T21:18:31.077035Z'
updated_at: '2026-07-28T21:20:42.982531Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Add a small duplicate-screening domain module and tracker-backed persistence for screening state. This is the foundation for preflight scheduling; do not add scheduler dispatch in this task.

Implementation scope:
- Add a typed record for duplicate-screening evidence with states/results sufficient to represent checked, running claim data, verdict, checked timestamp, detector identity/version, task fingerprint, and matched task identifiers/evidence.
- Define a stable fingerprint from the task fields that materially affect duplicate analysis: normalized title, description/body, project, parent relationship, dependencies, and user-authored labels relevant to scope. Exclude Oompah-owned transient labels and comments so writing the result does not invalidate itself.
- Store the record in tracker metadata under a namespaced Oompah key using get_metadata/set_metadata_field, following patterns in intake_schema.py and terminal audit metadata.
- Provide helpers that classify a task as unchecked, running, checked, or stale. A fingerprint or detector-version mismatch must classify as stale without deleting historical evidence.
- Read the legacy focus-complete:duplicate_detector label only as migration input. It must not be treated as a current model-backed pass when a reliable fingerprint cannot be reconstructed; expose it as stale/legacy so the task is eligible for a fresh check.
- Keep the storage format JSON-compatible and tolerant of absent, partial, or future-version metadata.

Relevant context/files:
- oompah/tracker.py and tracker implementations expose metadata APIs.
- oompah/intake_schema.py demonstrates typed, tolerant metadata parsing.
- oompah/orchestrator.py currently skips focus-complete:duplicate_detector in _apply_duplicate_detection.
- tests/test_orchestrator_duplicate_detection.py contains legacy behavior coverage.

Required tests:
- Unit tests for canonical fingerprint stability and changes for every included field.
- Unit tests proving transient Oompah labels/comments do not change the fingerprint.
- Round-trip, missing-field, malformed-record, unknown-version, detector-version mismatch, and legacy-label tests.
- Tracker contract coverage demonstrating metadata works with the native Markdown tracker and does not overwrite unrelated metadata.

Acceptance criteria:
1. Callers can persist and retrieve a typed duplicate-screening record through the generic Tracker API.
2. Callers can determine unchecked/running/checked/stale from an Issue and detector version.
3. Material task edits make a prior pass stale; metadata-only writes do not.
4. Malformed/old records fail safe as unchecked or stale and never make a task implementation-eligible.
5. Focused tests pass through the appropriate Makefile test target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:20
---
Claimed by the current interactive Codex session. Implementation will begin on epic branch epic-OOMPAH-528; do not dispatch another agent for this task.
---
<!-- COMMENTS:END -->
