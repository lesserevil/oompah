---
id: OOMPAH-464
type: feature
status: Archived
priority: 1
title: Persist the upgrade grandfather baseline and recover pending audits
parent: OOMPAH-457
children: []
blocked_by:
- OOMPAH-462
- OOMPAH-463
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:05:06.169316Z'
updated_at: '2026-08-04T23:20:21.861160Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 09e5e016-981c-4cb4-8627-4ae28e83a360
oompah.work_branch: epic-OOMPAH-457
oompah.task_costs:
  total_input_tokens: 298
  total_output_tokens: 7564
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 298
      output_tokens: 7564
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 298
    output_tokens: 7564
    cost_usd: 0.0
    recorded_at: '2026-07-28T18:57:15.087815+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-dff3c7581e07: '2026-08-04T23:20:08.483760+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-464
    target_state: Archived
    evidence_fingerprint: 45ebe8b84d7a75b3b6bf4c866519c50b75e9e293221cd667d23d1697e016a015
    audit_ids:
    - audit-bbdd18e64e5c
    kind: result
    applied: true
    retired_at: '2026-08-04T23:20:08.483772+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-464
    audit_id: audit-bbdd18e64e5c
    attempt_id: attempt-dff3c7581e07
    target_state: Archived
    evidence_fingerprint: 45ebe8b84d7a75b3b6bf4c866519c50b75e9e293221cd667d23d1697e016a015
    status: Archived
    audit_ids:
    - audit-bbdd18e64e5c
    applied: true
    created_at: '2026-08-04T23:20:08.483788+00:00'
    applied_at: '2026-08-04T23:20:20.134790+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-bbdd18e64e5c
    project_id: proj-14849f1b
    task_id: OOMPAH-464
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 45ebe8b84d7a75b3b6bf4c866519c50b75e9e293221cd667d23d1697e016a015
    attempts:
    - version: 1
      attempt_id: attempt-605e78be8661
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 45ebe8b84d7a75b3b6bf4c866519c50b75e9e293221cd667d23d1697e016a015
      created_at: '2026-08-04T21:40:39.009749+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:40:39.009749+00:00'
      branch_key: epic-OOMPAH-457
      ended_at: '2026-08-04T21:47:48.369010+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-dff3c7581e07
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 45ebe8b84d7a75b3b6bf4c866519c50b75e9e293221cd667d23d1697e016a015
      created_at: '2026-08-04T23:12:28.740679+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T23:12:28.740679+00:00'
      branch_key: epic-OOMPAH-457
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-08-04T23:20:08.483627+00:00'
      ended_at: '2026-08-04T23:20:08.483627+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T21:33:43.966727+00:00'
    updated_at: '2026-08-04T23:20:08.483627+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-605e78be8661
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 45ebe8b84d7a75b3b6bf4c866519c50b75e9e293221cd667d23d1697e016a015
    created_at: '2026-08-04T21:40:39.009749+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:40:39.009749+00:00'
    branch_key: epic-OOMPAH-457
    ended_at: '2026-08-04T21:47:48.369010+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-dff3c7581e07
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 45ebe8b84d7a75b3b6bf4c866519c50b75e9e293221cd667d23d1697e016a015
    created_at: '2026-08-04T23:12:28.740679+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T23:12:28.740679+00:00'
    branch_key: epic-OOMPAH-457
    candidate_rotation_count: 1
---
## Summary

Implementation scope

Extend service_state.json with a versioned terminal-audit enforcement record. On the first upgraded startup, snapshot each existing terminal task as a grandfather tuple of project, task, terminal state, and current evidence fingerprint. Reuse that baseline across restart. A task that leaves and later re-enters terminal state, or whose evidence fingerprint changes, is no longer grandfathered. Also scan In Validation metadata on startup and rebuild pending audit queue entries without duplicating attempts. Keep legacy/corrupt entries fail-closed and observable.

Tests

Use temporary service-state and fake trackers to cover first startup, second startup, unchanged grandfathered records, changed evidence, terminal-to-nonterminal-to-terminal, pending queue recovery, duplicate suppression, corrupt state, and multiple projects with overlapping task IDs. Run focused tests and make test.

Acceptance criteria

Deployment does not retroactively audit existing terminal records, restart does not forget enforcement or pending work, and any post-upgrade terminal/evidence change requires a fresh audit.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:55
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 18:56
---
Understanding: Investigating OOMPAH-464 as Duplicate Investigator. The task requires extending service_state.json with a versioned terminal-audit enforcement record, snapshotting existing terminal tasks on first upgrade, and recovering pending audit queue entries on restart. Before implementing, I am searching for existing tasks that cover the same ground: grandfather baselining, terminal state audit enforcement, upgrade persistence, or audit queue recovery.
---
author: oompah
created: 2026-07-28 18:56
---
Discovery: Completed duplicate screening. Searched 280+ archived/merged/backlog tasks, git log history, code files, and design plans. No existing task addresses grandfather baseline snapshotting, upgrade persistence to service_state.json, or pending audit queue recovery. OOMPAH-462 and OOMPAH-463 (the two blocking dependencies) are already committed in epic-OOMPAH-457; they provide terminal-audit domain records and metadata persistence. OOMPAH-464 is a new, non-duplicate task that builds on them.
---
author: oompah
created: 2026-07-28 18:57
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-464 is a unique task, not a re-detection of existing work.

**Evidence searched:**
- All .oompah/tasks/ states (open, in-progress, merged, archived, backlog) — 280+ tasks scanned
- Git history: git log --all --oneline | grep patterns for 'grandfather', 'baseline', 'pending audit', 'recovery', 'upgrade' — zero matches
- Code files: rg 'grandfather|baseline.*snapshot|first.*startup.*snapshot|recovery.*pending' in oompah/ and tests/
- Design documents: plans/ directory for related architecture or TODOs — no matches
- Recent commits: OOMPAH-462 (terminal-audit domain records) and OOMPAH-463 (metadata persistence) are already implemented on this branch as dependencies

