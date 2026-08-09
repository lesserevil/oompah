---
id: OOMPAH-916
type: task
status: Done
priority: null
title: Unset removed .env configuration across graceful exec restarts
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T14:27:25.215337Z'
updated_at: '2026-08-09T21:43:01.527452Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-199b73c4cd62
    project_id: proj-14849f1b
    task_id: OOMPAH-916
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 61240cf79492af987768c7d31b30b42f10748f29e87fc75c2a908fb9d4762590
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope is contained in that validated head; owner override avoids fabricating
      a separate branch/integration generation.
    created_at: '2026-08-08T16:26:40.953319+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-916
    target_state: Done
    evidence_fingerprint: 61240cf79492af987768c7d31b30b42f10748f29e87fc75c2a908fb9d4762590
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:26:49.769363+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Owner-reviewed terminal implementation is retained. The Done child is
      durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
      exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
    marked_at: '2026-08-09T21:43:00.054989+00:00'
    updated_at: '2026-08-09T21:43:00.054989+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Owner-reviewed terminal implementation is retained. The Done child is
        durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
        exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
      recorded_at: '2026-08-09T21:43:00.054989+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

During workflow rollout, removing the four workflow-domain mode keys from .env and running make graceful did not disable shadow mode. The service uses os.execv for graceful restart, so the child inherits the old process environment; _load_startup_env calls load_dotenv(..., override=True), which updates present keys but never removes keys that disappeared from the authoritative .env file. The restarted process therefore retained stale rollout configuration until explicit off values were added.\n\nImplementation scope:\n- Synchronize environment keys managed by the authoritative dotenv file across in-process exec restarts, removing formerly file-managed keys that are absent after reload.\n- Preserve unrelated externally supplied environment variables and define fail-closed behavior for missing or unreadable dotenv files.\n- Use one shared restart environment path for Uvicorn and Granian exec flows.\n- Document the operator-visible semantics if needed.\n\nRequired tests:\n- Load a dotenv key, remove it from the file, reload in the same process, and prove it is removed.\n- Prove changed values override inherited values, unrelated external keys remain, and missing/unreadable files do not erase unmanaged configuration.\n- Cover both server restart backends or their common exec helper.\n\nAcceptance criteria:\n- Removing an OOMPAH_* key from .env takes effect after make graceful without requiring an explicit replacement value.\n- Graceful restart cannot retain stale rollout modes from a previous process image.\n- Focused config and lifecycle restart tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 14:37
---
Direct owner implementation completed locally on the systemic composition branch. Graceful Uvicorn and Granian exec restarts now reconcile the authoritative dotenv before exec, remove only formerly file-managed keys that disappeared, preserve unrelated variables, and keep last-known-good values for missing/unreadable files. 153 focused tests pass. Status remains Backlog until transition recovery is deployed.
---
author: oompah
created: 2026-08-08 16:26
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope is contained in that validated head; owner override avoids fabricating a separate branch/integration generation.
---
<!-- COMMENTS:END -->
