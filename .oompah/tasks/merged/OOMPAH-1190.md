---
id: OOMPAH-1190
type: task
status: Merged
priority: null
title: Sanitize legacy username-only userinfo in managed canonical remotes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-12T22:25:20.676127Z'
updated_at: '2026-08-14T03:40:56.622465Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: f01ec846-9ac5-473d-aaae-428603c060fd
  request_fingerprint: 2e8962baf19d5e1b07cb1196d198039e040e6b841ecc623363ed710f3e25669b
oompah.lifecycle_revision: 3
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-13be62762bd9
    project_id: proj-14849f1b
    task_id: OOMPAH-1190
    digest: 3b276b96baece8ebefb59526ee4b021278b859dd5820df5e8a6a47d286b89e5d
  - version: 1
    audit_id: audit-3a159708a3be
    project_id: proj-14849f1b
    task_id: OOMPAH-1190
    digest: 3b276b96baece8ebefb59526ee4b021278b859dd5820df5e8a6a47d286b89e5d
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7a3966cb8d0a
    project_id: proj-14849f1b
    task_id: OOMPAH-1190
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3b276b96baece8ebefb59526ee4b021278b859dd5820df5e8a6a47d286b89e5d
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner terminal closure while Oompah scheduling remains intentionally
      paused: PR 839 head ad14380b merged as 28938503; all Python 3.11, 3.12, and
      3.13 CI jobs passed; the merge is included in deployed main 948ef6f; queued
      terminal audits have zero attempts and no recorded error or unresolved review
      blocker.'
    created_at: '2026-08-14T03:40:42.387259+00:00'
    selected_ref: origin/OOMPAH-1190
    selected_sha: ad14380b0004fc42fe0e4e5d9f3e8f57cb12990d
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1190
    target_state: Merged
    evidence_fingerprint: 3b276b96baece8ebefb59526ee4b021278b859dd5820df5e8a6a47d286b89e5d
    workflow_revision: null
    selected_ref: origin/OOMPAH-1190
    selected_sha: ad14380b0004fc42fe0e4e5d9f3e8f57cb12990d
    landing_revision: null
    audit_ids:
    - audit-13be62762bd9
    - audit-3a159708a3be
    kind: override
    applied: true
    retired_at: '2026-08-14T03:40:50.454563+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-13be62762bd9
    project_id: proj-14849f1b
    task_id: OOMPAH-1190
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3b276b96baece8ebefb59526ee4b021278b859dd5820df5e8a6a47d286b89e5d
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-12T22:37:38.654914+00:00'
    eligible_at: '2026-08-12T22:37:38.654914+00:00'
    selected_ref: origin/OOMPAH-1190
    selected_sha: ad14380b0004fc42fe0e4e5d9f3e8f57cb12990d
    updated_at: '2026-08-14T03:40:50.454517+00:00'
  - version: 1
    audit_id: audit-3a159708a3be
    project_id: proj-14849f1b
    task_id: OOMPAH-1190
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3b276b96baece8ebefb59526ee4b021278b859dd5820df5e8a6a47d286b89e5d
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-12T22:37:38.654914+00:00'
    prerequisite_audit_id: audit-13be62762bd9
    selected_ref: origin/OOMPAH-1190
    selected_sha: ad14380b0004fc42fe0e4e5d9f3e8f57cb12990d
    updated_at: '2026-08-14T03:40:50.454545+00:00'
  attempt_history: []
---
## Summary

Bug found while deploying OOMPAH-1189. A managed project may retain a legacy HTTPS clone URL with username-only userinfo, such as https://actor@github.example/org/repo.git, while its secret token is stored separately. OOMPAH-1189 rejected all HTTP(S) userinfo during tracker construction, causing the whole service to fail startup when any paused project had this legacy representation. Scope: accept username-only legacy clone URLs, derive a credential-free canonical transport URL before any Git argv construction, continue rejecting password-bearing URLs without echoing secrets, preserve ephemeral GIT_ASKPASS token delivery, and ensure one paused legacy project cannot crash multi-project service startup. Relevant code: oompah/oompah_md_tracker.py and managed state-branch tracker construction. Tests must cover username removal (including a port), password rejection/redaction, and successful tracker construction alongside mixed project configurations. Acceptance: service starts with the current OVA/Coroot legacy URLs, Git argv contains no userinfo/token, focused canonical-remote tests and the complete branch gate pass, and the fix is merged into main.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 22:25
---
Direct owner recovery implementation is committed and pushed on hotfix/canonical-remote-userinfo at 5900dd8d. Focused canonical-remote tests pass (3 passed). The recovery build started successfully at this revision; all projects remain paused pending merge and final deployment.
---
author: oompah
created: 2026-08-12 22:28
---
Expanded regression coverage now proves orchestrator tracker construction succeeds for a state-branch project with a legacy username-only URL. Focused result: 4 passed. Pushed ad14380b and opened PR #839 with auto-merge armed.
---
author: oompah
created: 2026-08-12 22:37
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 03:40
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Project-owner terminal closure while Oompah scheduling remains intentionally paused: PR 839 head ad14380b merged as 28938503; all Python 3.11, 3.12, and 3.13 CI jobs passed; the merge is included in deployed main 948ef6f; queued terminal audits have zero attempts and no recorded error or unresolved review blocker.
---
author: oompah
created: 2026-08-14 03:40
---
Merged and deployed through PR 839; owner-verified terminal evidence replaces the intentionally unrun paused-project auditor.
---
<!-- COMMENTS:END -->
