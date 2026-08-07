---
id: OOMPAH-886
type: task
status: In Progress
priority: null
title: Add atomic idempotent create-once tracker operations
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-879
labels:
- human-only
assignee: null
created_at: '2026-08-07T12:42:12.972567Z'
updated_at: '2026-08-07T18:19:07.135354Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-886
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0bea2cd2fea4fce3202d8deff0fe3f1022ab48374b5b74f48d32e75edc901b70
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T12:58:13.843360+00:00'
  matched_identifiers: []
  evidence: 'Project-owner corpus review: no existing task provides a TrackerProtocol/native
    tracker atomic create-once idempotency contract for ambiguous create responses.
    OOMPAH-879 intentionally supplies only the immediate fail-closed reservation;
    OOMPAH-886 is the distinct liveness completion.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-07T12:58:13.843360+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: 'Project-owner corpus review: no existing task provides
    a TrackerProtocol/native tracker atomic create-once idempotency contract for ambiguous
    create responses. OOMPAH-879 intentionally supplies only the immediate fail-closed
    reservation; OOMPAH-886 is the distinct liveness completion.'
oompah.agent_run_id: 5e3e5dd3-0c9e-4720-bb24-fc4f8fb9aff0
oompah.work_contributors:
  runs:
  - run_id: 58a7d3726e5c4310b95d2456e1ceb9d2--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-886
    source_sha: null
    completed_at: ''
  - run_id: 837fcb836918483888e7b6e4ccde98f8--contributor-57ff1a86c984
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: general
    source_branch: epic-OOMPAH-763--task-OOMPAH-886
    source_sha: null
    completed_at: ''
  - run_id: f51b6730742f4f619681e6ebcf72e89e--contributor-1e03bff0a496
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: general
    source_branch: epic-OOMPAH-763--task-OOMPAH-886
    source_sha: null
    completed_at: ''
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-886
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-886
  base_branch: epic-OOMPAH-763
  base_sha: a85a36baf7b3ebcb45be27823755b5694a790a49
  updated_at: '2026-08-07T17:54:54.402892+00:00'
---
## Summary

OOMPAH-879 must fail closed after an ambiguous tracker create response because TrackerProtocol.create_issue has no idempotency key: a retry can create a second scheduler helper after the first commit succeeded but its response was lost. Implement a native atomic create-once primitive keyed by project, operation kind, and durable caller-supplied creation marker. Scope: extend the tracker protocol and native Markdown tracker so marker lookup and issue creation commit under the same write/state-branch transaction; an authorized retry returns the exact original issue without another allocation; concurrent requests and restart recovery converge on one issue; adapters that cannot prove create-once support fail closed rather than retry ambiguously. Wire epic-rebase helper creation to reconcile its persisted marker through this primitive, allowing a definitely failed create to retry safely without a permanent reservation deadlock. Relevant context: OOMPAH-879 authority state, tracker protocol/native tracker allocation, state-branch persistence, and helper scheduler. Required tests: response lost after commit then retry; response lost before commit then retry; concurrent same-key calls; same key with mismatched payload rejected; process restart; state-branch push/reconciliation failure; unsupported external tracker; epic-rebase helper resumes naturally and creates exactly one task. Acceptance: no ambiguous create response can duplicate a task or permanently deadlock recoverable creation, and the operation remains fail closed across persistence and adapter failures.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 12:42
---
Filed from OOMPAH-879 final review. OOMPAH-879 ships the immediate no-duplicate fail-closed reservation; this task restores bounded liveness with a real atomic create-once contract after the authority fix lands.
---
author: oompah
created: 2026-08-07 12:51
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 12:51
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 21s
---
author: oompah
created: 2026-08-07 12:51
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-848, OOMPAH-849, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861, OOMPAH-862, OOMPAH-863, OOMPAH-864, OOMPAH-865, OOMPAH-866, OOMPAH-877, OOMPAH-878, OOMPAH-879, OOMPAH-880, OOMPAH-881, OOMPAH-882, OOMPAH-884, OOMPAH-885, OOMPAH-887. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
author: oompah
created: 2026-08-07 17:51
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-07 17:51
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-07 17:52
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-07 17:52
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 2s
- Log: OOMPAH-886__20260807T175152Z.jsonl
---
author: oompah
created: 2026-08-07 17:53
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-07 17:53
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-07 17:54
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 20s (attempt #2)
---
author: oompah
created: 2026-08-07 17:54
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 56s
- Log: OOMPAH-886__20260807T175341Z.jsonl
---
author: oompah
created: 2026-08-07 17:54
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-08-07 17:55
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-07 18:01
---
Understanding: Implementing atomic idempotent create-once tracker operations. The core issue is that TrackerProtocol.create_issue has no idempotency key, so a retry after a lost response can create a second epic-rebase helper task.

Plan:
1. Add TrackerCreateOnceUnsupportedError to tracker.py
2. Add create_issue_once(creation_marker, title, ...) to TrackerProtocol
3. Implement create_issue_once atomically on OompahMarkdownTracker: under the write lock, scan for existing task with marker in body; if found return it; if not, call create_issue (RLock is re-entrant so no deadlock)
4. Fail-closed implementation on GitHub/GitLab trackers (raise TrackerCreateOnceUnsupportedError)
5. Update _file_rebase_task in orchestrator.py to use create_issue_once for native trackers, and add recovery path for authority_creation_reserved=True that calls create_issue_once instead of returning None
6. Write all required tests

Key files: oompah/tracker.py, oompah/oompah_md_tracker.py, oompah/github_tracker.py, oompah/gitlab_tracker.py, oompah/orchestrator.py, tests/test_oompah_md_tracker.py, tests/test_tracker_protocol.py, tests/test_epic_rebase_state.py
---
<!-- COMMENTS:END -->
