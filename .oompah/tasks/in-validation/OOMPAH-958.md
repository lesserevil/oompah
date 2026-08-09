---
id: OOMPAH-958
type: bug
status: In Validation
priority: 1
title: Bridge durable integration workflow authority to exact queue leases
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T12:44:46.874602Z'
updated_at: '2026-08-09T14:37:41.793703Z'
work_branch: OOMPAH-958
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-958
  base_branch: epic-OOMPAH-940
  base_sha: 1ab5776d8e191d7cf1e98696a322969485a7d35a
  head_sha: 44c2e40d0940f0c8f5edd859141b1b042eafd411
  submitted_at: '2026-08-09T13:09:54.446784+00:00'
  updated_at: '2026-08-09T13:09:54.446784+00:00'
oompah.work_branch: OOMPAH-958
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-42e232e2c1de
    project_id: proj-14849f1b
    task_id: OOMPAH-958
    digest: f854211d29753504241eba273dd748323ab6a16e04c834bdb72f31c1614ad127
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-42e232e2c1de
    project_id: proj-14849f1b
    task_id: OOMPAH-958
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f854211d29753504241eba273dd748323ab6a16e04c834bdb72f31c1614ad127
    attempts:
    - version: 1
      attempt_id: attempt-aa9e85abcb71
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f854211d29753504241eba273dd748323ab6a16e04c834bdb72f31c1614ad127
      created_at: '2026-08-09T14:37:32.749924+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T14:37:32.749924+00:00'
      branch_key: OOMPAH-958
      selected_ref: 44c2e40d0940f0c8f5edd859141b1b042eafd411
      selected_sha: 44c2e40d0940f0c8f5edd859141b1b042eafd411
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: In Progress
    created_at: '2026-08-09T13:12:17.244771+00:00'
    selected_ref: 44c2e40d0940f0c8f5edd859141b1b042eafd411
    selected_sha: 44c2e40d0940f0c8f5edd859141b1b042eafd411
    updated_at: '2026-08-09T14:37:32.749924+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-aa9e85abcb71
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f854211d29753504241eba273dd748323ab6a16e04c834bdb72f31c1614ad127
    created_at: '2026-08-09T14:37:32.749924+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T14:37:32.749924+00:00'
    branch_key: OOMPAH-958
    selected_ref: 44c2e40d0940f0c8f5edd859141b1b042eafd411
    selected_sha: 44c2e40d0940f0c8f5edd859141b1b042eafd411
---
## Summary

Triggered by live durable workflow failures on OOMPAH-941, OOMPAH-943, OOMPAH-954, OOMPAH-955, and OOMPAH-956.\n\nThe ProductionIntegrationWorkflowBackend passes a ready IntegrationQueue row directly to Orchestrator._execute_integration_item, but the executor's current-authority predicate requires IntegrationQueue.owns_active_lease. Durable workflow integration_attempt jobs therefore deterministically fail before preparation with "integration authority was withdrawn before preparation": OOMPAH-941/OOMPAH-943 exhausted 5/5 even though their heads are already in the epic; OOMPAH-954/OOMPAH-956 have started consuming attempts; OOMPAH-955 is queued and at risk.\n\nImplementation scope: bridge durable workflow job authority to the legacy integration executor with an exact, bounded IntegrationQueue lease or an equivalently strong explicit workflow authority contract. Preserve project/task/branch/head, queue generation, workflow job generation, lease owner/token/deadline, replacement/expiry/ABA fencing, cancellation, heartbeat during long quality gates/integration, and exact release/cleanup on success, retry, cancellation, and exceptions. Never bypass or weaken IntegrationQueue.owns_active_lease for legacy callers. Make already-landed epic-child heads converge idempotently without rerunning unsafe effects.\n\nRequired tests: production-shaped workflow integration claim acquires exact queue authority and reaches preparation; missing/stale/expired/replaced queue or workflow lease fails closed; cancellation and exception release only the exact lease; heartbeat keeps a legitimate long effect authorized; concurrent legacy/workflow claims have one winner; restart/replay is idempotent; already-landed OOMPAH-941/OOMPAH-943-shaped rows complete from ancestry proof; retries for OOMPAH-954/OOMPAH-955/OOMPAH-956 no longer spend attempts on deterministic authority mismatch.\n\nAcceptance: durable integration_attempt jobs can never enter the executor without matching fenced queue authority; no stale or concurrent generation can mutate; focused integration-workflow/queue/executor/restart tests and required Makefile scans pass; after deployment, use supported service rearm/resubmission (no SQLite edits) to recover OOMPAH-941/OOMPAH-943 and let OOMPAH-954/OOMPAH-955/OOMPAH-956 flow naturally.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 12:56
---
Root cause confirmed and regression-tested on the newly composed epic head. Durable workflow integration deliberately keeps IntegrationQueue rows ready+unleased while its heartbeat-fenced workflow job owns effect authority; the shared executor incorrectly required the legacy queue lease both before preparation and again during candidate canonicalization. Implemented an explicit workflow-authority path that preserves exact job generation, queue generation, tracker branch/head, interruption, candidate head/base, and quality-gate owner fencing while leaving the legacy owns_active_lease path unchanged. Rebased head 9a61587fb0f904da22e1aa46e4cef0b79091e87c; 353 focused workflow/integration/executor/recovery tests pass. Independent review pending before push/submission.
---
author: oompah
created: 2026-08-09 13:09
---
Qualification complete on pushed exact head 44c2e40d0940f0c8f5edd859141b1b042eafd411, rebased onto composed epic head 1ab5776d8e191d7cf1e98696a322969485a7d35a. Production-shaped coverage now proves real WorkflowJobStore token/deadline expiry and ABA replacement, DurableWorkflowWorker heartbeat renewal, timeout quarantine and late-effect fencing, restart receipt replay without effect reexecution, exact attempt accounting, concurrent legacy/workflow one-winner ownership, invalid mixed/leased/generation-less authority rejection, candidate generation/owner fencing, and unchanged legacy owns_active_lease behavior. Validation: 515 focused tests passed; reviewer independently ran 405 combined tests plus 20 repeated timing-sensitive runs; terminal mutation scan, secret scan, and diff check passed. Independent re-review: no blockers.
---
author: oompah
created: 2026-08-09 13:10
---
Bridge durable integration workflow jobs into the shared executor with explicit exact workflow authority, preserving unleased queue checkpoint semantics and the legacy queue-lease fence. Candidate quality-gate authority is bound to job generation, candidate head, and base; stale, expired, replaced, concurrent, timed-out, and restarted executions fail closed. 515 focused tests and independent no-blocker review passed.
---
author: oompah
created: 2026-08-09 13:12
---
Worked around the exact integration bug this task fixes by fast-forwarding its independently reviewed exact head 44c2e40d0 into origin/epic-OOMPAH-940. The submitted task head is now an exact ancestor of its authoritative target.
---
author: oompah
created: 2026-08-09 13:12
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 14:37
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 14:37
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
