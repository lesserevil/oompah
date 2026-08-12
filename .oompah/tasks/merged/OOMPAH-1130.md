---
id: OOMPAH-1130
type: bug
status: Merged
priority: 1
title: Prevent exhausted terminal-audit recovery from starving project workflow publication
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-11T22:58:51.766509Z'
updated_at: '2026-08-12T20:01:39.448860Z'
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
  creation_marker: incident-20260811-trickle-exhausted-audit-publication-starvation
  request_fingerprint: a23088f523c0d76bd968ffb741359d6773e64e242e6d9e82e2bd933678778eb0
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-2fc76209be6f
    project_id: proj-14849f1b
    task_id: OOMPAH-1130
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b6e3b04ce17604dc5f7f3c5d7c1dc358dd00fc904d3cc24a2ee01b2c5f0905e0
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Direct-owner completion verified in merged PR #836 at a6a983171: exhausted-audit
      recovery no longer churns terminal authority or starves unrelated workflow publication;
      full CI passed.'
    created_at: '2026-08-12T20:01:33.311807+00:00'
    selected_ref: origin/OOMPAH-1130
    selected_sha: b8a77e4d094a94ebb1b814606c15ac6aa4e94b1f
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

Triggered by: OOMPAH-1127

After the Trickle GitHub-to-GitLab migration, TRICKLE-99, TRICKLE-114, and TRICKLE-115 have exhausted terminal audits. Recovery repeatedly fails with "current task evidence could not be refreshed" while the terminal-audit disposition revision changes. Every durable workflow reconciliation is then superseded with "terminal-audit disposition changed before publication". As a result, work-decision requests return 503 and none of 16 unrelated Open Trickle tasks can dispatch. A normal service restart does not converge the state.

Implementation scope:
- Audit exhausted-audit recovery in oompah/orchestrator.py and terminal-authority publication fencing in oompah/workflow_runtime.py.
- Ensure a failed/no-op attempt to route an exhausted audit does not advance terminal authority or continuously supersede workflow publication.
- Isolate an unrecoverable audit task so unrelated task decisions for the same project can still be published safely.
- Make native-tracker evidence refresh after a forge cutover either succeed with the current project binding or produce one bounded actionable recovery state.
- Apply retry backoff and stable diagnostics rather than a five-second mutation/publication loop.

Required tests:
- Reproduce an exhausted terminal audit whose evidence refresh fails on every attempt and assert terminal authority remains stable after the first recorded failure.
- Verify workflow publication and implementation admission continue for unrelated Open tasks in the same project.
- Verify the affected audit task is retained in an actionable safe state and cannot be incorrectly terminalized.
- Cover restart reconstruction and project forge/credential cutover bindings.

Acceptance criteria:
- One unrecoverable terminal audit cannot starve project-wide workflow publication.
- Work-decision endpoints remain available for unaffected tasks.
- Retries are bounded/backed off, observable, and do not create a tight log loop.
- The three affected Trickle audits can converge or be routed for operator action without manual database edits.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 01:38
---
Direct operator ownership is active on branch OOMPAH-1130. The workflow-authorized Open → In Progress transition is currently unavailable because OOMPAH-1130 prevents publication of the required generation; this comment and branch are the durable ownership handoff until that blocker is repaired.
---
author: oompah
created: 2026-08-12 01:52
---
Implemented and deployed commit 5503ae15e on PR #836. Regression coverage: 338 terminal-transition/recovery tests pass. Live verification: Trickle workflow snapshot generation 5225 published successfully, three workflow worker lanes became active, and stale terminal-audit transport failures fell from 3 to 0. Oompah remains paused; only Trickle is resumed. Awaiting protected-branch CI/merge while I continue the remaining directly owned blockers.
---
<!-- COMMENTS:END -->
