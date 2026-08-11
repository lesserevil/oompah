---
id: OOMPAH-1127
type: bug
status: Backlog
priority: 1
title: Fence stale checkpoint writers during tracker forge and credential cutovers
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T22:38:37.996985Z'
updated_at: '2026-08-11T22:38:37.996985Z'
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

