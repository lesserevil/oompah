---
id: OOMPAH-886
type: task
status: Needs Human
priority: null
title: Add atomic idempotent create-once tracker operations
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-879
labels: []
assignee: null
created_at: '2026-08-07T12:42:12.972567Z'
updated_at: '2026-08-07T12:51:53.162471Z'
work_branch: null
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
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: 'Required structural peers could not fit the bounded duplicate corpus.
    Omitted peer identifiers: OOMPAH-848, OOMPAH-849, OOMPAH-850, OOMPAH-851, OOMPAH-852,
    OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861,
    OOMPAH-862, OOMPAH-863, OOMPAH-864, OOMPAH-865, OOMPAH-866, OOMPAH-877, OOMPAH-878,
    OOMPAH-879, OOMPAH-880, OOMPAH-881, OOMPAH-882, OOMPAH-884, OOMPAH-885, OOMPAH-887.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 3
  retry_after: '2026-08-07T12:51:29.337142+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3c8bd66f-68ab-4674-90f8-6bf7e87745f2
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
<!-- COMMENTS:END -->
