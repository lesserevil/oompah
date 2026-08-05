---
id: OOMPAH-820
type: bug
status: Merged
priority: 1
title: Bootstrap exact-head review-generation fence on main
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T03:09:46.087231Z'
updated_at: '2026-08-05T05:23:58.056358Z'
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
  applied_result_attempts:
    attempt-9523d45a243e: '2026-08-05T05:19:41.394496+00:00'
    attempt-b34e4b658463: '2026-08-05T05:23:48.900315+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-820
    target_state: Done
    evidence_fingerprint: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
    audit_ids:
    - audit-c6b562003077
    kind: result
    applied: true
    retired_at: '2026-08-05T05:19:41.394504+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-820
    target_state: Merged
    evidence_fingerprint: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
    audit_ids:
    - audit-f6f065e8d0df
    kind: result
    applied: true
    retired_at: '2026-08-05T05:23:48.900335+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-820
    audit_id: audit-c6b562003077
    attempt_id: attempt-9523d45a243e
    target_state: Done
    evidence_fingerprint: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
    status: In Validation
    audit_ids:
    - audit-c6b562003077
    applied: true
    created_at: '2026-08-05T05:19:41.394515+00:00'
    applied_at: '2026-08-05T05:19:50.116728+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-820
    audit_id: audit-f6f065e8d0df
    attempt_id: attempt-b34e4b658463
    target_state: Merged
    evidence_fingerprint: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
    status: Merged
    audit_ids:
    - audit-f6f065e8d0df
    applied: true
    created_at: '2026-08-05T05:23:48.900353+00:00'
    applied_at: '2026-08-05T05:23:56.779155+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c6b562003077
    project_id: proj-14849f1b
    task_id: OOMPAH-820
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
    attempts:
    - version: 1
      attempt_id: attempt-9523d45a243e
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
      created_at: '2026-08-05T04:46:26.008377+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T04:46:26.008377+00:00'
      branch_key: OOMPAH-820
      verdict: pass
      completed_at: '2026-08-05T05:19:41.394381+00:00'
      ended_at: '2026-08-05T05:19:41.394381+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-05T04:42:16.948692+00:00'
    updated_at: '2026-08-05T05:19:41.394381+00:00'
  - version: 1
    audit_id: audit-f6f065e8d0df
    project_id: proj-14849f1b
    task_id: OOMPAH-820
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
    attempts:
    - version: 1
      attempt_id: attempt-b34e4b658463
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
      created_at: '2026-08-05T05:21:05.471012+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T05:21:05.471012+00:00'
      branch_key: OOMPAH-820
      verdict: pass
      completed_at: '2026-08-05T05:23:48.900161+00:00'
      ended_at: '2026-08-05T05:23:48.900161+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-05T04:42:16.948692+00:00'
    updated_at: '2026-08-05T05:23:48.900161+00:00'
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
  - version: 1
    attempt_id: attempt-b34e4b658463
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1590905549166dea0996dc2e2167092ed63d7014a21a8416275efb1ff4e6d4da
    created_at: '2026-08-05T05:21:05.471012+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T05:21:05.471012+00:00'
    branch_key: OOMPAH-820
oompah.task_costs:
  total_input_tokens: 6
  total_output_tokens: 192
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 6
      output_tokens: 192
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 192
    cost_usd: 0.0
    recorded_at: '2026-08-05T05:20:50.840355+00:00'
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
author: oompah
created: 2026-08-05 05:19
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- reviewed_head: f3b9f9bc5dad4cae876f081b45a6cece2eb72341
- main_merge_commit: 8d24fb7b4
- pr_number: 717
- diff_stat: 10 files changed, 2753 insertions(+), 278 deletions(-)
- test_run: 15428 passed, 7 skipped, 1 xfailed, 1 flaky failed in 522.62s
- flaky_failure: tests/test_pr_body_and_review_metadata.py::TestBuildPrBody::test_non_github_tracker_uses_plain_link (5s pytest-timeout on sqlite3.executescript in IntegrationQueueStore.__init__; file not touched by OOMPAH-820)
- terminal_mutation_scan: 8/8 allowlisted
- focused_regressions_passed: test_oompah_818_old_merged_review_cannot_terminalize_new_submission, test_remote_head_must_match_accepted_submission_before_gate, test_resubmit_generation_change_after_review_lookup_fences_terminal_staging, test_two_loop_submit_wins_before_exact_review_metadata_or_audit, test_bridge_timeout_retains_task_ownership_until_inner_operation_exits, test_final_review_revalidation_rejects_state_change_before_metadata
---
author: oompah
created: 2026-08-05 05:20
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 55, Tool calls: 37
- Tokens: 6 in / 192 out [198 total]
- Cost: $0.0000
- Exit: normal, Duration: 34m 20s
- Log: OOMPAH-820__20260805T044641Z.jsonl
---
author: oompah
created: 2026-08-05 05:21
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 05:21
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 05:23
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- reviewed_head: f3b9f9bc5dad4cae876f081b45a6cece2eb72341
- main_merge_commit: 8d24fb7b411af40bb02292236368c727ecfdb0d0
- pr_number: 717
- merge_ancestor_check: f3b9f9bc5 is ancestor of origin/main
- focused_regressions: 6 passed in 3.56s
- diff_stat: 10 files changed, 2753 insertions(+), 278 deletions(-)
- prior_full_gate: 15428 passed, 7 skipped, 1 xfailed, 1 flaky failed (unrelated file) in 522.62s
---
<!-- COMMENTS:END -->
