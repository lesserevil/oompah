---
id: OOMPAH-820
type: bug
status: In Validation
priority: 1
title: Bootstrap exact-head review-generation fence on main
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T03:09:46.087231Z'
updated_at: '2026-08-05T04:46:38.095804Z'
work_branch: OOMPAH-820
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/717
review_number: '717'
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-820
  head_sha: f3b9f9bc5dad4cae876f081b45a6cece2eb72341
  submitted_at: '2026-08-05T04:25:04.476905+00:00'
  updated_at: '2026-08-05T04:25:04.476905+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/717
oompah.review_number: '717'
oompah.work_branch: OOMPAH-820
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c6b562003077
    project_id: proj-14849f1b
    task_id: OOMPAH-820
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
    attempts:
    - version: 1
      attempt_id: attempt-9523d45a243e
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
      created_at: '2026-08-05T04:46:26.008377+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T04:46:26.008377+00:00'
      branch_key: OOMPAH-820
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-05T04:42:16.948692+00:00'
    updated_at: '2026-08-05T04:46:26.008377+00:00'
  - version: 1
    audit_id: audit-f6f065e8d0df
    project_id: proj-14849f1b
    task_id: OOMPAH-820
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-05T04:42:16.948692+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-9523d45a243e
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
    created_at: '2026-08-05T04:46:26.008377+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T04:46:26.008377+00:00'
    branch_key: OOMPAH-820
---
## Summary

Triggered by: OOMPAH-819

Bootstrap delivery for the live stale-review-generation regression discovered while re-submitting OOMPAH-818. OOMPAH-819 is correctly attached to systemic epic OOMPAH-768 for program accounting, but that nested epic branch cannot repair the currently running main-based integration path needed to land the fix. Implement the OOMPAH-819 exact-head review fence on a standalone branch targeting main first, using the same code/tests: standalone Ready reconciliation must never reuse a merged/closed/open review whose forge head differs from the current accepted oompah.integration head; terminal staging requires exact reviewed-head landing proof; stale review history is preserved; concurrent resubmit/webhook/restart paths are fenced. Required regressions include the exact OOMPAH-818 e3140b65 versus PR #716 old-head sequence and current-head controls. Acceptance: the fix passes focused and configured exact-head gates, deploys to main, and OOMPAH-818 can then be re-submitted to a new gate/review without stale terminalization. After deployment, the same patch may be recorded on OOMPAH-819's epic lineage for program rollup.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 03:11
---
Started main-based implementation of the exact-head Ready reconciliation fence. Live evidence confirms find_pr_for_branch returned historical PR #716 for OOMPAH-818 at new accepted head e3140b65, then Ready reconciliation staged Merged without an exact-head gate or target landing. I am binding review reuse and terminal staging to the accepted integration head plus current delivery authority, with stale-history and resubmit/webhook/restart regressions.
---
author: oompah
created: 2026-08-05 03:19
---
Acceptance blocker added from exact live OOMPAH-818 audit metadata: stale Done/in_progress fingerprint can be reused across a new Merged fingerprint, omitting required fresh Done audit. Bootstrap must make _build_merged_entries fingerprint-aware, supersede stale active Done while preserving history, and test the exact old-Done+new-Merged chain. Review-generation fix must also bind source/target/head and execute terminal staging under final standalone submission authority. Server remains paused; OOMPAH-818 audit queue is zero.
---
author: oompah
created: 2026-08-05 03:42
---
Independent concurrency review found and blocked two production-only races before submission: the prior task ownership lock was an asyncio.Lock shared across API and scheduler event loops, and exact-review metadata writes occurred before the final submission-generation fence. The bootstrap is being strengthened with one process-wide cross-loop task mutex covering submit, dispatch, webhook/label terminal requests, exact review metadata, final authority revalidation, and coordinator staging. The original RLock/coordinator deadlock and malformed Done→Merged audit-chain replay are already reproduced and fixed; server remains paused pending bounded two-loop race tests and re-review.
---
author: oompah
created: 2026-08-05 04:02
---
Implemented and pushed generation-safe standalone Ready delivery fencing at 43a8b531ea8ab4bf06dd1d8fd54b484b0a34fdc3. Exact source/target/head review validation now fails closed; historical cleanup, open-review adoption, and post-gate review creation run under the shared cross-loop task mutex with final tracker/forge CAS; stale webhook/label snapshots refresh and reject changed delivery generations; malformed mixed-fingerprint Done/Merged audit chains are superseded and rebuilt. Verification: 743 affected workflow/concurrency/webhook tests passed; 226 additional terminal-audit/fingerprint/override tests passed; terminal mutation scan passed (8/8 allowlisted); check-secrets and git diff --check passed. Branch origin/OOMPAH-820 is ready for independent review. Task intentionally not submitted yet.
---
author: oompah
created: 2026-08-05 04:07
---
Final independent review rejected exact head 43a8b531 before submission. Four remaining fail-closed gaps are under repair: delayed open/reopen webhook writes bypass task ownership/exact review-head CAS; bridge timeout cancellation can release ownership while uncancellable worker side effects continue; authority-owned review metadata writes can swallow required-field failures and still move In Review; and native Markdown compatibility does not mirror review_head, allowing stale top-level evidence to override namespaced updates. The existing exact-head/audit-chain tests remain green. New race/persistence regressions and another exact-head review are required; server stays paused.
---
author: oompah
created: 2026-08-05 04:22
---
Final concurrency-review repairs pushed at f3b9f9bc5dad4cae876f081b45a6cece2eb72341. Added task-owned open/reopen webhook adoption with fresh tracker generation CAS, signed webhook head parsing, exact live forge review identity/source/target/head validation, strict grouped metadata persistence, and In Review only after persisted evidence verifies. Terminal staging now runs in a shielded inner lock owner; bridge timeout no longer cancels it, so submit cannot cross outstanding to_thread/coordinator work. Authority-owned metadata failures now fail closed, and native Markdown mirrors oompah.review_head to review_head. Verification: 749 affected workflow/concurrency/webhook tests passed; 383 terminal-audit/native tracker tests passed; full standalone 56/56; terminal mutation scan 8/8; check-secrets, compile, and diff-check passed. Branch remains unsubmitted for independent final review.
---
author: oompah
created: 2026-08-05 04:25
---
Independent exact-head re-review ACCEPTED f3b9f9bc5dad4cae876f081b45a6cece2eb72341. Concurrency reviewer verified task-owned signed-head open/reopen webhook adoption and cancellation-safe bridge ownership (344 exact/webhook tests). Tracker/audit reviewer verified strict metadata failure ordering, native review_head compatibility, and exact webhook persistence (518 targeted/impacted tests). Combined implementation matrices and scans remain green; submitting this exact clean head for the configured server gate.
---
author: oompah
created: 2026-08-05 04:25
---
Implemented exact-head standalone review-generation fencing, cross-loop task ownership, cancellation-safe terminal staging, fingerprint-correct Done→Merged audit recovery, strict review metadata persistence, and signed-head webhook adoption. Independent reviews accepted exact head f3b9f9bc; affected matrices and scans pass.
---
author: oompah
created: 2026-08-05 04:32
---
Branch quality gate passed for `f3b9f9bc5dad4cae876f081b45a6cece2eb72341` using `make test` in 428.5s. Review creation may proceed.
---
author: oompah
created: 2026-08-05 04:42
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 04:42
---
YOLO: merged PR #717.
---
author: oompah
created: 2026-08-05 04:46
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 04:46
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
