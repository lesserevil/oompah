---
id: OOMPAH-783
type: feature
status: Done
priority: 1
title: Implement the durable workflow worker and resumable external-effect saga
parent: OOMPAH-766
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-780
labels: []
assignee: null
created_at: '2026-08-04T13:59:02.492322Z'
updated_at: '2026-08-04T15:51:14.109643Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-783
  head_sha: a55846f783f215ce2383ab4d67699031ddc8a71b
  submitted_at: '2026-08-04T15:50:27.189523+00:00'
  updated_at: '2026-08-04T15:50:27.189523+00:00'
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-a97cb3deb035
    project_id: proj-14849f1b
    task_id: OOMPAH-783
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 840d4cadc71e391f55ebaeeb58d05edf821cf6c738ec2ac4494d190663ed0deb
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Direct-owner exact-head integration: commit a55846f783f215ce2383ab4d67699031ddc8a71b
      was proven a descendant and fast-forwarded to epic-OOMPAH-766. Verification:
      206 workflow worker/job/decision/transition tests, ruff check/format, terminal
      mutation scan, secret scan, and diff check passed.'
    created_at: '2026-08-04T15:50:56.972798+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-783
    target_state: Done
    evidence_fingerprint: 840d4cadc71e391f55ebaeeb58d05edf821cf6c738ec2ac4494d190663ed0deb
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-04T15:51:10.536975+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Build the worker that consumes WorkDecision actions as jobs and executes persist intent -> lease -> revalidate -> external effect -> verify -> checkpoint -> transition request -> complete. Define idempotent action handler interfaces for tracker/Git/forge/audit work, interruption checks, heartbeats, bounded timeouts, error taxonomy, and safe recovery when an effect succeeds before acknowledgement. Required tests inject death/failure after every step, stale evidence after claim, effect-already-applied, transition-applied-before-crash, lost lease, handler timeout, and shutdown drain. Acceptance: every incomplete job resumes, supersedes, or reaches explicit action_required after restart; late workers cannot mutate a reclaimed generation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 15:50
---
Implemented the durable workflow worker saga: token-fenced leases and heartbeats; exact generation/evidence/head revalidation; idempotency inspection; bounded external effects and verification; durable phase checkpoints; TaskTransitionService routing; retry/error taxonomy; stale-race supersession; cooperative interruption; graceful drain; and restart recovery. Added 31 focused tests including process-death injection at leased, revalidated, effect pending/returned/verified, transition returned/applied, and completed boundaries; effect-before-ack and transition-before-ack recovery; lost leases; timeouts; and cancellation. Verification: 206 focused/adjacent tests passed; ruff check/format, make terminal-audit-scan, staged secret scan, and diff check passed.
---
author: oompah
created: 2026-08-04 15:50
---
Implemented and verified the resumable durable workflow worker; exact commit a55846f783f215ce2383ab4d67699031ddc8a71b is ready to land on epic-OOMPAH-766.
---
author: oompah
created: 2026-08-04 15:51
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct-owner exact-head integration: commit a55846f783f215ce2383ab4d67699031ddc8a71b was proven a descendant and fast-forwarded to epic-OOMPAH-766. Verification: 206 workflow worker/job/decision/transition tests, ruff check/format, terminal mutation scan, secret scan, and diff check passed.
---
<!-- COMMENTS:END -->
