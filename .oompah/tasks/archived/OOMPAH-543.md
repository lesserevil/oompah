---
id: OOMPAH-543
type: bug
status: Archived
priority: 1
title: Support removing task dependencies through the CLI and API
parent: null
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T14:38:32.101999Z'
updated_at: '2026-08-05T16:34:21.740139Z'
work_branch: OOMPAH-543
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/577
review_number: '577'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/577
oompah.review_number: '577'
oompah.work_branch: OOMPAH-543
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-fff4e58db6cd: '2026-08-05T16:33:52.774349+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-543
    target_state: Archived
    evidence_fingerprint: 8a8e27f5c6682f235d792dded87cf68da3b8a846611af2b8ca04ff24eb0f7114
    audit_ids:
    - audit-885b974060d0
    kind: result
    applied: true
    retired_at: '2026-08-05T16:33:52.774362+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-543
    audit_id: audit-885b974060d0
    attempt_id: attempt-fff4e58db6cd
    target_state: Archived
    evidence_fingerprint: 8a8e27f5c6682f235d792dded87cf68da3b8a846611af2b8ca04ff24eb0f7114
    status: Archived
    audit_ids:
    - audit-885b974060d0
    applied: true
    created_at: '2026-08-05T16:33:52.774377+00:00'
    applied_at: '2026-08-05T16:34:00.886463+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-885b974060d0
    project_id: proj-14849f1b
    task_id: OOMPAH-543
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8a8e27f5c6682f235d792dded87cf68da3b8a846611af2b8ca04ff24eb0f7114
    attempts:
    - version: 1
      attempt_id: attempt-fff4e58db6cd
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8a8e27f5c6682f235d792dded87cf68da3b8a846611af2b8ca04ff24eb0f7114
      created_at: '2026-08-05T16:29:32.502938+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T16:29:32.502938+00:00'
      branch_key: OOMPAH-543
      verdict: pass
      completed_at: '2026-08-05T16:33:52.774110+00:00'
      ended_at: '2026-08-05T16:33:52.774110+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T16:26:53.698981+00:00'
    updated_at: '2026-08-05T16:33:52.774110+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-fff4e58db6cd
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8a8e27f5c6682f235d792dded87cf68da3b8a846611af2b8ca04ff24eb0f7114
    created_at: '2026-08-05T16:29:32.502938+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T16:29:32.502938+00:00'
    branch_key: OOMPAH-543
oompah.task_costs:
  total_input_tokens: 25
  total_output_tokens: 5213
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 25
      output_tokens: 5213
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 25
    output_tokens: 5213
    cost_usd: 0.0
    recorded_at: '2026-08-05T16:34:18.731090+00:00'
---
## Summary

Implementation scope

Add a supported tracker-neutral removal operation so operators can correct unnecessary dependency edges without hand-editing native task Markdown. Add `oompah task remove-dependency <task-id> --depends-on <blocker-id>`, an authenticated server endpoint, TrackerProtocol support, and native oompah Markdown tracker persistence through the state branch. The operation must be idempotent when the edge is already absent, reject unresolved task identifiers consistently with add-dependency, invalidate issue caches, broadcast the updated graph, and wake dispatch when removing an edge makes Open work eligible. Update AGENTS/bootstrap CLI quick-reference generation where set-dependency is listed.

Tests

Cover CLI request construction and errors; API auth, validation, project resolution, cache/broadcast/refresh behavior; native tracker state-branch persistence and idempotency; and no mutation of unrelated dependencies. Run focused tests and `make test`.

Acceptance criteria

An operator can remove one exact dependency edge using only the supported oompah CLI; the canonical state-branch task is updated safely; repeated removal is harmless; unrelated edges remain; and newly unblocked Open work is considered immediately.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 14:38
---
Claimed by the interactive Codex session performing the owner-requested Open dependency audit. The human-only label prevents scheduler dispatch while I add the supported removal path and use it to prune verified unnecessary edges.
---
author: oompah
created: 2026-07-29 15:07
---
PR #577 CI note: GitHub-hosted Python 3.13 job 90612340751 entered pytest at 14:47:59 UTC and remained in progress >19 minutes; 3.11 and 3.12 passed in about 6 minutes. Exact commit 4591eeca8 passed locally under Python 3.13.11 via make test-serial: 13,136 passed, 7 skipped in 277.11s with clean exit. The immediately preceding main run's Python 3.13 job also passed in 5m29s. This is currently consistent with an isolated hosted-runner/subprocess-test stall rather than a deterministic PR regression; GitHub does not expose the live log archive until completion. PR remains blocked on that required check.
---
author: oompah
created: 2026-07-29 15:31
---
YOLO: merged PR #577.
---
author: oompah
created: 2026-08-05 16:27
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-05 16:29
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 16:29
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 16:34
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 7b7341201
- pr_number: 577
- merged_on_main: true
- merged_at: 2026-07-29
- days_since_merge: 7
- cli_symbol: oompah/task_cli.py:876 _cmd_remove_dependency
- server_endpoint: oompah/server.py:12358 api_remove_dependency
- tracker_protocol: oompah/tracker.py:263 remove_dependency
- native_tracker: oompah/oompah_md_tracker.py:853 remove_dependency
- github_tracker: oompah/github_tracker.py:2382 remove_dependency
- gitlab_tracker: oompah/gitlab_tracker.py:709 remove_dependency
- acp_tools: oompah/acp_tools.py:923
- agents_md_updated: AGENTS.md:72,117
- bootstrap_updated: oompah/agent_instructions.py:63,112,223,286
- tests_cli: tests/test_task_cli.py (1187,1208,1518,1677)
- tests_server: tests/test_server_dependencies.py (511,554,567,589,608,635)
- tests_native_tracker: tests/test_oompah_md_tracker.py (316,336)
- tests_github_tracker: tests/test_github_tracker.py (3852,3878,3895)
- tests_gitlab_tracker: tests/test_gitlab_tracker.py (868,880)
- tests_authority_boundary: tests/test_authority_boundary.py:681
---
author: oompah
created: 2026-08-05 16:34
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 28, Tool calls: 19
- Tokens: 25 in / 5.2K out [5.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 44s
- Log: OOMPAH-543__20260805T162949Z.jsonl
---
<!-- COMMENTS:END -->
