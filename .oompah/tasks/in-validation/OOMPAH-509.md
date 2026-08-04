---
id: OOMPAH-509
type: feature
status: In Validation
priority: 2
title: Parallelize pytest safely on isolated workers
parent: OOMPAH-502
children: []
blocked_by:
- OOMPAH-492
- OOMPAH-490
labels: []
assignee: null
created_at: '2026-07-28T15:06:10.253754Z'
updated_at: '2026-08-04T21:29:09.773824Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.work_branch: epic-OOMPAH-502
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-83c5b2c0ec81
    project_id: proj-14849f1b
    task_id: OOMPAH-509
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2170d2dcb816c9a09f0d0baf964fc1c30a6bb78365e2d4f12521507b50d6c355
    attempts:
    - version: 1
      attempt_id: attempt-ada7fba12612
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 2170d2dcb816c9a09f0d0baf964fc1c30a6bb78365e2d4f12521507b50d6c355
      created_at: '2026-08-04T21:28:54.022325+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T21:28:54.022325+00:00'
      branch_key: epic-OOMPAH-502
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T18:28:52.300310+00:00'
    updated_at: '2026-08-04T21:28:54.022325+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ada7fba12612
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2170d2dcb816c9a09f0d0baf964fc1c30a6bb78365e2d4f12521507b50d6c355
    created_at: '2026-08-04T21:28:54.022325+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T21:28:54.022325+00:00'
    branch_key: epic-OOMPAH-502
---
## Summary

Problem: make test runs roughly 12k tests serially despite 64 CPUs. OOMPAH-490 is pruning and isolating the suite, and OOMPAH-491 blocks network Git; OOMPAH-492 owns known live-tracker leaks. Parallel execution must build on those protections rather than mask races.

Implementation: add pytest-xdist as a development/test dependency and make OOMPAH_PYTEST_WORKERS in .env control the Makefile test worker count with a conservative default based on measured safety, plus an explicit serial diagnostic target. Mark or group genuinely process-global tests (ports, Granian, environment, service PID, Git worktree metadata) so they remain deterministic. Ensure each worker receives isolated temp/cache/home paths and the Git-remote barrier. Record serial versus parallel duration and worker count; do not select 64 blindly under memory/storage pressure.

Tests: run collection and focused isolation suites, then compare a clean serial full run with repeated parallel full runs. Assert identical pass/skip/xfail outcomes, no live network Git, no leaked subprocesses, clean git status, and useful failure output. Add Makefile/config/docs contract tests.

Acceptance criteria: make test uses a safe bounded worker count, is materially faster than serial, remains deterministic, and make test-serial provides a reliable debugging fallback.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:06
---
Claimed for manual implementation by the current Codex session. Held in Backlog while the shared epic branch is built so Oompah does not dispatch another agent; status will move to In Progress and Done as this session completes the slice.
---
author: oompah
created: 2026-07-28 16:00
---
Sequencing update: the required no-network and live-tracker isolation changes are committed only on the still-incomplete epic-OOMPAH-490 branch. Added an explicit dependency on the whole epic to preserve branch atomicity; no child commit will be cherry-picked. I am proceeding with the non-overlapping xdist/config work on epic-OOMPAH-502 and will run repeated parallel full-suite verification only after OOMPAH-490 is merged and rebased.
---
author: oompah
created: 2026-07-28 16:08
---
Checkpoint c25b592c5 is pushed on epic-OOMPAH-502: pytest-xdist 3.8.0; bounded OOMPAH_PYTEST_WORKERS=1..16 with default 4; make test-serial; private per-run and per-worker HOME/TMP/XDG cache trees under OOMPAH_TEMP_ROOT; one xdist group for process-owning tests; docs and contract tests. Focused results: 10 runner/plugin contracts passed; 97 process integration cases passed serially in 27.76s; 108 cases passed with four isolated workers in 37.28s before grouping optimization; the corrected live grouping check passed and put both selected process modules on gw0. No run directories or subprocesses leaked. Full repeated parallel-suite timing remains blocked on whole-epic OOMPAH-490 merge as recorded by the dependency.
---
author: oompah
created: 2026-07-28 17:29
---
Authoritative repeated parallel validation now passes on aa93fa639 with four isolated workers: 12,616 passed, 7 skipped in 70.52s and 69.12s. The prior clean serial baseline on the same product code was 12,614 passed, 7 skipped in 274.81s; the two additional passes are isolation regression tests. A full exact-head serial confirmation is now running. The xdist work also found and fixed two real runner isolation defects (tilde temp-root expansion and legacy tests clearing OOMPAH_PYTEST_RUN_ROOT). No pytest run roots or child processes leaked after either successful run.
---
author: oompah
created: 2026-07-28 17:34
---
Completed exact-head validation on aa93fa639. Serial: 12,616 passed, 7 skipped in 271.98s. Parallel with OOMPAH_PYTEST_WORKERS=4: the same 12,616 passed and 7 skipped in 70.52s and 69.12s on consecutive runs, a stable 3.9x speedup. The serial fallback and both parallel runs removed their private run roots and leaked no pytest or Granian child process. The branch is clean and pushed. make test now uses bounded four-worker isolation; make test-serial remains the reliable diagnostic fallback.
---
author: oompah
created: 2026-07-28 17:34
---
Added bounded four-worker pytest-xdist execution with per-run/per-worker filesystem isolation, serialized process-owning tests, and an exact-outcome serial fallback; repeated full suites show a stable 3.9x speedup.
---
author: oompah
created: 2026-08-04 18:28
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 21:29
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
<!-- COMMENTS:END -->
