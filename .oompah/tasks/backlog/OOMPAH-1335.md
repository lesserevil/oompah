---
id: OOMPAH-1335
type: task
status: Backlog
priority: null
title: Remove stale local Git URL rewrites during managed-clone credential sanitation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T21:56:39.839941Z'
updated_at: '2026-08-24T21:56:39.839941Z'
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
  creation_marker: ac1c7df9-1451-4dc9-bef5-89f3a580a2cd
  request_fingerprint: 480170a98d186409d1ea6f9a920a742b09780738918f101c6c54c6db917c2491
---
## Summary

A managed native Markdown project (trickle, proj-3e4e9214) had canonical repo_url=https://gitlab-master.nvidia.com/omniverse/devplat/trickle.git and remote.origin.url correctly normalized to HTTPS, but its managed clone .git/config retained a local url.git@gitlab-master.nvidia.com:.insteadof=https://gitlab-master.nvidia.com/ rewrite. Every state-branch fetch was silently rewritten back to SSH, which failed with publickey/incorrect-port (12051) and made `oompah task create --project proj-3e4e9214` return HTTP 500. Existing sanitize_managed_clone_credentials removes remote userinfo, credential helpers, and http.*.extraheader and normalizes origin, but does not remove local url.*.insteadof rewrite routes. Implement fail-closed sanitation of managed-clone/worktree-local url.*.insteadof entries that rewrite the canonical project repo URL/host to another transport or credential-bearing route, without altering unrelated global config or unrelated remotes. Ensure clone/adopt/migrate/self-heal/direct-maintenance call sites apply it. Regression: local insteadOf rewrites HTTPS canonical GitLab URL to SSH; sanitation removes it; git remote get-url and state-branch fetch use canonical HTTPS; task creation succeeds. Preserve benign unrelated url rewrites. Acceptance: canonical project repo_url cannot be overridden by stale local insteadOf config, and no agent gains a direct push/credential route.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

