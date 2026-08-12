---
id: OOMPAH-1189
type: bug
status: Open
priority: 1
title: Use managed authenticated remote for native state-branch claims
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-12T21:09:00.853491Z'
updated_at: '2026-08-12T21:10:09.570098Z'
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
  creation_marker: scheduling-state-branch-canonical-auth-20260812
  request_fingerprint: a3aa7f1c53b8557fa4553c1a9f238cd5489828892b0581957135e622aa99fc99
oompah.lifecycle_revision: 1
---
## Summary

Triggered by: OOMPAH-1177

Live reproduction after resuming Trickle on merged main 00db66b58: every Open implementation task reaches dispatch admission, then exact run-ID claim persistence fails closed with StateBranchFetchError because git fetch origin oompah/state/proj-3e4e9214 resolves to git@gitlab-master.nvidia.com:12051 and public-key authentication fails. The managed Trickle project is configured for authenticated HTTPS and startup sync succeeds, but the native Markdown state-branch tracker still inherits or rewrites to the stale SSH transport. No provider starts, so all dispatchable Trickle work remains Open.

Implementation scope:
- Trace native state-branch tracker construction and remote selection across ProjectStore, tracker caching/provenance wrappers, OompahMdTracker, checkpoint queues, and project reconfiguration.
- Resolve state-branch fetch/push from the managed project canonical authenticated remote and credential material, never an ambient clone remote or global insteadOf rewrite that changes authority.
- Invalidate stale tracker/credential generations after project migration or service restart.
- Preserve fail-closed provider admission and bounded actionable errors when the canonical transport is unavailable.

Required tests:
- Configure a managed GitLab HTTPS project while the canonical clone or ambient Git config exposes a stale SSH origin/rewrite; prove state-branch fetch and push use authenticated HTTPS.
- Cover service restart and tracker-cache reconstruction after GitHub-to-GitLab migration.
- Prove failed canonical authentication starts zero provider/workspace instances and successful exact claim persistence starts once.
- Verify credentials are redacted from logs and other projects are isolated.

Acceptance criteria:
- Resumed Trickle tasks can durably transition Open to In Progress and launch agents using the managed GitLab credential path.
- No state-branch operation for Trickle attempts git@gitlab-master.nvidia.com.
- Exact claim generation remains committed and re-read before provider admission.
- Focused regression tests and the full Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 21:10
---
Direct operator implementation started on branch OOMPAH-1189 while the Oompah project remains paused. Trickle is temporarily paused after live fail-closed reproduction; no provider was admitted. The durable owner-claim request is queued under workflow job workflow-job-08d53f39e0dc4967a51a5aef0e3cb767, and this comment records the handoff while paused workflow execution cannot materialize it.
---
<!-- COMMENTS:END -->
