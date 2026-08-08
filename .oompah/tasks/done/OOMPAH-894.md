---
id: OOMPAH-894
type: task
status: Done
priority: null
title: Coalesce repeated owner rearm without erasing retained auto-archive provenance
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T13:45:31.251950Z'
updated_at: '2026-08-08T16:27:35.029464Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-319b12991196
    project_id: proj-14849f1b
    task_id: OOMPAH-894
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 642890b8c42ebed8bcf5cb299f9121437c1cfa8a369c4dd71f25b4880b31ac36
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope is contained in that validated head; owner override avoids fabricating
      a separate branch/integration generation.
    created_at: '2026-08-08T16:27:30.975178+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Live diagnostic while repairing OOMPAH-877: an exhausted unbound auto-archive audit can be owner-rearmed successfully once while correctly retaining requested_by=auto_archive for future origin/main provenance binding, but repeating the same otherwise idempotent rearm returns audit_not_retryable because coalescing requires the fresh audit requested_by actor to equal the rearm-history owner actor. Implementation scope: separate retained transition provenance from rearm authorization/idempotency identity in terminal_transition_coordinator and terminal audit metadata; coalesce an exact repeated owner rearm for the same project/task/target/evidence generation without rewriting original auto_archive provenance or accepting a different actor/generation. Preserve evidence fingerprint and project-lock CAS fences. Required tests: unbound auto-archive first rearm then exact repeated rearm coalesces; retained requested_by remains auto_archive; late origin/main binding still works; bound owner provenance control; different owner/reason/evidence generation does not coalesce; concurrent repeat has one durable history entry; restart persistence. Acceptance: exact repeated owner rearm is idempotent and successful while historical transition provenance remains truthful and immutable.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 07:31
---
Implementation started in isolated worktree at systemic head 6cbbd6ef7bb7882257c4c9e9175bd5b3edc14183. Reproducing repeated owner-rearm provenance/idempotency conflict and adding focused concurrency/restart coverage.
---
author: oompah
created: 2026-08-08 07:43
---
Implementation checkpoint: separated retained terminal requested_by provenance from durable owner-rearm identity in coordinator coalescing and restart intent validation. Added restart/late origin-main binding, bound provenance, changed actor/reason/fingerprint/generation rejection, concurrent single-history-entry, and auto-archive crash-recovery regressions. Static compile/diff/terminal-mutation checks pass; focused broker suite is waiting behind the active full gate.
---
author: oompah
created: 2026-08-08 07:50
---
Implementation complete for integration at commit fccb3b746faec2ace2f9f241ced3fa7d0fe4509d on implementation/OOMPAH-894-direct (exact parent 6cbbd6ef7bb7882257c4c9e9175bd5b3edc14183). Focused dedicated broker: 12 passed in 2.40s; artifact /home/shedwards/.oompah/tmp/OOMPAH-894-focused.g4wmmY. Final py_compile, git diff --check, and make terminal-audit-scan passed. Worktree is clean; awaiting systemic-head integration and the configured full gate.
---
<!-- COMMENTS:END -->
