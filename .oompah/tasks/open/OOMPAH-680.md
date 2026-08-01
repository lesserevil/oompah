---
id: OOMPAH-680
type: task
status: Open
priority: null
title: Use project forge credentials for all managed Git network operations
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T17:31:44.735248Z'
updated_at: '2026-08-01T17:42:04.849683Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 26e4c605cd4b174aae95ca9bca020dcfc7f0aa3165acc75318ef4df395d353b8
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 5b193f8b-ca4f-4260-8bb9-8b244036d0e4
  claim_owner: cdcf766d-728b-41c9-bcaa-eb3b220f310c
  claimed_at: '2026-08-01T17:41:49.501664+00:00'
  claim_expires_at: '2026-08-01T18:11:49.501664+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 8904b37e-d4f9-4212-ac47-503356b91b86
---
## Summary

Live NodeVirt failure on 2026-08-01: the GitLab project has a valid configured access token and forge API calls succeed, but ordinary Oompah-managed git pushes run without forge credentials. Publishing epic-NODEVIRT-* and checkpointing oompah/state/proj-bbba976d failed with `fatal: could not read Username for https://gitlab-master.nvidia.com`, sending NODEVIRT-7 through NODEVIRT-21 to Needs Human before duplicate screening began. State-branch migration already has an ephemeral, redacted GIT_ASKPASS mechanism in oompah/git_credentials.py, but normal ProjectStore, worktree/epic publication, integration, branch cleanup, and oompah_md state-branch checkpoint Git commands do not consistently use it. Implementation scope: route every managed network Git operation through a shared forge-aware credential environment derived from the target Project access_token; cover clone/fetch/ls-remote/push/delete/verification paths in oompah/projects.py, oompah/oompah_md_tracker.py, integration/review helpers, and any other managed Git callers. Never place tokens in argv, remote URLs, persisted Git config, stdout/stderr, exceptions, or logs; preserve noninteractive failure and redact credential-bearing output. Required tests: private GitLab-style remotes accept the configured project token for epic publication and state checkpoints; missing/invalid tokens fail with forge-neutral actionable diagnostics and no partial state; GitHub behavior remains unchanged; concurrent projects cannot receive each other credentials; worktrees inherit the safe behavior; secret scans pass. Acceptance: a configured GitLab project can dispatch a new epic child, publish its epic/task branches, checkpoint native task state, and clean branches without operator Git credential configuration, while tokens remain absent from process listings, config, URLs, and logs.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 17:42
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 17:42
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
