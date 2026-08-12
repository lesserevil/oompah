---
id: OOMPAH-1127
type: bug
status: Open
priority: 1
title: Fence stale checkpoint writers during tracker forge and credential cutovers
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T22:38:37.996985Z'
updated_at: '2026-08-12T16:00:29.437282Z'
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
  creation_marker: incident-20260811-trickle-forge-cutover-checkpoint-fencing
  request_fingerprint: 3de38f978420eee0995ae789c6acad1d54859cfec2a8f4923b625abb518eb916
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 79300d84bb5b4a8196156d4d2929ad553e2609700b4cb5eb57f9b0efacff2812
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4cd92af1d62e456e292772c72f60fbbe05fa49f92807748f835e9fc697ab0f18:11840
  claim_owner: 02fd371b-4f1d-4e9b-a422-f3effd90464e
  claimed_at: '2026-08-12T15:59:36.414669+00:00'
  claim_expires_at: '2026-08-12T16:29:36.414669+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8d5b7f74-148e-4ed7-be48-1887128d5cfb
oompah.work_contributors:
  runs:
  - run_id: 970c2fe725bc48c380ce746f7d8db174--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1127
    source_sha: null
    completed_at: ''
  - run_id: 970c2fe725bc48c380ce746f7d8db174--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1127
    source_sha: null
    completed_at: ''
---
## Summary

Triggered by: OOMPAH-1098

A live OompahMdTracker checkpoint queue retained obsolete GitHub push authority while the Trickle project repository, forge, and credentials were migrated to GitLab. Subsequent state commits were created locally but repeated checkpoint pushes failed with HTTP 403 until an operator pushed the exact state head with the current GitLab credential.

Implementation scope:
- Audit project reconfiguration and tracker-cache invalidation in oompah/projects.py, the project update routes in oompah/server.py, and checkpoint lifecycle/flush behavior in oompah/oompah_md_tracker.py.
- Make repository/forge/credential cutover atomic with respect to live checkpoint writers: drain pending state safely or fence the old writer generation before publishing the new configuration.
- Ensure a stale tracker or queued callback cannot push using superseded remote or credential state after the cutover commits.
- Preserve pending task-state commits and provide an actionable diagnostic if the cutover cannot safely complete.

Required tests:
- Reproduce a live checkpoint queue created with old credentials, change a project from a GitHub remote to a GitLab remote with new credentials, and prove no post-cutover push uses the old authority.
- Verify pending commits are preserved and flushed exactly once with the new authority.
- Cover ordinary same-forge credential rotation and configuration updates without pending work.

Acceptance criteria:
- No stale checkpoint actor can write after its project configuration generation is superseded.
- A successful cutover leaves local and remote state heads equal without manual recovery.
- Failure is bounded and surfaced once with remediation evidence rather than retried indefinitely.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 22:58
---
Post-cutover live verification found an additional project-wide deadlock: exhausted audits for TRICKLE-99, TRICKLE-114, and TRICKLE-115 cannot refresh evidence and repeatedly supersede durable workflow publication, blocking 16 unrelated Open tasks. This distinct recovery/publication starvation defect is tracked by OOMPAH-1130. A normal service restart reproduced the condition.
---
author: oompah
created: 2026-08-12 01:38
---
Direct operator ownership is active on branch OOMPAH-1130. The workflow-authorized Open → In Progress transition is currently unavailable because OOMPAH-1130 prevents publication of the required generation; this comment and branch are the durable ownership handoff until that blocker is repaired.
---
author: oompah
created: 2026-08-12 15:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-12 16:00
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 39s
---
<!-- COMMENTS:END -->
