---
id: OOMPAH-357
type: task
status: In Validation
priority: 1
title: Define actionable epic branch synchronization policy
parent: OOMPAH-356
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T01:23:49.686725Z'
updated_at: '2026-08-02T01:33:10.952697Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 951c7d25-3fe7-4b6a-9775-c7c46d7014fd
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-366580793319
    project_id: proj-14849f1b
    task_id: OOMPAH-357
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 624ba18a5f7cc991ac0e7eabbacda5e4261ee35ebc4a9ec1defabd9154ebe071
    attempts:
    - version: 1
      attempt_id: attempt-306137c9db77
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 624ba18a5f7cc991ac0e7eabbacda5e4261ee35ebc4a9ec1defabd9154ebe071
      created_at: '2026-08-02T01:32:55.857461+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:32:55.857461+00:00'
      branch_key: OOMPAH-357
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:12:50.727916+00:00'
    updated_at: '2026-08-02T01:32:55.857461+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-306137c9db77
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 624ba18a5f7cc991ac0e7eabbacda5e4261ee35ebc4a9ec1defabd9154ebe071
    created_at: '2026-08-02T01:32:55.857461+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:32:55.857461+00:00'
    branch_key: OOMPAH-357
---
## Summary

Audit every orchestrator path that currently detects, schedules, or performs epic branch merge/rebase work. Implement a single policy decision point that classifies a request as allowed or suppressed.\n\nRules:\n- Suppress automatic synchronization solely because main advanced.\n- Always suppress direct synchronization between two epic branches.\n- Allow synchronization only for: explicit operator request; an epic PR being opened/refreshed; a merge-blocking conflict or required-base condition; or a configured staleness threshold for a long-lived branch.\n- Return a machine-readable reason for both allowed and suppressed decisions.\n\nTests:\n- Unit tests for each allow and suppress case.\n- Regression test that an incomplete stale epic is reported but no rebase/merge action is queued.\n\nAcceptance criteria:\n- All epic synchronization callers use the policy decision point.\n- The default policy has no automatic main-to-epic synchronization.\n- Direct epic-to-epic synchronization is impossible through Oompah automation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:29
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 01:29
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 01:30
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 0, Tool calls: 2
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 30s
- Log: OOMPAH-357__20260722T012937Z.jsonl
---
author: oompah
created: 2026-07-22 01:30
---
Implemented policy gate: main advancement is observation-only, explicit requests/conflicts are actionable, and epic-to-epic synchronization is prohibited.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: the actionable synchronization policy gate is present on origin/main in commit 2ba37886b. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:27
---
Verified delivered on origin/main in 2ba37886b and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:12
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:33
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:33
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
