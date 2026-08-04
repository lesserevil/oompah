---
id: OOMPAH-529
type: task
status: Archived
priority: 2
title: Persist revision-aware duplicate-screening evidence
parent: OOMPAH-528
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T21:18:31.077035Z'
updated_at: '2026-08-04T23:50:38.879076Z'
work_branch: epic-OOMPAH-528
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 6bbf97b4-c6ae-45c6-b1bb-612bb6e8ddc0
oompah.work_branch: epic-OOMPAH-528
oompah.task_costs:
  total_input_tokens: 774029
  total_output_tokens: 4312
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 774029
      output_tokens: 4312
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 773703
    output_tokens: 4250
    cost_usd: 0.0
    recorded_at: '2026-07-28T21:23:55.393926+00:00'
  - profile: default
    model: haiku
    input_tokens: 326
    output_tokens: 62
    cost_usd: 0.0
    recorded_at: '2026-07-28T21:27:05.257409+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-f1fdfa299a68: '2026-08-04T23:50:21.512384+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-529
    target_state: Archived
    evidence_fingerprint: 5beedfad6608e3b6febbb00b1a2ebcee9ecc13a6f5f1e3a8cc46241301b36fe5
    audit_ids:
    - audit-8e2ed2ecb98f
    kind: result
    applied: true
    retired_at: '2026-08-04T23:50:21.512392+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-529
    audit_id: audit-8e2ed2ecb98f
    attempt_id: attempt-f1fdfa299a68
    target_state: Archived
    evidence_fingerprint: 5beedfad6608e3b6febbb00b1a2ebcee9ecc13a6f5f1e3a8cc46241301b36fe5
    status: Archived
    audit_ids:
    - audit-8e2ed2ecb98f
    applied: true
    created_at: '2026-08-04T23:50:21.512403+00:00'
    applied_at: '2026-08-04T23:50:35.629550+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-8e2ed2ecb98f
    project_id: proj-14849f1b
    task_id: OOMPAH-529
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5beedfad6608e3b6febbb00b1a2ebcee9ecc13a6f5f1e3a8cc46241301b36fe5
    attempts:
    - version: 1
      attempt_id: attempt-f1fdfa299a68
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5beedfad6608e3b6febbb00b1a2ebcee9ecc13a6f5f1e3a8cc46241301b36fe5
      created_at: '2026-08-04T23:45:32.783755+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T23:45:32.783755+00:00'
      branch_key: epic-OOMPAH-528
      verdict: pass
      completed_at: '2026-08-04T23:50:21.512271+00:00'
      ended_at: '2026-08-04T23:50:21.512271+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T22:36:22.144955+00:00'
    updated_at: '2026-08-04T23:50:21.512271+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-f1fdfa299a68
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5beedfad6608e3b6febbb00b1a2ebcee9ecc13a6f5f1e3a8cc46241301b36fe5
    created_at: '2026-08-04T23:45:32.783755+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T23:45:32.783755+00:00'
    branch_key: epic-OOMPAH-528
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
author: oompah
created: 2026-07-28 21:24
---
**Discovery**: Found the key architecture patterns:

1. **Metadata Pattern** (intake_schema.py, terminal_audit_metadata.py):
   - Typed dataclass with from_raw/to_raw for tolerant parsing
   - Persisted via tracker.set_metadata_field/get_metadata with versioning
   - Preserves unknown fields for forward compatibility
   
2. **Current Duplicate Detection** (orchestrator.py:14295):
   - Skips candidates with 'focus-complete:duplicate_detector' label
   - Uses find_similar_issues() to detect matches
   - Moves matches to 'Duplicate Candidate' status
   
3. **Legacy Label** (test_orchestrator_duplicate_detection.py):
   - Tests show focus-complete:duplicate_detector means 'already checked'
   - Must migrate to new metadata-backed model

**Implementation Plan**:
- Create oompah/duplicate_screening.py with DuplicateScreeningEvidence dataclass
- Implement canonical fingerprint from task fields (title, description, project, parent, dependencies, user labels)
- Implement state helpers: is_unchecked(), is_running(), is_checked(), is_stale()
- Add metadata persistence via DuplicateScreeningMetadataStore
- Handle legacy label as migration input (expose as stale)
- Write comprehensive tests for fingerprint stability, metadata round-trip, tracker contract
---
author: oompah
created: 2026-07-28 21:26
---
Implemented revision-aware duplicate-screening metadata in commit 1a3a882c5 on epic-OOMPAH-528. Added typed tolerant parsing, stable material-input fingerprints, legacy/malformed fail-closed behavior, all tracker adapter hydration, and native tracker round-trip coverage. Focused result: 7 passed.
---
author: oompah
created: 2026-07-28 21:27
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 16
- Tokens: 326 in / 62 out [388 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 58s
- Log: OOMPAH-529__20260728T212409Z.jsonl
---
author: oompah
created: 2026-07-28 21:27
---
Implemented and pushed as 1a3a882c5 on epic-OOMPAH-528; focused duplicate-screening tests pass.
---
author: oompah
created: 2026-07-28 22:03
---
The parent epic OOMPAH-528 merged from epic-OOMPAH-528, but this task was Done with work branch epic-OOMPAH-528. Its work is not proven to be in the merged epic. Git evidence: OOMPAH-529 branch epic-OOMPAH-528 has 1 unlanded commit(s), including 92aa5e5c2410. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-28 22:05
---
The parent epic OOMPAH-528 merged from epic-OOMPAH-528, but this task was Needs Human with work branch epic-OOMPAH-528. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-28 22:13
---
Resolved: this was a false unlanded-work alert from the stale managed epic worktree. PR #568 merged verified head c4c7f5dfa into main as 70771b4e9. The flagged 92aa5e5c2 commit was a separate incomplete scheduler attempt that explicitly left dispatch integration pending; it was intentionally rejected before review and is not required task work. The stale local worktree/branch has now been removed, while origin/epic-OOMPAH-528 and all completed implementation remain preserved in main. Final branch validation was 13,070 passed, 7 skipped. No human recovery action is required.
---
author: oompah
created: 2026-07-28 22:13
---
Verified the completed revision-aware screening implementation landed in PR #568; removed stale divergent worktree evidence.
---
author: oompah
created: 2026-08-04 22:36
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 23:45
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 23:45
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 23:50
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- impl_commit: 99a432cfd on main via PR #568 (merge 70771b4e9)
- module_path: oompah/duplicate_screening.py
- test_path: tests/test_duplicate_screening.py
- focused_test_result: 9 passed in 0.22s
- downstream_dependents_merged: OOMPAH-539, OOMPAH-541, OOMPAH-658, OOMPAH-682, OOMPAH-721, OOMPAH-728
- previous_unlanded_alert: resolved false-positive per 2026-07-28 22:13 comment
- previous_state: Merged
- requested_target: Archived
- trigger_reason: Aged Merged auto-archive (closed 7 days ago)
---
<!-- COMMENTS:END -->
