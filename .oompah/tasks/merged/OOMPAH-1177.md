---
id: OOMPAH-1177
type: bug
status: Merged
priority: 1
title: Fail closed when dispatch claim persistence does not converge
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- bug
- human-only
assignee: null
created_at: '2026-08-12T15:54:19.893858Z'
updated_at: '2026-08-12T20:02:20.048398Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: dispatch-claim-persistence-open-live-agent-20260812
  request_fingerprint: 17e5f5425300a525dfb0db14b1eca163f241a7ff4a86ffcd5c058ae92fee4b10
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-b8c5348bc26f
    project_id: proj-14849f1b
    task_id: OOMPAH-1177
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b1d2387a807434655673ed826591407984e8bbbd1ed96bf5541b9521680fec50
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Direct-owner completion verified in merged PR #837 at 00db66b58: provider
      admission now fails closed unless exact durable claim evidence converges; full
      Python 3.11/3.12/3.13 CI passed.'
    created_at: '2026-08-12T20:01:58.553483+00:00'
    selected_ref: origin/OOMPAH-1177
    selected_sha: 6ce5745fa2a73f182521e01855f5b36e351abfe5
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1177
    target_state: Merged
    evidence_fingerprint: b1d2387a807434655673ed826591407984e8bbbd1ed96bf5541b9521680fec50
    workflow_revision: null
    selected_ref: origin/OOMPAH-1177
    selected_sha: 6ce5745fa2a73f182521e01855f5b36e351abfe5
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-12T20:02:09.062104+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

Live reproduction on 2026-08-12 after service restart: Trickle implementation providers were launched for TRICKLE-118, TRICKLE-119, TRICKLE-121, TRICKLE-132, TRICKLE-134, TRICKLE-135, TRICKLE-136, and TRICKLE-137 while every canonical native Markdown task remained Open. The /api/v1/state running overlay reported each run as In Progress, but work_decision.status and oompah task view remained Open. Earlier pre-provider attempts correctly failed closed with contributor_evidence_unavailable / StateBranchFetchError; subsequent retry paths proceeded to a live provider without a durable Open -> In Progress transition. Logs also recorded state-branch fetch attempts through an unauthorized SSH URL even though the managed Trickle origin is configured as authenticated HTTPS. Exact live-generation checks suppressed duplicate dispatch only in memory, so restart could lose that protection and redispatch the same work.

Implementation scope: make every implementation launch path, including ordinary scheduling, durable workflow retries, recovery retries, and provider fallback, require a successfully committed and re-read durable claim/status generation before provider or workspace authority starts. Centralize the pre-provider admission fence so no retry path can bypass it. Resolve state-branch transport from the managed project canonical authenticated remote rather than a stale or rewritten SSH URL, and surface a bounded actionable transport error when persistence is unavailable. If persistence fails or the post-write read does not prove the exact run ID, task generation, branch/head, project, and In Progress status, retire the runtime and keep/recover the task as dispatchable without a live provider. Reconcile any live-provider/Open mismatch deterministically: either durably adopt the exact live generation or revoke it without creating duplicate work. Ensure the dashboard and work-decision projection derive status consistently from committed tracker evidence, with explicit degraded-state telemetry rather than an invented overlay-only In Progress state.

Relevant code/context: oompah/orchestrator.py dispatch and retry launch paths, native Markdown/state-branch tracker mutation and remote resolution, workflow_runtime.py/workflow_worker.py implementation-start effects, task transition service, /api/v1/state running projection, and restart reconciliation. Preserve pause/quiesce fences, exact-generation ABA protection, provider/model contributor evidence, and project isolation.

Required tests: reproduce StateBranchFetchError before claim for each dispatch/retry entry point and prove zero provider/workspace starts; simulate write success followed by stale Open re-read and prove launch aborts; cover provider fallback after the first candidate persistence failure; cover authenticated HTTPS canonical remote versus stale SSH transport selection; race task/operator changes with claim commit; restart after a live-provider/Open mismatch and prove no duplicate dispatch; exercise deterministic adopt-or-revoke repair; verify state API/Kanban and work decisions agree; verify successful exact claims still launch once. Include focused regression tests and the full Makefile gate.

Acceptance criteria: no provider can remain active for a task whose exact durable generation is still Open; claim persistence failures fail closed across all scheduling paths; restart cannot redispatch the eight-task failure pattern; remote/auth selection is deterministic and uses the managed project credential path; mismatches are self-healed or shown as actionable degraded state; no in-memory-only claim is presented as canonical In Progress; all relevant tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 17:48
---
Direct implementation committed and pushed on branch OOMPAH-1177 at exact head 6ce5745fa2a73f182521e01855f5b36e351abfe5. Dispatch now fails closed when the shared run-ID claim cannot be persisted/read, when post-status evidence cannot be refreshed, when the durable status remains Open, or when a replacement assignment wins. Compensation restores the prior dispatchable state and no worker/provider is constructed. Regression coverage replaces the former explicit fail-open test and adds stale-Open plus assignment-ABA cases. Verification: 105 broad dispatch/retry tests passed; focused exact suite 88 passed; terminal mutation scan 21/21; diff and secret hooks clean. Full branch gate will run with the combined review-ready program.
---
author: oompah
created: 2026-08-12 19:22
---
Combined with the transactional batch update work on PR #837 at exact head aaa3ec17a0b98e280bffa1e71d3dd904f5060d41. Combined focused regression coverage passes 911 tests; the authoritative full Makefile gate and GitHub 3.11/3.12/3.13 checks are running before merge.
---
author: oompah
created: 2026-08-12 20:02
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Direct-owner completion verified in merged PR #837 at 00db66b58: provider admission now fails closed unless exact durable claim evidence converges; full Python 3.11/3.12/3.13 CI passed.
---
author: oompah
created: 2026-08-12 20:02
---
Completed by merged PR #837 (00db66b58). Every covered dispatch path now requires a committed and re-read exact claim before provider admission, with safe compensation on mismatch.
---
<!-- COMMENTS:END -->
