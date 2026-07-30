---
id: OOMPAH-628
type: bug
status: In Validation
priority: 1
title: Rearm explicitly resubmitted integrated queue rows
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T22:37:04.318940Z'
updated_at: '2026-07-30T22:51:56.205790Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.integration:
  version: 1
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-585--task-OOMPAH-628
  base_branch: epic-OOMPAH-585
  base_sha: 2a8fc4a4b3a101c15e2fea0608480f783f9f3e28
  head_sha: b8c6817b12744e164a2de65b3c49ce8e3ce2b551
  integrated_sha: b8c6817b12744e164a2de65b3c49ce8e3ce2b551
  submitted_at: '2026-07-30T22:41:28.108593+00:00'
  updated_at: '2026-07-30T22:46:48.872338+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-2f03e5509604
    project_id: proj-14849f1b
    task_id: OOMPAH-628
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 87eacfec78bca7a0b9e1ded75ba2ff0de471743246c18e3bd452045c916b811d
    attempts:
    - version: 1
      attempt_id: attempt-62700fcd7450
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 87eacfec78bca7a0b9e1ded75ba2ff0de471743246c18e3bd452045c916b811d
      created_at: '2026-07-30T22:50:02.911008+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T22:50:02.911008+00:00'
      branch_key: OOMPAH-628
      failure_classification: infrastructure_error
      ended_at: '2026-07-30T22:51:52.412521+00:00'
      failure_reason: normal
      next_retry_at: '2026-07-30T22:52:02.412491+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T22:46:51.130292+00:00'
    updated_at: '2026-07-30T22:51:52.412521+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-62700fcd7450
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 87eacfec78bca7a0b9e1ded75ba2ff0de471743246c18e3bd452045c916b811d
    created_at: '2026-07-30T22:50:02.911008+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T22:50:02.911008+00:00'
    branch_key: OOMPAH-628
    failure_classification: infrastructure_error
    ended_at: '2026-07-30T22:51:52.412521+00:00'
    failure_reason: normal
    next_retry_at: '2026-07-30T22:52:02.412491+00:00'
oompah.task_costs:
  total_input_tokens: 6
  total_output_tokens: 451
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 6
      output_tokens: 451
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 451
    cost_usd: 0.0
    recorded_at: '2026-07-30T22:51:52.228719+00:00'
---
## Summary

Implementation scope: distinguish an explicit operator resubmission of a task whose tracker lifecycle was deliberately returned to Ready to Integrate from background synchronization of an already-integrated queue row. Allow the explicit API/CLI submit path to rearm the identical task branch and head only when the canonical task integration record is newly Ready, while preserving idempotency for duplicate submissions in Ready or Integrating and for periodic synchronization. This repairs the observed OOMPAH-627 state where supported Done-to-Ready reflow wrote a new ready integration record but IntegrationQueueStore.enqueue returned the old integrated row forever. Relevant files: oompah/integration_queue.py, server submission wiring, orchestrator synchronization, and focused queue/submission tests. Tests must reproduce same-head integrated explicit reflow, prove background sync remains integrated/idempotent, prove ordinary duplicate active submissions do not reset leases or attempts, and run the focused tests plus the Makefile gate. Acceptance criteria: an explicitly reflowed same-head task cannot remain stranded in Ready to Integrate behind an integrated durable row; no automatic duplicate integration loop is introduced; all focused and complete tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 22:37
---
Claimed directly to repair the live same-head integration queue deadlock before completing the epic rollout.
---
author: oompah
created: 2026-07-30 22:41
---
Implemented explicit same-head integrated-row rearming behind a fresh-ready evidence fence; background and active-row idempotency remain unchanged.
---
author: oompah
created: 2026-07-30 22:41
---
Implementation complete at b8c6817b12744e164a2de65b3c49ce8e3ce2b551. Verification: 26 focused integration-queue/task-handoff tests passed; expanded queue/handoff/orchestrator suite reported 302 passed; terminal mutation scan passed. Regression covers integrated same-head explicit reflow, background synchronization idempotency, and ready/integrating lease preservation.
---
author: oompah
created: 2026-07-30 22:41
---
Rearm only explicit fresh-ready same-head reflows while preserving automatic and active-row idempotency.
---
author: oompah
created: 2026-07-30 22:46
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 22:47
---
Audit handoff: exact integrated task/epic head is b8c6817b12744e164a2de65b3c49ce8e3ce2b551 and passed the complete Makefile gate. Focused verification: 26 queue/handoff tests passed; expanded queue/handoff/orchestrator run reported 302 passed; terminal mutation scan passed. Review the fresh-ready rearm fence, background idempotency, and active lease preservation, then submit the structured verdict without reimplementation.
---
author: oompah
created: 2026-07-30 22:50
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 22:50
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 22:51
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 3, Tool calls: 0
- Tokens: 6 in / 451 out [457 total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 46s
- Log: OOMPAH-628__20260730T225012Z.jsonl
---
author: oompah
created: 2026-07-30 22:51
---
Auditor attempt ended: auditor exited (normal) without a result. A different independent auditor will be tried on the next scheduler tick.
---
<!-- COMMENTS:END -->
