---
id: OOMPAH-785
type: task
status: Done
priority: 1
title: Replace process-local workflow scheduling primitives with durable job ownership
parent: OOMPAH-766
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-783
- OOMPAH-779
labels: []
assignee: null
created_at: '2026-08-04T13:59:05.979634Z'
updated_at: '2026-08-04T16:35:45.906015Z'
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
  task_branch: OOMPAH-785
  head_sha: fd480f6bd8aeab2763b927bee841ffae52a345e1
  submitted_at: '2026-08-04T16:35:01.954426+00:00'
  updated_at: '2026-08-04T16:35:01.954426+00:00'
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-94bcbd5eeb34
    project_id: proj-14849f1b
    task_id: OOMPAH-785
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cc4ae5ee49a81edc4b2971b04f8a122ae99b013c2ed9fe1e2f6b191f6d9d23fb
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project owner directly verified fd480f6bd with the exact prerequisite
      merge: focused workflow and scheduler tests, 428 adjacent orchestration tests,
      terminal mutation scan, secret scan, lint, compile, and ancestry all passed;
      the exact head is now the tip of epic-OOMPAH-766.'
    created_at: '2026-08-04T16:35:33.873482+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-785
    target_state: Done
    evidence_fingerprint: cc4ae5ee49a81edc4b2971b04f8a122ae99b013c2ed9fe1e2f6b191f6d9d23fb
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-04T16:35:44.210996+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Add the event-to-decision-to-job scheduling layer and migrate shared lifecycle ownership away from fire-and-forget futures, mutable cooldown maps, completed/reject sets, and timer-only retries as domain handlers become available. Events become wakeups; durable rows remain correctness authority. Preserve per-project/task serialization without a global bottleneck and expose queue/lease/retry health. Required tests: event coalescing/missed events, duplicate scheduling, concurrent ticks, process restart, bounded full-sync recovery, per-project fairness, and graceful drain. Acceptance: lifecycle progress never depends solely on an in-memory future/map/monotonic timestamp and a missed event cannot strand work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 16:35
---
Implemented commit fd480f6bd on canonical branch OOMPAH-785 after merging exact prerequisite heads. Added durable per-task decision cursors with persisted activation generations and stale-scan CAS fencing; atomic decision-to-job enqueue/replay/supersession; recurrence-safe A→B→A activation; per-task execution serialization; restart-persistent project fairness and bounded rotating decision windows; coalesced event wakeups plus mandatory full-sync recovery; bounded fair worker driving, startup recovery, graceful drain, aggregate lease/retry/queue health in state/WebSocket snapshots, schema v3 migration, and design documentation. Verification: 100 workflow-focused tests passed, 428 adjacent orchestrator/event-loop/long-tick/WebSocket/state/IPC tests passed, the final 17 scheduler tests passed after scan-window hardening, terminal mutation scan passed, secret scan passed, Ruff/format/compile/diff checks passed.
---
author: oompah
created: 2026-08-04 16:35
---
Implemented restart-safe event-to-decision-to-job scheduling with durable stale-scan fences, task serialization, persisted fairness, bounded full-sync recovery, graceful drain, and queue health.
---
author: oompah
created: 2026-08-04 16:35
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Project owner directly verified fd480f6bd with the exact prerequisite merge: focused workflow and scheduler tests, 428 adjacent orchestration tests, terminal mutation scan, secret scan, lint, compile, and ancestry all passed; the exact head is now the tip of epic-OOMPAH-766.
---
<!-- COMMENTS:END -->
