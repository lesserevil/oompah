---
id: OOMPAH-461
type: feature
status: Archived
priority: 1
title: Add the canonical In Validation lifecycle status
parent: OOMPAH-457
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:05:03.234325Z'
updated_at: '2026-08-04T22:09:01.554291Z'
work_branch: epic-OOMPAH-457
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9f091fa6-25ed-4357-8487-f68351e2a7ea
oompah.work_branch: epic-OOMPAH-457
oompah.task_costs:
  total_input_tokens: 354
  total_output_tokens: 8226
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 354
      output_tokens: 8226
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 354
    output_tokens: 8226
    cost_usd: 0.0
    recorded_at: '2026-07-28T18:09:00.904036+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-f217328aa10f: '2026-08-04T22:08:52.475390+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-461
    target_state: Archived
    evidence_fingerprint: 603fd80a9bad2eada8423644a7b3bd6255b543e038c29cb2024917936cb5085e
    audit_ids:
    - audit-4de729228280
    kind: result
    applied: true
    retired_at: '2026-08-04T22:08:52.475403+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-461
    audit_id: audit-4de729228280
    attempt_id: attempt-f217328aa10f
    target_state: Archived
    evidence_fingerprint: 603fd80a9bad2eada8423644a7b3bd6255b543e038c29cb2024917936cb5085e
    status: Archived
    audit_ids:
    - audit-4de729228280
    applied: true
    created_at: '2026-08-04T22:08:52.475420+00:00'
    applied_at: '2026-08-04T22:09:00.277485+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-4de729228280
    project_id: proj-14849f1b
    task_id: OOMPAH-461
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 603fd80a9bad2eada8423644a7b3bd6255b543e038c29cb2024917936cb5085e
    attempts:
    - version: 1
      attempt_id: attempt-1df8059d192d
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 603fd80a9bad2eada8423644a7b3bd6255b543e038c29cb2024917936cb5085e
      created_at: '2026-08-04T21:40:05.740185+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:40:05.740185+00:00'
      branch_key: epic-OOMPAH-457
      ended_at: '2026-08-04T21:46:55.535430+00:00'
      failure_reason: auditor session abandoned; no live worker owns the attempt
    - version: 1
      attempt_id: attempt-f217328aa10f
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 603fd80a9bad2eada8423644a7b3bd6255b543e038c29cb2024917936cb5085e
      created_at: '2026-08-04T21:47:08.830102+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T21:47:08.830102+00:00'
      branch_key: epic-OOMPAH-457
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-08-04T22:08:52.475218+00:00'
      ended_at: '2026-08-04T22:08:52.475218+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T21:33:17.768456+00:00'
    updated_at: '2026-08-04T22:08:52.475218+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-1df8059d192d
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 603fd80a9bad2eada8423644a7b3bd6255b543e038c29cb2024917936cb5085e
    created_at: '2026-08-04T21:40:05.740185+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:40:05.740185+00:00'
    branch_key: epic-OOMPAH-457
    ended_at: '2026-08-04T21:46:55.535430+00:00'
    failure_reason: auditor session abandoned; no live worker owns the attempt
  - version: 1
    attempt_id: attempt-f217328aa10f
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 603fd80a9bad2eada8423644a7b3bd6255b543e038c29cb2024917936cb5085e
    created_at: '2026-08-04T21:47:08.830102+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T21:47:08.830102+00:00'
    branch_key: epic-OOMPAH-457
    candidate_rotation_count: 1
---
## Summary

Implementation scope

Add IN_VALIDATION = "In Validation" to oompah/statuses.py and include it in canonical status parsing, ordering, and display lists. It must be nonterminal, non-working, and not ordinarily dispatchable. Update tracker/config status defaults and status-label conversion code only where required so native Markdown, GitHub Issues, and GitLab Issues can round-trip the value. Do not build the dashboard column or auditor scheduler in this task.

Tests

Add focused status tests for canonicalization, aliases, rank, terminal=false, working=false, and dispatchable=false. Add tracker serialization/label round-trip cases following existing status tests. Run the focused tests and make test.

Acceptance criteria

In Validation is accepted and returned consistently by every configured tracker, is not treated as Done/Merged/Archived, cannot enter ordinary worker dispatch, and does not change behavior of existing statuses.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:06
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:06
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 18:08
---
Duplicate screening complete: OOMPAH-461 is NOT a duplicate.

Evidence reviewed:
- Searched .oompah/tasks (archived, merged, open, backlog) for keywords: validation, status, lifecycle, canonical, IN_VALIDATION
- Searched docs/ and plans/ directories for IN_VALIDATION or validation status discussions
- Searched git log --all for commits mentioning 'In Validation', 'OOMPAH-461', or 'OOMPAH-457'
- Examined 25+ related tasks (OOMPAH-28, OOMPAH-252, etc.) covering status audits, lifecycle work, and existing canonicalization
- Reviewed statuses.py source code — no IN_VALIDATION constant currently exists
- Checked codebase for any prior 'In Validation' implementation attempts — none found

Closest candidates reviewed and ruled out:
- OOMPAH-28 (Archived): Audited existing 14 canonical statuses for 1.0 readiness; confirmed no gaps. Does not cover adding new statuses.
- OOMPAH-31 (Archived): Added Needs Answer / Needs Human intake statuses (separate prior feature); completed 2026-06-22. OOMPAH-461 targets a different status.
- All Release Delivery tasks (OOMPAH-200/236/252, etc.): Focus on dashboard UI/workflow, not status lifecycle.

