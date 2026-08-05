---
id: OOMPAH-838
type: bug
status: Ready to Integrate
priority: 1
title: Preserve forced quality-gate retry through integration claim
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:45:03.282492Z'
updated_at: '2026-08-05T17:16:13.042545Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-838
  head_sha: 005e9e717de8cf1d77b4c3331df20ecc64c421e9
  submitted_at: '2026-08-05T16:58:22.388278+00:00'
  updated_at: '2026-08-05T16:58:22.388278+00:00'
---
## Summary

Live regression from OOMPAH-523: an explicit same-head resubmission correctly calls IntegrationQueueStore.enqueue(... explicit_retry=True) and persists retry_forced=1, but claim_next clears retry_forced before returning the claimed IntegrationQueueItem. Orchestrator._execute_integration_item therefore always passes retry_forced=False to BranchQualityGate, reuses the prior cached failed result, and immediately routes a locally verified clean head back to Needs CI Fix. The cached failure for 9ea2b5523 is a 48.94-second truncated 9%-progress run containing only PASS lines; OOMPAH-523's immediately preceding official make test passed 15,452 tests. Implementation scope: carry one-shot force-retry authority on the claimed item while atomically clearing the durable pending flag so restarts do not loop; distinguish consumed retry intent from stored ready state and preserve exact owner/head fencing. Relevant files: oompah/integration_queue.py, oompah/orchestrator.py integration claim/execution, quality-gate cache tests. Required tests: blocked same-head explicit retry bypasses a cached failed/timed-out/error result exactly once; claimed item exposes the consumed force flag while the persisted integrating row no longer advertises a pending retry; crash/recovery does not loop; normal/new-head claims remain unforced; OOMPAH-523 regression. Acceptance: an explicit same-head resubmission executes a fresh exact gate instead of replaying cached failure, and a passing gate can integrate naturally without manual cache deletion or fake commits.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 16:58
---
Implemented one-shot forced gate retry handoff with exact SQLite claim fencing. The durable retry flag is consumed atomically at claim, an ephemeral claimed authority reaches the executor, crash recovery cannot loop, and the returned head/lease cannot race with another connection's replacement. Independent re-review found no blockers. Verification: 43 focused queue/executor tests passed; terminal mutation scan passed 8/8.
---
author: oompah
created: 2026-08-05 16:58
---
Preserved one-shot forced quality-gate retry through exact fenced integration claims; 43 focused tests and terminal mutation scan pass.
---
author: oompah
created: 2026-08-05 16:58
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-838`
Target: `main`
Head: `005e9e717de8cf1d77b4c3331df20ecc64c421e9`
Command: `make test`
Result: `infrastructure_error`

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Trusted quality-gate runtime corruption detected; candidate CI was not run: trusted editable source mapping is inconsistent: expected one of ['/home/shedwards/src/oompah'] or immutable candidate /home/shedwards/.oompah/tmp/oompah-quality-gate-k34subi4/workspace; actual /home/shedwards/.oompah/worktrees/oompah/OOMPAH-838. Repair or replace the service test runtime before rerunning the branch gate.
```
---
author: oompah
created: 2026-08-05 17:16
---
Branch quality gate passed for `005e9e717de8cf1d77b4c3331df20ecc64c421e9` using `make test` in 635.7s. Review creation may proceed.
---
<!-- COMMENTS:END -->
