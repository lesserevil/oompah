---
id: OOMPAH-463
type: feature
status: Archived
priority: 1
title: Persist terminal-audit state through the tracker metadata contract
parent: OOMPAH-457
children: []
blocked_by:
- OOMPAH-462
- OOMPAH-452
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:05:05.235115Z'
updated_at: '2026-08-04T23:11:04.876020Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 6b481f50-63b9-4f13-b105-3bb0e917194f
oompah.work_branch: epic-OOMPAH-457
oompah.task_costs:
  total_input_tokens: 884039
  total_output_tokens: 5338
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 884025
      output_tokens: 5192
      cost_usd: 0.0
    unknown:
      input_tokens: 14
      output_tokens: 146
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 884025
    output_tokens: 5192
    cost_usd: 0.0
    recorded_at: '2026-07-28T18:41:59.044747+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 14
    output_tokens: 146
    cost_usd: 0.0
    recorded_at: '2026-08-04T22:44:42.801892+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-610def39f9af: '2026-08-04T23:10:58.925433+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-463
    target_state: Archived
    evidence_fingerprint: ff00e333901ab04a54eebd37cb848bdd4f2409383af296b196505ef67969f8d4
    audit_ids:
    - audit-cabe006dc997
    kind: result
    applied: true
    retired_at: '2026-08-04T23:10:58.925445+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-463
    audit_id: audit-cabe006dc997
    attempt_id: attempt-610def39f9af
    target_state: Archived
    evidence_fingerprint: ff00e333901ab04a54eebd37cb848bdd4f2409383af296b196505ef67969f8d4
    status: Archived
    audit_ids:
    - audit-cabe006dc997
    applied: false
    created_at: '2026-08-04T23:10:58.925462+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-cabe006dc997
    project_id: proj-14849f1b
    task_id: OOMPAH-463
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ff00e333901ab04a54eebd37cb848bdd4f2409383af296b196505ef67969f8d4
    attempts:
    - version: 1
      attempt_id: attempt-b62af15411ff
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: ff00e333901ab04a54eebd37cb848bdd4f2409383af296b196505ef67969f8d4
      created_at: '2026-08-04T21:40:33.327400+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:40:33.327400+00:00'
      branch_key: epic-OOMPAH-457
      ended_at: '2026-08-04T21:47:43.270276+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-af2ad6e01581
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: ff00e333901ab04a54eebd37cb848bdd4f2409383af296b196505ef67969f8d4
      created_at: '2026-08-04T22:42:27.086185+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T22:42:27.086185+00:00'
      branch_key: epic-OOMPAH-457
      candidate_rotation_count: 1
      ended_at: '2026-08-04T22:55:06.040502+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-610def39f9af
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: ff00e333901ab04a54eebd37cb848bdd4f2409383af296b196505ef67969f8d4
      created_at: '2026-08-04T22:55:21.475506+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-04T22:55:21.475506+00:00'
      branch_key: epic-OOMPAH-457
      candidate_rotation_count: 2
      verdict: pass
      completed_at: '2026-08-04T23:10:58.925218+00:00'
      ended_at: '2026-08-04T23:10:58.925218+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T21:33:33.972125+00:00'
    updated_at: '2026-08-04T23:10:58.925218+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-b62af15411ff
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ff00e333901ab04a54eebd37cb848bdd4f2409383af296b196505ef67969f8d4
    created_at: '2026-08-04T21:40:33.327400+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:40:33.327400+00:00'
    branch_key: epic-OOMPAH-457
    ended_at: '2026-08-04T21:47:43.270276+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-af2ad6e01581
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ff00e333901ab04a54eebd37cb848bdd4f2409383af296b196505ef67969f8d4
    created_at: '2026-08-04T22:42:27.086185+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T22:42:27.086185+00:00'
    branch_key: epic-OOMPAH-457
    candidate_rotation_count: 1
    ended_at: '2026-08-04T22:55:06.040502+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-610def39f9af
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ff00e333901ab04a54eebd37cb848bdd4f2409383af296b196505ef67969f8d4
    created_at: '2026-08-04T22:55:21.475506+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-04T22:55:21.475506+00:00'
    branch_key: epic-OOMPAH-457
    candidate_rotation_count: 2
---
## Summary

Implementation scope

Add tracker-neutral helpers that read and write a single namespaced oompah.terminal_audit metadata document containing the pending chain and bounded audit-attempt history. Use TrackerProtocol.get_metadata/set_metadata_field and the per-project write lock; do not parse human comments as authority. Implement no-op detection so polling does not create metadata-only commits when the document is unchanged. Cover native Markdown, GitHub body metadata, and GitLab metadata once the GitLab adapter is available. Preserve unknown future fields during updates.

Tests

Add contract tests for empty metadata, round trips, append/update, no-op writes, unknown-field preservation, concurrent serialized updates, malformed-document quarantine, and secret redaction for each tracker adapter. Run focused tests and make test.

Acceptance criteria

