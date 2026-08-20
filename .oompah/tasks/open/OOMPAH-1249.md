---
id: OOMPAH-1249
type: task
status: Open
priority: null
title: Sanitize credential routes from managed clone Git config
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T16:07:17.780951Z'
updated_at: '2026-08-20T23:02:56.501388Z'
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
  creation_marker: 38414c00-1ce0-4772-8ca6-34b094cc432f
  request_fingerprint: 161c9ff76929a7deb62fc461fd2af12e3940f907f457dfd38ca6015cd1b8f517
oompah.lifecycle_revision: 1
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ac16839b98a35e44ffa203782336151a9e5ff81d3f799e101eabcba48ecc8de7
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 63068b92109bc667029d8b55ec492d11efb527fb9d7393025dc65fa2475f5b0b:56509
  claim_owner: b0161d82-55d7-4b08-9b68-ee54b4e13c9c
  claimed_at: '2026-08-20T23:02:49.088670+00:00'
  claim_expires_at: '2026-08-20T23:32:49.088670+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 23da71bd-db8f-4275-ad4b-63141734413c
---
## Summary

Live scheduling bug reproduced on TRICKLE-141 after the Trickle GitLab migration: the canonical project record stores a credential-free repo_url and server-owned access token, but /home/shedwards/.oompah/repos/trickle/.git/config retained HTTP remote userinfo plus local credential.helper entries. Direct epic-maintenance dispatch correctly refuses any workspace inheriting such a route before its no-network sanitized Bubblewrap executor starts, so every scoped rebase publisher exits before a turn. Scope: whenever a managed clone is created, adopted, migrated, self-healed, or prepared for direct maintenance, normalize every managed remote to the credential-free canonical Project.repo_url; remove worktree/common local credential.helper and http.*.extraheader routes from the managed clone after server-owned credential transport is established; prove ordinary server fetch/push still use ProjectStore's isolated git_credential_environment; fail closed if sanitation cannot be proven. Required tests: GitLab migration with legacy userinfo/helper config; existing linked worktrees; canonical SSH/HTTPS remotes; server-owned fetch/push authentication; direct-rebase preflight then passes while restricted_rebase_command still exposes no network, remotes, helpers, operator home, or task token; restart/self-heal idempotency. Acceptance: a clean canonical project configuration cannot leave direct rebase helpers permanently undispatchable due solely to stale managed-clone credentials, and no agent gains a direct push route.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 07:47
---
Claimed for direct implementation in /home/shedwards/src/oompah-1249 on branch OOMPAH-1249 from origin/main 948ef6f2. Oompah remains paused. Implementing managed-clone credential-route sanitation with fail-closed proof, linked-worktree coverage, isolated server-owned transport preservation, and restricted rebase preflight acceptance.
---
<!-- COMMENTS:END -->
