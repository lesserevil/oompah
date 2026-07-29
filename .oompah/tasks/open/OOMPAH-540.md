---
id: OOMPAH-540
type: task
status: Open
priority: null
title: Let read-only duplicate preflight bypass dependency and epic serialization
  gates
parent: null
children: []
blocked_by: []
labels:
- needs:backend
- needs:test
- needs:docs
assignee: null
created_at: '2026-07-29T00:46:32.053029Z'
updated_at: '2026-07-29T00:48:49.328808Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ab83d9f4e304a67a40246836c5e51e480ddc6fed67248267b351bb1d20b021f9
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 18b14cc7-379e-4502-9a52-f1f144050e37
  claim_owner: f4d00fa0-7632-4aaf-969a-6ff8237892b3
  claimed_at: '2026-07-29T00:48:48.578929+00:00'
  claim_expires_at: '2026-07-29T01:18:48.578929+00:00'
  retry_count: 0
  retry_after: null
---
## Summary

The Open-task duplicate-preflight implementation incorrectly reuses normal implementation eligibility for dependency readiness and one-agent-per-epic/shared-branch serialization. This defeats the feature's purpose: duplicate checks are read-only qualification work intended to run early on any ordinary Open task while screening capacity is available, even when implementation must wait on dependencies or another child is actively changing the shared epic branch. Production evidence on 2026-07-29: 21 unchecked Open tasks remained unscreened with 8 spare hardware slots because OOMPAH-471 through OOMPAH-489 were rejected by dependency/shared-epic gates.\n\nImplementation scope:\n- For duplicate_preflight=True only, bypass unresolved dependency/blocker readiness and one-agent-per-epic/shared-branch busy gates.\n- Continue enforcing ordinary-task/Open-state eligibility, exact per-task claim/running exclusivity, global/project pause, budget/rate/provider availability and whitelist, screening cap, deterministic ordering, and implementation-first capacity reservation.\n- Keep preflight strictly read-only and keep the task Open. Do not weaken any implementation dispatch gate.\n- Update documentation that currently says dependency and shared-epic constraints apply.\n\nRequired tests:\n- A dependency-blocked Open child can enter duplicate screening but cannot enter implementation.\n- A second child of a shared epic can screen while a sibling implementation agent is active, without moving state or mutating the worktree.\n- The same task cannot screen and implement concurrently and two preflights cannot claim the same task.\n- Pause, provider, budget, terminal/non-task, capacity cap, and implementation-lane reservation remain enforced.\n- Deterministic ordering remains stable and implementation behavior is unchanged. Run focused scheduler tests and make test.\n\nAcceptance criteria:\nWith spare screening capacity, blocked ordinary Open tasks and siblings of an actively implemented shared epic are selected for read-only duplicate preflight; implementation remains blocked until normal dependency/epic gates pass; screening stays Open and claim-safe; and production begins draining the existing unchecked Open queue.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 00:46
---
Claimed by the current interactive Codex session for immediate implementation and production verification; do not dispatch another worker for this task.
---
<!-- COMMENTS:END -->