Conclusion: OOMPAH-461 is a unique, original feature implementation task. No prior implementation or duplicate discovery found.
---
author: oompah
created: 2026-07-28 18:08
---
Focus handoff: duplicate_detector

**Outcome**: No duplicate found. OOMPAH-461 is a unique, original feature implementation task.

**Investigation scope & evidence**:
- All .oompah/tasks directories searched (200+ tasks)
- Keywords: validation, IN_VALIDATION, status, lifecycle, canonical, OOMPAH-457, OOMPAH-461
- Git history searched for 'In Validation', 'OOMPAH-461', 'OOMPAH-457'
- Reviewed 25+ related tasks covering status audits and lifecycle work
- Source code: statuses.py contains 14 existing canonical statuses; no IN_VALIDATION constant exists
- Docs/plans: No design discussions found for adding validation status

**Closest reviewed candidates**:
- OOMPAH-28 (Archived): Audited existing 14 statuses; ruled out — does not cover adding new statuses
- OOMPAH-31 (Archived): Added Needs Answer / Needs Human (different feature, completed 2026-06-22)
- All Release Delivery tasks: UI/workflow focus, not status system extensions

**Implementation scope** (from task description):
- Add IN_VALIDATION = "In Validation" constant to oompah/statuses.py
- Include in CANONICAL_STATUSES tuple and related lists (aliases, rank, etc.)
- Properties: nonterminal, non-working, not ordinarily dispatchable
- Update tracker/config status defaults for MD, GitHub Issues, GitLab Issues round-tripping
- Add comprehensive status tests (canonicalization, aliases, rank, terminal/working/dispatchable flags)
- Add tracker serialization/label round-trip tests

**Files likely to change**:
- oompah/statuses.py — main constants and logic
- oompah/tracker/*.py — GitHub Issues, GitLab, Markdown tracker status handling
- tests/test_statuses.py — focused status tests
- tests/test_*_tracker.py — tracker round-trip tests

**Remaining work**: Full implementation as described in task scope. No blockers identified.

**Recommended next focus**: feature (implement the new IN_VALIDATION status constant and integrate across all trackers)
---
author: oompah
created: 2026-07-28 18:09
---
Agent completed successfully in 161s (8580 tokens)
---
author: oompah
created: 2026-07-28 18:09
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 100, Tool calls: 53
- Tokens: 354 in / 8.2K out [8.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 41s
- Log: OOMPAH-461__20260728T180629Z.jsonl
---
author: oompah
created: 2026-07-28 18:09
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 18:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 18:09
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-28 18:09
---
Understanding: add the canonical In Validation lifecycle status, preserve its nonterminal/non-working/non-dispatchable semantics, integrate tracker round-tripping, add focused tests, and verify with focused checks plus make test.
---
author: oompah
created: 2026-07-28 18:09
---
Discovery: status vocabulary and rank live in oompah/statuses.py; GitHub label auth derives its slug map from CANONICAL_STATUSES, and label bootstrap derives required labels from the same tuple. Markdown/GitLab/GitHub adapters need targeted review for hard-coded defaults and state filters.
---
author: oompah
created: 2026-07-28 18:13
---
Implementation: added IN_VALIDATION to canonical constants, aliases, rank order, native Markdown status directories, and GitHub bootstrap labels. GitHub, GitLab, Markdown, and orchestrator candidate/state filters explicitly keep In Validation out of ordinary worker dispatch while preserving existing configured In Progress behavior.
---
author: oompah
created: 2026-07-28 18:15
---
Verification: focused status, dispatch, label-auth/bootstrap, GitHub, GitLab, and native Markdown suites pass: 681 tests passed. The first pytest invocation hit an environment import-path mismatch; rerunning with python -m pytest --import-mode=importlib passed cleanly.
---
author: oompah
created: 2026-07-28 18:21
---
Completion: delivered and pushed eb8da0e97. In Validation now canonicalizes aliases, has ordered display/rank support, remains nonterminal/non-working/non-dispatchable, round-trips through native Markdown, GitHub labels, and GitLab labels, and is excluded from ordinary worker candidates. Focused tests: 681 passed. Full make test gate: 12,631 passed, 7 skipped (14 pre-existing warnings). Branch is clean and up to date with origin.
---
author: oompah
created: 2026-07-28 18:21
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 98
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 12m 27s
- Log: OOMPAH-461__20260728T180914Z.jsonl
---
author: oompah
created: 2026-07-28 18:21
---
Added canonical In Validation lifecycle status with tracker round-tripping and dispatch exclusion; tests and full gate pass.
---
author: oompah
created: 2026-08-04 21:33
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 21:47
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 21:47
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 22:08
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- commit: eb8da0e97
- commit_message: OOMPAH-461: add In Validation lifecycle status
- on_main: true
- focused_tests_passed: 701
- files_changed: 13
- in_canonical_statuses: true
- not_in_terminal_statuses: true
- not_in_working_statuses: true
- not_in_dispatchable_statuses: true
- aliases_present: in validation, validation
---
<!-- COMMENTS:END -->
