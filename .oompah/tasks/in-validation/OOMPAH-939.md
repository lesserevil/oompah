---
id: OOMPAH-939
type: task
status: In Validation
priority: null
title: Continue saturated durable workflow batches without full-sync delay
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T08:54:39.101794Z'
updated_at: '2026-08-09T09:44:42.281399Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-4827a2c0df9f
    project_id: proj-14849f1b
    task_id: OOMPAH-939
    digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
  - version: 1
    audit_id: audit-bd560d2bb335
    project_id: proj-14849f1b
    task_id: OOMPAH-939
    digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-4827a2c0df9f
    project_id: proj-14849f1b
    task_id: OOMPAH-939
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
    attempts:
    - version: 1
      attempt_id: attempt-70a86da90e2f
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
      created_at: '2026-08-09T09:44:34.011942+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T09:44:34.011942+00:00'
      branch_key: OOMPAH-939
      selected_ref: origin/OOMPAH-939
      selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-09T09:39:27.270044+00:00'
    selected_ref: origin/OOMPAH-939
    selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
    updated_at: '2026-08-09T09:44:34.011942+00:00'
  - version: 1
    audit_id: audit-bd560d2bb335
    project_id: proj-14849f1b
    task_id: OOMPAH-939
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-09T09:39:27.270044+00:00'
    selected_ref: origin/OOMPAH-939
    selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
  attempt_history:
  - version: 1
    attempt_id: attempt-70a86da90e2f
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d5681f0cb4429f02b6f02dbf0f61ad858ed770de5ef84b193888026dc6cd6dec
    created_at: '2026-08-09T09:44:34.011942+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T09:44:34.011942+00:00'
    branch_key: OOMPAH-939
    selected_ref: origin/OOMPAH-939
    selected_sha: b1fc26aa98edc4fdd53c2315906af7321d48a1eb
---
## Summary

Triggered by: OOMPAH-785\n\nProduction regression observed on 2026-08-09 while recovering the legacy Done backlog after OOMPAH-935: WorkflowRuntime._run_due processed exactly the configured 32-job batch cap, left current claimable Oompah jobs queued/due, and then remained idle until the independent 300-second FULL_SYNC safety net. The runtime transition observer wakes only for transition_applied; batches made entirely of retry/superseded/no-transition results emit no wake. _run_due reports processed but no saturation/continuation signal, so bounded work can be stranded for five minutes despite worker.accepting=true.\n\nImplementation scope: preserve bounded batches and project fairness; make the durable runtime report when a batch reaches its cap and may have more eligible work; after the current durable tick publishes its report/metrics, request exactly one coalesced REFRESH_REQUESTED continuation through the production orchestrator event loop. Do not recurse inside the tick and do not spin from raw queued counts because those include paused projects, future retries, and ineligible actions. Suppress continuation during drain/shutdown and expose bounded observability such as batch_saturated/continuation_requested. Relevant files: oompah/workflow_runtime.py, oompah/orchestrator.py, scheduler/runtime tests.\n\nRequired tests: seed more than one batch of current claimable jobs whose handlers complete/retry/supersede without transition events; prove the first production tick processes the cap and posts one coalesced continuation; prove the next tick immediately handles the suffix without FULL_SYNC; prove paused-project, future-retry, and ineligible rows do not cause a loop; preserve multi-project fairness and shutdown/drain fencing.\n\nAcceptance: current eligible work never waits for the five-minute safety net solely because the prior batch hit its cap; each continuation remains bounded/coalesced and non-recursive; no busy loop occurs for non-claimable rows; focused and complete branch gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 08:55
---
Accepted as the live batch-continuation regression found during OOMPAH-935 rollout.
---
author: oompah
created: 2026-08-09 09:03
---
Direct-owner fix is committed and pushed at 2bac503b1 on protected-main PR 751. The runtime now reports cap saturation and the production orchestrator posts one coalesced, shutdown-fenced continuation; future-due/ineligible rows do not rearm. Verification: 109 adjacent tests passed plus targeted lint/diff checks. Hosted complete gates are starting.
---
author: oompah
created: 2026-08-09 09:03
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-939`
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
created: 2026-08-09 09:19
---
Published reviewed head b1fc26aa on PR #751. The continuation path now preserves durable cross-project fairness with an explicit runnable-project allowlist; the production dispatch-loop test proves an exact-cap batch posts and consumes one coalesced refresh without waiting for the 5-minute full sync. Focused/adjacent result: 221 passed; targeted undefined-name lint passed. Independent re-review approved; hosted 3.11/3.12/3.13 gates are running with auto-merge enabled.
---
author: oompah
created: 2026-08-09 09:39
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 09:44
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 09:44
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