Audit state survives process restart and tracker rereads, concurrent writers cannot silently drop attempts, unchanged writes are true no-ops, and no secret or full model response reaches tracker metadata.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:39
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:39
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 18:40
---
Understanding: I will screen existing oompah tasks and project documentation for terminal-audit/tracker-metadata work, then read each plausible candidate's full description and comments. If no duplicate is confirmed, I will record the closest reviewed tasks and evidence, add the duplicate-detector completion label, and hand off for implementation without changing code.
---
author: oompah
created: 2026-07-28 18:41
---
Discovery: Duplicate screening found no confirmed duplicate. Exact searches across .oompah/tasks, docs, plans, README.md, and WORKFLOW.md found no prior terminal_audit, pending-chain, audit-attempt, or metadata-contract task. Full task views reviewed: OOMPAH-462 (Done) defines tracker-neutral audit records/fingerprints only; OOMPAH-452 (Merged) restores GitLab adapter metadata support only; OOMPAH-464 covers service_state.json grandfather baselines/recovery; OOMPAH-465 covers transition staging/chains. These are dependencies/consumers with distinct acceptance criteria, not duplicates. Existing source primitives are TrackerProtocol.get_metadata/set_metadata_field in oompah/tracker.py, the per-project lock in oompah/projects.py, and the completed terminal_audit domain in oompah/terminal_audit.py; no terminal-audit persistence helper exists.
---
author: oompah
created: 2026-07-28 18:41
---
Focus handoff: duplicate_detector\n\nOutcome: No duplicate confirmed; OOMPAH-463 remains a distinct implementation task.\n\nEvidence and decisions: Searched with rg for terminal-audit, terminal_audit, audit-attempt, pending chain, tracker metadata, metadata contract, malformed-document, secret redaction, terminal, and audit across .oompah/tasks, docs, plans, README.md, and WORKFLOW.md. Read full task descriptions/comments for OOMPAH-462, OOMPAH-452, OOMPAH-464, OOMPAH-465, plus closest historical candidates OOMPAH-28, OOMPAH-29, OOMPAH-173, OOMPAH-194, OOMPAH-219, OOMPAH-253, and OOMPAH-257. OOMPAH-462 supplies domain types; OOMPAH-452 supplies the GitLab adapter; OOMPAH-464 owns service-state upgrade/recovery; OOMPAH-465 owns transition orchestration. None covers the requested tracker-neutral oompah.terminal_audit document, unknown-field-preserving updates, no-op detection, per-project lock serialization, malformed quarantine, or adapter contract/redaction tests. Relevant current primitives/files: oompah/terminal_audit.py, oompah/tracker.py (TrackerProtocol metadata methods), oompah/projects.py (project_write_lock), and existing adapter tests.\n\nRemaining work/risks: implement and test the metadata helper across native Markdown, GitHub body metadata, and the now-available GitLab adapter; ensure concurrent read-modify-write operations cannot lose attempts, unchanged writes make no tracker mutation, malformed metadata is quarantined safely, and secrets/model prose never enter tracker metadata.\n\nRecommended next focus: feature (backend implementation), with OOMPAH-452 and OOMPAH-462 treated as completed prerequisites.
---
author: oompah
created: 2026-07-28 18:41
---
Agent completed successfully in 124s (889217 tokens)
---
author: oompah
created: 2026-07-28 18:42
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 30
- Tokens: 884.0K in / 5.2K out [889.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 4s
- Log: OOMPAH-463__20260728T184000Z.jsonl
---
author: oompah
created: 2026-07-28 18:42
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 18:42
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 18:42
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 18:42
---
Understanding: I will add a tracker-neutral terminal-audit metadata helper backed by oompah.terminal_audit, use the project write lock for serialized read-modify-write operations, preserve unknown fields, quarantine malformed data, redact persisted values, and cover native/GitHub/GitLab behavior with focused tests before committing and closing the task.
---
author: oompah
created: 2026-07-28 18:50
---
Implementation: Added oompah/terminal_audit_metadata.py. TerminalAuditMetadataStore persists one versioned oompah.terminal_audit envelope with pending_chain and bounded attempt_history, updates it under ProjectStore.project_write_lock, skips unchanged writes, preserves forward-compatible fields (including nested record fields), and quarantines malformed payloads using only a SHA-256 marker. It never reads comments and redacts credentials/model-response-like data before persistence. Added adapter contract tests for native Markdown, GitHub body, and GitLab metadata.
---
author: oompah
created: 2026-07-28 18:53
---
Verification: New metadata contract suite passes (19 tests), including native Markdown, GitHub, and GitLab round trips/no-op writes/unknown-field retention/quarantine/redaction; adjacent terminal-audit and tracker suites pass (633 tests). make test was attempted but cannot initialize uv in this sandbox due DBus transient-scope failure; the equivalent final parallel pytest gate passed (12,685 tests, 7 skipped). make check-secrets passed (with an existing null-byte shell warning).
---
author: oompah
created: 2026-07-28 18:53
---
Completion: Delivered and pushed 1116ff8c6. Terminal-audit state now survives tracker rereads through a single namespaced metadata envelope; serialized updates retain concurrent attempts, unchanged polls do not mutate trackers, malformed payloads fail closed with secret-free quarantine markers, and persisted fields are redacted. Tests and final equivalent full gate passed; branch is clean and up to date with origin.
---
author: oompah
created: 2026-07-28 18:53
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 0, Tool calls: 44
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 11m 43s
- Log: OOMPAH-463__20260728T184219Z.jsonl
---
author: oompah
created: 2026-07-28 18:53
---
Persisted tracker-neutral terminal-audit metadata with locking, no-op writes, quarantine/redaction, and adapter contract tests.
---
author: oompah
created: 2026-08-04 21:33
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 22:42
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 22:42
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 22:44
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 6, Tool calls: 4
- Tokens: 14 in / 146 out [160 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 11s
- Log: OOMPAH-463__20260804T224258Z.jsonl
---
author: oompah
created: 2026-08-04 22:55
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-04 22:55
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
