---
id: OOMPAH-891
type: task
status: In Progress
priority: null
title: Isolate epic-rebase workers from all remote-write credentials
parent: OOMPAH-879
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T13:30:11.042474Z'
updated_at: '2026-08-07T14:29:47.704530Z'
work_branch: epic-OOMPAH-879--task-OOMPAH-891
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
  evidence: 'git worktree add failed: fatal: invalid reference: origin/epic-OOMPAH-763--task-OOMPAH-879'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 2
  retry_after: '2026-08-07T13:55:10.535986+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 745c3bcf-b097-4cf0-9927-c6ad9b2476f3
oompah.work_branch: epic-OOMPAH-879--task-OOMPAH-891
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-879--task-OOMPAH-891
  base_branch: epic-OOMPAH-763--task-OOMPAH-879
  base_sha: 41b1477682c6460a1bb55356ac44c799c9fa783a
  updated_at: '2026-08-07T13:52:51.862140+00:00'
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
author: oompah
created: 2026-08-07 13:45
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 13:46
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 37s
---
author: oompah
created: 2026-08-07 13:52
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 13:53
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 27s
---
author: oompah
created: 2026-08-07 13:54
---
Root renewed direct-owner fence after implementation agent completion so the server cannot dispatch this security-sensitive task while independent review blockers are repaired. Current unbrokered validation is withdrawn; brokered review awaits a complete filesystem/network capability boundary.
---
author: oompah
created: 2026-08-07 14:01
---
Implemented the reviewed capability-boundary redesign on OOMPAH-879: direct rebase shells now run in Bubblewrap with unshared network/user/pid namespaces, no provider-runtime or task-handoff mount, private HOME/TMP, linked-worktree Git metadata, and sanitized local Git config. Legacy CLI and Codex subscription CLI are fail-closed for isolated rebase work; API/bridged ACP tool calls retain server-mediated task operations. Added regression coverage; static compilation and diff checks pass. Focused tests remain queued behind the active validation broker and independent re-review is requested.
---
author: oompah
created: 2026-08-07 14:03
---
Follow-up: isolated shared-epic rebase dispatch now proactively selects a supported ACP bridged profile instead of a legacy CLI profile, and skips Codex subscription ACP because its provider transport and native shell cannot be separated. This prevents repeated unsafe/unusable CLI retries.
---
author: oompah
created: 2026-08-07 14:07
---
Final isolation hardening: OpenCode is now fail-closed for every isolated shared-epic rebase mode before any auth bootstrap or subprocess launch; the rebase profile selector excludes it, alongside Codex subscription CLI. Static compilation and diff checks pass. Broker remains owned by OOMPAH-877 (with OOMPAH-846 queued), so focused tests remain correctly deferred.
---
author: oompah
created: 2026-08-07 14:09
---
Selector correction: an initially matched ACP profile is no longer assumed safe. Shared-epic rebase dispatch reroutes both OpenCode and Codex-subscription ACP profiles to a proven bridged callback profile; OpenCode runtime remains fail-closed before auth bootstrap or Popen. Static checks pass; focused tests still await broker capacity.
---
author: oompah
created: 2026-08-07 14:20
---
Acceptance review found one remaining launch-path blocker after the selector hardening: the final focus-resolved provider could still be missing/empty/unknown and  would default it to Claude before credential bootstrap. Required fix is now in progress: isolated epic-rebase work must revalidate the final resolved provider and fail closed before defaults/auth; only explicit Claude or explicit non-subscription Codex is admissible. Dispatch-level regressions will cover missing, empty, unknown, and unsafe focus overrides. The sandbox/remote-shell review found no other escape route.
---
author: oompah
created: 2026-08-07 14:20
---
Correction: the affected launch method is _run_acp_worker. The previous comment's shell formatting omitted that method name; the required fix and scope are unchanged.
---
author: oompah
created: 2026-08-07 14:29
---
Independent acceptance review now passes. Both ACP and API launch paths enforce final focus-resolved provider admission before backend defaults, credential snapshots, reservations, staging, signatures, or session construction. The five-case parity matrix covers absent provider, empty or deleted provider_id, and empty or deleted model_role. Static diff checks are clean. Brokered focused validation is being queued behind the definitive shared-epic gate; no commit or push yet.
---
<!-- COMMENTS:END -->
