---
id: OOMPAH-529
type: task
status: In Progress
priority: 2
title: Persist revision-aware duplicate-screening evidence
parent: OOMPAH-528
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T21:18:31.077035Z'
updated_at: '2026-07-28T21:24:20.001176Z'
work_branch: epic-OOMPAH-528
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 6bbf97b4-c6ae-45c6-b1bb-612bb6e8ddc0
oompah.work_branch: epic-OOMPAH-528
oompah.task_costs:
  total_input_tokens: 773703
  total_output_tokens: 4250
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 773703
      output_tokens: 4250
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 773703
    output_tokens: 4250
    cost_usd: 0.0
    recorded_at: '2026-07-28T21:23:55.393926+00:00'
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
author: oompah
created: 2026-07-28 21:22
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 21:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 21:22
---
Understanding: I will first screen related oompah tasks for a confirmed duplicate, reading candidate descriptions and comments. If no duplicate covers the same revision-aware persistence foundation, I will record the evidence and hand off for implementation as required by the Duplicate Investigator focus.
---
author: oompah
created: 2026-07-28 21:23
---
Discovery: No confirmed duplicate found. Full records reviewed: OOMPAH-528 (parent epic) and siblings OOMPAH-530 through OOMPAH-534; OOMPAH-217 (duplicate-focus handoff workflow), OOMPAH-156 (error_watcher fingerprint deduplication), and OOMPAH-160 (corrupt native-task/intake protection). These cover orchestration workflow, event-task deduplication, and file/intake recovery respectively; none provides revision-aware duplicate-screening evidence, task-field fingerprinting, or generic Tracker metadata persistence.
---
author: oompah
created: 2026-07-28 21:23
---
Focus handoff: duplicate_detector\n\n1. Outcome: No duplicate confirmed; OOMPAH-529 is a distinct implementation child of OOMPAH-528.\n2. Evidence/decisions: Searched .oompah/tasks, docs, and plans for duplicate-screening, detector, fingerprint, and metadata matches. Read full task records for OOMPAH-528 through OOMPAH-534, OOMPAH-217, OOMPAH-156, and OOMPAH-160 with oompah task view. The parent and siblings split claims, scheduling, verdicts, API/UI, and end-to-end work; historical candidates address focus handoff, error-watcher deduplication, or corrupt-file intake protection. None covers typed revision-aware screening evidence persisted through Tracker metadata.\n3. Remaining work/risks: Implement the domain record, canonical fingerprint, tolerant namespaced metadata round trip, state classification, legacy-label migration handling, and native Markdown tracker contract tests required by the description. Preserve unrelated metadata and ensure malformed/unknown-version records never unlock implementation. Relevant files include oompah/tracker.py, oompah/oompah_md_tracker.py, oompah/intake_schema.py, terminal audit metadata, and tests/test_orchestrator_duplicate_detection.py.\n4. Recommended next focus: feature.
---
author: oompah
created: 2026-07-28 21:23
---
Agent completed successfully in 101s (777953 tokens)
---
author: oompah
created: 2026-07-28 21:23
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 21
- Tokens: 773.7K in / 4.2K out [778.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 41s
- Log: OOMPAH-529__20260728T212218Z.jsonl
---
author: oompah
created: 2026-07-28 21:23
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 21:24
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 21:24
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 21:24
---
**Understanding**: This is a Maintenance Engineer focus to implement duplicate-screening evidence persistence. The Duplicate Investigator confirmed no duplicate exists; now I need to build the foundation for preflight scheduling.

**Plan**:
1. Create a duplicate_screening domain module with typed evidence record
2. Implement canonical fingerprint from task fields (title, description, project, parent, dependencies, user labels)
3. Add tracker metadata storage/retrieval using get_metadata/set_metadata_field pattern
4. Implement state classification helpers (unchecked/running/checked/stale)
5. Handle legacy focus-complete:duplicate_detector label migration
6. Write comprehensive unit and tracker contract tests
7. Verify all acceptance criteria met

**Key insight from prior context**: Need to handle fingerprint/detector-version mismatch as stale (not delete historical evidence), exclude Oompah-owned transient labels/comments, and fail safe on malformed records.
---
<!-- COMMENTS:END -->
