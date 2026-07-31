---
id: OOMPAH-658
type: bug
status: Open
priority: 2
title: Deduplicate duplicate-preflight runs across deferred dispatch ticks
parent: null
children: []
blocked_by:
- OOMPAH-657
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T11:19:01.632127Z'
updated_at: '2026-07-31T11:19:15.232962Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7dacb214eb5cff97521a3899e7dbe399f5079dcbb7addd84b6d5610b4040efe9
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: e4a95e10-2947-471e-a955-b75df2d4031a
  claim_owner: f6d86559-4e9d-42bf-ac66-416781dbb14f
  claimed_at: '2026-07-31T11:19:07.121451+00:00'
  claim_expires_at: '2026-07-31T11:49:07.121451+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 45a246a5-1e77-4d13-bc05-3ebf993b75f6
---
## Summary

Triggered by: OOMPAH-655

Live scheduler reproduction on OOMPAH-655: after one unchanged Open transition, duplicate screening ran at 11:09-11:11 (comments 36-38), then ran again at 11:13-11:15 (comments 39-41) before the implementation agent dispatched. No task status, description, branch head, dependency, or duplicate-screening input changed between runs. This wastes provider capacity and can starve implementation while a finish-order dependency delays dispatch. Implementation scope: persist or retain duplicate-preflight completion keyed to the exact task intake/evidence revision, treat a completed normal/no-duplicate result as satisfied across scheduler ticks and dependency waits, invalidate it only when relevant title/description/source/parent/revision inputs change, and keep concurrent ticks single-flight. Relevant code includes duplicate-preflight focus/dispatch selection, claimed/completed state recovery, retry handling, and task metadata. Add deterministic multi-tick and restart tests with an Open task held behind an unfinished finish-order dependency; prove exactly one screening launches for an unchanged revision, implementation dispatch follows when eligible, changed intake triggers exactly one new screen, failures retry according to policy, and project/task isolation holds. Acceptance: unchanged Open work cannot launch duplicate investigators repeatedly; no valid rescreen is suppressed; focused scheduler tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 11:19
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 11:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 11:19
---
Finish-order dependency on OOMPAH-657: implement in parallel, but final gate/review must use the immutable exact-head lifecycle.
---
<!-- COMMENTS:END -->
