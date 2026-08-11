---
id: OOMPAH-1082
type: task
status: In Review
priority: null
title: Wake and age chained terminal-audit stages only after prerequisites become
  eligible
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T11:08:16.081490Z'
updated_at: '2026-08-11T11:36:07.349445Z'
work_branch: OOMPAH-1082
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/819
review_number: '819'
review_head: a2d82ab7009cdba0bb325296d26d73568906a593
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 874ac2f5-239e-4a7e-9442-06875ae3cd57
  request_fingerprint: 598acece51eff7c2be5431e6f95b016bb819341113c8f2b0b2f3fd89a5d1c05d
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1082
  head_sha: a2d82ab7009cdba0bb325296d26d73568906a593
  submitted_at: '2026-08-11T11:30:18.399366+00:00'
  updated_at: '2026-08-11T11:30:18.399366+00:00'
oompah.work_branch: OOMPAH-1082
oompah.review_url: https://github.com/lesserevil/oompah/pull/819
oompah.review_number: '819'
oompah.target_branch: main
oompah.review_head: a2d82ab7009cdba0bb325296d26d73568906a593
---
## Summary

Triggered by: OOMPAH-1072. Live evidence: Merged was requested and the coordinator correctly created a Done prerequisite audit plus Merged audit. Done audit-00d5d7755c13 passed at 10:43:03 and left In Validation as designed. The next Merged audit-078f5a8faba5 and durable workflow-job-ce9f7c40c06a44ebb780a1c28c811c9d remained pending/queued with attempts=0 across graceful restart until an 11:02 owner workaround, despite available audit capacity. Health also reported it stale using the chain creation time 08:56, including the period when Merged was not yet eligible because Done was running. Scope: atomically mark/wake the next chained terminal stage when its prerequisite result commits; ensure durable workflow scheduling immediately revisits that exact job after PASS and restart; define pending age from the stage eligible-at boundary rather than initial blocked-chain creation; preserve distinct-auditor policy, exact evidence/revision binding, lane budgets/fairness, idempotent recovery, pause semantics, and no concurrent sibling launch. Relevant code: TerminalTransitionCoordinator advanced_target/result commit, terminal audit workflow jobs, Orchestrator audit-lane continuation/candidate cursor, and terminal_audit_health. Tests/acceptance: Done PASS makes the existing Merged job eligible and dispatchable within one bounded continuation without waiting for a full poll; crash/restart between result commit and wake converges once; blocked next stages do not age as stale; truly eligible unattempted stages do; capacity/pause waits remain truthful; no duplicate launch or bypass of independent candidates; focused tests and protected CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 11:30
---
Make chained terminal-audit successor eligibility durable and restart-safe, wake the exact successor after prerequisite PASS, and age only eligible stages at a2d82ab7009cdba0bb325296d26d73568906a593; 496 focused and 915 adjacent tests plus terminal scan pass.
---
author: oompah
created: 2026-08-11 11:35
---
Branch quality gate passed for `a2d82ab7009cdba0bb325296d26d73568906a593` using `make test` in 176.2s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 11:36
---
Independent exact-head review BLOCKED a2d82ab7009cdba0bb325296d26d73568906a593: prerequisite_audit_id is persisted but not enforced. An eligible Merged stage referencing audit-done-other can fail open and dispatch using a different same-authority Done PASS audit-done-a; coordinator PASS stamping can also preserve the wrong ID while making it eligible. Author is fixing exact prerequisite identity enforcement plus wrong/missing/stale negative regressions; this head will not merge.
---
<!-- COMMENTS:END -->
