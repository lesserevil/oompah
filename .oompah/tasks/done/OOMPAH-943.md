---
id: OOMPAH-943
type: bug
status: Done
priority: 1
title: Persist successful landing refresh facts before job completion
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:32.442706Z'
updated_at: '2026-08-09T16:26:09.057445Z'
work_branch: OOMPAH-943
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
  task_branch: OOMPAH-943
  base_branch: epic-OOMPAH-940
  base_sha: b7e7d9509a4e6025b48c54336098acef2dda4986
  head_sha: b30a2880d57460b730547faa2d90732a4bab8e9c
  submitted_at: '2026-08-09T09:44:21.729146+00:00'
  updated_at: '2026-08-09T09:44:21.729146+00:00'
oompah.work_branch: OOMPAH-943
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-ac3836042a86
    project_id: proj-14849f1b
    task_id: OOMPAH-943
    digest: a9f43b17f0a0e1a017c70050d59ebc60182ae1c132df8a1ce9298c97555256dd
  oompah.terminal_override_records:
  - version: 1
    override_id: override-d9ff64830cfe
    project_id: proj-14849f1b
    task_id: OOMPAH-943
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a9f43b17f0a0e1a017c70050d59ebc60182ae1c132df8a1ce9298c97555256dd
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner override after exact accepted head b30a2880d57460b730547faa2d90732a4bab8e9c
      was proven contained in aggregate head 2dd74be288b81265ea4a242d7467ecc1ed9f1435,
      merged by PR #757 as ba0859da9d47d3417a50bfbaa2cb10a7a32f5f01, with hosted Python
      3.11/3.12/3.13 checks successful.'
    created_at: '2026-08-09T16:25:52.994430+00:00'
    selected_ref: b30a2880d57460b730547faa2d90732a4bab8e9c
    selected_sha: b30a2880d57460b730547faa2d90732a4bab8e9c
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-943
    target_state: Done
    evidence_fingerprint: a9f43b17f0a0e1a017c70050d59ebc60182ae1c132df8a1ce9298c97555256dd
    audit_ids:
    - audit-ac3836042a86
    kind: override
    applied: true
    retired_at: '2026-08-09T16:26:05.058934+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-ac3836042a86
    project_id: proj-14849f1b
    task_id: OOMPAH-943
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a9f43b17f0a0e1a017c70050d59ebc60182ae1c132df8a1ce9298c97555256dd
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Ready to Integrate
    created_at: '2026-08-09T12:52:58.786711+00:00'
    selected_ref: b30a2880d57460b730547faa2d90732a4bab8e9c
    selected_sha: b30a2880d57460b730547faa2d90732a4bab8e9c
    updated_at: '2026-08-09T16:26:05.058902+00:00'
  attempt_history: []
---
## Summary

Live OOMPAH-761/OOMPAH-762 generation-246 integration_landing_refresh jobs completed with git_ancestry checkpoints, but workflow_landing_facts retained no rows and later generations queued the same landing action again. Scope: make the integration landing action durably persist the exact source/target/revision/result fact in the same fenced success boundary before completing the job; make replay idempotent and ensure publication failures retry rather than report success. Relevant code: integration action backend/controller, workflow_landing_facts store, workflow worker completion/replay. Tests: successful ancestry and patch-equivalence effects survive restart and suppress a replacement action; persistence failure cannot complete; stale lease/revision cannot publish; repeated event is idempotent. Acceptance: a successful refresh is observable by the next fact cut and is not re-enqueued absent evidence change.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 09:10
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
author: oompah
created: 2026-08-09 09:43
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-943`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`
Process: ended without subprocess exit evidence

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
author: oompah
created: 2026-08-09 09:44
---
Implementation complete on pushed branch OOMPAH-943 at b30a2880d. PR #753 is open with squash auto-merge enabled. Local verification: 298 focused workflow/integration tests and 39 epic-workflow tests passed; Ruff, terminal task-status mutation scan, and secret scan passed. The atomic completion boundary now persists durable landing facts, rejects stale authority/evidence, retries persistence failures, replays idempotently, and feeds proof into the next fact cut.
---
author: oompah
created: 2026-08-09 09:44
---
Persisted successful integration landing proof atomically with fenced job completion, added idempotent replay and retry-on-publication-failure semantics, rejected stale lease/revision publication, and consumed durable proof on subsequent fact cuts to suppress replacement refresh actions. PR #753; local verification: 298 focused tests plus 39 epic-workflow tests.
---
author: oompah
created: 2026-08-09 12:52
---
Reconciled the in-flight integration deadlock: the accepted task commits are authoritatively contained in origin/epic-OOMPAH-940, so the exhausted administrative integration job is obsolete. Advancing to terminal validation while OOMPAH-958 fixes the systemic lease contract.
---
author: oompah
created: 2026-08-09 12:53
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 16:26
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Project-owner override after exact accepted head b30a2880d57460b730547faa2d90732a4bab8e9c was proven contained in aggregate head 2dd74be288b81265ea4a242d7467ecc1ed9f1435, merged by PR #757 as ba0859da9d47d3417a50bfbaa2cb10a7a32f5f01, with hosted Python 3.11/3.12/3.13 checks successful.
---
<!-- COMMENTS:END -->
