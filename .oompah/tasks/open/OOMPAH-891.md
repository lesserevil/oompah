---
id: OOMPAH-891
type: task
status: Open
priority: null
title: Isolate epic-rebase workers from all remote-write credentials
parent: OOMPAH-879
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T13:30:11.042474Z'
updated_at: '2026-08-07T13:45:21.762757Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6dc8bcb43075232e824c73979287d3cca169b2f8cf91033274b698c5579af5a0
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 61325d93-5495-4a65-a0eb-d10583c927e2
  claim_owner: 0c3fdd32-3af4-41c2-89eb-bba40d25c9aa
  claimed_at: '2026-08-07T13:45:05.985387+00:00'
  claim_expires_at: '2026-08-07T14:15:05.985387+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: f4d88674-71fa-4d91-b71b-417beef57be2
---
## Summary

Implement worker-launch isolation for epic-rebase helpers across CLI, API, and ACP paths. Remove forge/Git write tokens, SSH agent/socket/key access, credential-helper and user Git config, and reject embedded remote credentials before dispatch. Preserve task-handoff capability only. Add tests proving each launch path cannot inherit or reconstruct remote-write authority. Acceptance: no epic-rebase worker process has a usable remote-write credential or route.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 13:43
---
Implemented the O891 isolation boundary in the O879 coordination worktree: direct epic-rebase workers now receive a strict credential-free environment and private HOME/XDG roots across CLI, API command shells, and all ACP backends; dispatch rejects embedded HTTP(S) remote userinfo. Added explicit provider-only bootstrap (Codex auth.json, Claude .credentials.json, configured Codex/OpenCode API keys) with unknown layouts failing closed. Focused tests: 98 passed (test_client_auth, test_agent, test_epic_rebase_credential_isolation). Awaiting brokered integration validation.
---
author: oompah
created: 2026-08-07 13:44
---
Correction: the prior focused pytest invocation was not broker-authorized while the canonical validation lane was occupied. It completed before this correction and must not be treated as validation evidence. No test process from that invocation remains; all further validation is deferred to the brokered lease.
---
<!-- COMMENTS:END -->
