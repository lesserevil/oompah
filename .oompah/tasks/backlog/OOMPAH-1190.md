---
id: OOMPAH-1190
type: task
status: Backlog
priority: null
title: Sanitize legacy username-only userinfo in managed canonical remotes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-12T22:25:20.676127Z'
updated_at: '2026-08-12T22:25:20.676127Z'
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
---
## Summary

Bug found while deploying OOMPAH-1189. A managed project may retain a legacy HTTPS clone URL with username-only userinfo, such as https://actor@github.example/org/repo.git, while its secret token is stored separately. OOMPAH-1189 rejected all HTTP(S) userinfo during tracker construction, causing the whole service to fail startup when any paused project had this legacy representation. Scope: accept username-only legacy clone URLs, derive a credential-free canonical transport URL before any Git argv construction, continue rejecting password-bearing URLs without echoing secrets, preserve ephemeral GIT_ASKPASS token delivery, and ensure one paused legacy project cannot crash multi-project service startup. Relevant code: oompah/oompah_md_tracker.py and managed state-branch tracker construction. Tests must cover username removal (including a port), password rejection/redaction, and successful tracker construction alongside mixed project configurations. Acceptance: service starts with the current OVA/Coroot legacy URLs, Git argv contains no userinfo/token, focused canonical-remote tests and the complete branch gate pass, and the fix is merged into main.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

