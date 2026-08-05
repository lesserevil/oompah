---
id: OOMPAH-543
type: bug
status: In Validation
priority: 1
title: Support removing task dependencies through the CLI and API
parent: null
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T14:38:32.101999Z'
updated_at: '2026-08-05T16:29:46.535078Z'
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
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-885b974060d0
    project_id: proj-14849f1b
    task_id: OOMPAH-543
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8a8e27f5c6682f235d792dded87cf68da3b8a846611af2b8ca04ff24eb0f7114
    attempts:
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
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T16:26:53.698981+00:00'
    updated_at: '2026-08-05T16:29:32.502938+00:00'
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
<!-- COMMENTS:END -->