**Blocking dependencies (both complete):**
- OOMPAH-462: terminal_audit.py — domain records for TargetState, RequestState, audit attempts, evidence fingerprints
- OOMPAH-463: terminal_audit_metadata.py — tracker metadata persistence (oompah.terminal_audit key)

**Remaining work for OOMPAH-464:**
1. Extend service_state.json schema with versioned terminal-audit enforcement record
2. On first upgraded startup: enumerate existing terminal tasks, snapshot as grandfather tuples (project, task, terminal state, evidence fingerprint)
3. Persist grandfather baseline to service_state.json, reuse on restart
4. Logic: task leaving terminal state, re-entering terminal state, or evidence fingerprint changing → no longer grandfathered
5. Scan tracker metadata for 'In Validation' status and rebuild pending audit queue without duplicating attempts
6. Handle corrupt/legacy entries fail-closed with observable errors
7. Tests: first/second startup, unchanged records, changed evidence, terminal↔non-terminal↔terminal transitions, queue recovery, duplicate suppression, corrupt state, multi-project overlapping IDs
8. Acceptance: no retroactive audit of existing terminal records, restart preserves enforcement and pending work, post-upgrade state/evidence changes require fresh audit

**Relevant files to modify:**
- oompah/orchestrator.py — add startup handler for grandfather snapshotting, pending queue recovery
- oompah/service_state.py (if it exists) or service_state.json management — add schema + serialization
- oompah/terminal_audit_metadata.py — extend to scan 'In Validation' metadata on startup
- tests/test_terminal_audit_*.py — comprehensive coverage per acceptance criteria

**Risks/Gotchas:**
- Ensure backward compatibility: old service_state.json without grandfa ther record must be safely initialized
- Evidence fingerprint stability: changes in fingerprint algorithm must not invalidate existing grandfathered tuples
- Concurrent startup: if orchestrator starts in multiple places, ensure idempotent grandfather initialization
- Metadata scanning: 'In Validation' field name must match actual tracker metadata schema

**Recommended next focus:** feature (full implementation of grandfather baseline and pending audit recovery)
---
author: oompah
created: 2026-07-28 18:57
---
Agent completed successfully in 139s (7862 tokens)
---
author: oompah
created: 2026-07-28 18:57
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 86, Tool calls: 42
- Tokens: 298 in / 7.6K out [7.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 19s
- Log: OOMPAH-464__20260728T185502Z.jsonl
---
author: oompah
created: 2026-07-28 18:57
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 18:57
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:57
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-28 18:57
---
Understanding: I will extend durable service state with a versioned terminal-audit grandfather baseline, initialize it idempotently on first upgraded startup, invalidate records on terminal/evidence changes, and recover In Validation audits without duplicate attempts. I will first inspect the existing orchestrator, state, metadata, and test seams, then implement focused coverage and verify with Makefile targets.
---
author: oompah
created: 2026-07-28 18:58
---
Discovery: OOMPAH-462/463 supply only terminal-audit records and tracker metadata persistence; no enforcement coordinator exists. The single startup path is Orchestrator.run() before its initial _tick(), and project-scoped tracker resolution is available. I will add a dedicated coordinator with versioned service-state serialization, stable project+task keys, conservative evidence extraction, and metadata-based pending recovery.
---
author: oompah
created: 2026-07-28 19:06
---
Implementation: added oompah/terminal_audit_enforcement.py with durable grandfather tuples, versioned state serialization, deterministic duplicate-safe pending queue entries, metadata recovery for In Validation, and fail-closed/quarantined handling for malformed service state or task metadata. Orchestrator startup invokes it before the initial tick and periodically reconciles on the full-sync cadence; diagnostics are exposed in maintenance status and alerts.
---
author: oompah
created: 2026-07-28 19:11
---
Verification: focused terminal-audit/domain/metadata and orchestrator startup/restart/event-loop tests pass (82 tests). Added coverage for first/second startup, unchanged baselines, evidence changes, terminal transitions, metadata recovery and duplicate attempt suppression, corrupt/legacy state, overlapping project IDs, quarantine observability, audit completion, and startup wiring. Ruff and git diff checks are clean.
---
author: oompah
created: 2026-07-28 19:16
---
Completion: delivered and pushed commit 1f77c82a0 on epic-OOMPAH-457. Terminal-audit enforcement now persists a versioned grandfather baseline, invalidates it on state/evidence changes, recovers In Validation pending work with attempt deduplication, handles corrupt state/metadata fail-closed with logs/alerts, and scopes overlapping task IDs by project. Focused tests pass; full isolated suite passes 12,689 tests with 7 skips. The make test wrapper could not initialize uv in this environment due DBus transient-scope setup, while the equivalent isolated pytest gate passed. Branch is clean and up to date with origin.
---
author: oompah
created: 2026-07-28 19:16
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 81
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 19m 11s
- Log: OOMPAH-464__20260728T185727Z.jsonl
---
author: oompah
created: 2026-07-28 19:16
---
Persisted terminal-audit grandfather baseline and recovered pending audits with duplicate-safe, fail-closed enforcement
---
author: oompah
created: 2026-08-04 21:33
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 23:12
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 23:12
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 23:20
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- commit: 1f77c82a0
- on_main: true
- enforcement_tests_passed: 51
- neighbouring_tests_passed: 102
- implementation_file_size_chars: 104215
- test_file_size_chars: 69427
---
<!-- COMMENTS:END -->
