---
id: OOMPAH-535
type: bug
status: Archived
priority: 1
title: Prevent orphaned duplicate-preflight workers and phantom claims
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T23:18:01.725169Z'
updated_at: '2026-08-05T01:05:54.128349Z'
work_branch: OOMPAH-535
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/569
review_number: '569'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: aea7127676deee29c860f285d1e41a2c6ea3eeb1912c36c1ed408c5bdcd96e84
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: Duplicate-screening worker exited with reason normal.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: '2026-07-28T23:21:37.758030+00:00'
oompah.agent_run_id: e5c1863f-5dbc-4957-87a9-c6dc182bdde2
oompah.task_costs:
  total_input_tokens: 814068
  total_output_tokens: 16335
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 814000
      output_tokens: 4016
      cost_usd: 0.0
    unknown:
      input_tokens: 68
      output_tokens: 12319
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 814000
    output_tokens: 4016
    cost_usd: 0.0
    recorded_at: '2026-07-28T23:20:37.757056+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 68
    output_tokens: 12319
    cost_usd: 0.0
    recorded_at: '2026-08-05T01:05:48.654438+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/569
oompah.review_number: '569'
oompah.work_branch: OOMPAH-535
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-934bb11fc658: '2026-08-05T01:04:51.834437+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-535
    target_state: Archived
    evidence_fingerprint: 732538e0d13f16f1c5520e87466005bcaf2552949b4390708ff36d5bd33d9101
    audit_ids:
    - audit-1f5fb9f467fc
    kind: result
    applied: true
    retired_at: '2026-08-05T01:04:51.834447+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-535
    audit_id: audit-1f5fb9f467fc
    attempt_id: attempt-934bb11fc658
    target_state: Archived
    evidence_fingerprint: 732538e0d13f16f1c5520e87466005bcaf2552949b4390708ff36d5bd33d9101
    status: Archived
    audit_ids:
    - audit-1f5fb9f467fc
    applied: true
    created_at: '2026-08-05T01:04:51.834461+00:00'
    applied_at: '2026-08-05T01:04:59.649659+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-1f5fb9f467fc
    project_id: proj-14849f1b
    task_id: OOMPAH-535
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 732538e0d13f16f1c5520e87466005bcaf2552949b4390708ff36d5bd33d9101
    attempts:
    - version: 1
      attempt_id: attempt-934bb11fc658
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 732538e0d13f16f1c5520e87466005bcaf2552949b4390708ff36d5bd33d9101
      created_at: '2026-08-05T00:42:20.608601+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T00:42:20.608601+00:00'
      branch_key: OOMPAH-535
      verdict: pass
      completed_at: '2026-08-05T01:04:51.834213+00:00'
      ended_at: '2026-08-05T01:04:51.834213+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T00:41:07.984647+00:00'
    updated_at: '2026-08-05T01:04:51.834213+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-934bb11fc658
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 732538e0d13f16f1c5520e87466005bcaf2552949b4390708ff36d5bd33d9101
    created_at: '2026-08-05T00:42:20.608601+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T00:42:20.608601+00:00'
    branch_key: OOMPAH-535
---
## Summary

Incident context

The live server running main at 70771b4e dispatched duplicate-preflight workers for OOMPAH-469/470. Reconciliation treated their intentionally Open tracker state as no longer running, timed out termination, dropped the runtime entry anyway, and left persisted screening claims. One Codex process survived and modified the shared epic-OOMPAH-458 worktree while the server reported zero agents. Markdown-formatted no_duplicate verdicts were not recognized, causing retries and an incorrect Needs Human transition for OOMPAH-471.

Implementation scope

- Make reconciliation recognize duplicate-preflight workers as valid while their task remains Open and their exact claim/fingerprint is current.
- Make termination retain/represent the runtime until the CLI process group is confirmed dead; force-kill and verify on timeout, and expose termination failure instead of silently forgetting a live process.
- Clear or finalize the exact persisted duplicate claim on every normal, cancelled, failed, or forced exit without touching a newer claim. Expired claims must not count as live, and restart recovery must not permit a branch race with a surviving process.
- Parse the required verdict robustly when agents wrap field names/values in ordinary Markdown, while continuing to require a post-claim, unambiguous verdict and verifying active duplicate identifiers. Prefer a structured result path if it can be added without broadening scope.
- Enforce duplicate-preflight as read-only server-side for every backend, including Codex native tools/sandbox. Screening agents may inspect tasks/repository history and post the bounded verdict/handoff, but may not edit source, run arbitrary mutating commands, commit, push, change task state, or begin implementation.
- Preserve normal implementation-agent reconciliation, retries, one-agent-per-epic serialization, and concurrency accounting.

Relevant code

Start with oompah/orchestrator.py duplicate-preflight claim/select/finish/reconcile/termination paths, oompah/duplicate_screening.py, oompah/focus.py, oompah/api_agent.py and CLI session policy. Reuse existing authority/tool-policy mechanisms rather than relying only on prompt text.

Required tests

Add regressions proving: an Open preflight is not reconciled away; stale/mismatched claims are terminated; a cancellation-resistant CLI tree is killed and never disappears from accounting while alive; exact claims are cleared/finalized on every exit; bold/backticked Markdown no_duplicate and duplicate_candidate fields parse; ambiguous/free-form text remains inconclusive; Needs Human is not reached after a conclusive verdict; and Codex/Claude duplicate screening cannot mutate files or task state. Include a shared-epic branch-race/restart case. Run focused tests and make test.

Acceptance criteria

The server never reports zero agents while an Oompah-owned worker remains alive; Open duplicate-preflight workers survive reconciliation only while their exact claim is current; every exit leaves no phantom claim; a conclusive post-claim verdict advances screening exactly once; duplicate agents cannot modify the worktree; and the 22-task dispatch lane can resume without human intervention or concurrent writers on epic-OOMPAH-458.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 23:18
---
Claimed for direct incident recovery and implementation in this session. I will preserve the orphaned OOMPAH-458 worktree before terminating it, repair the live server, implement the lifecycle and read-only enforcement regressions, run focused tests plus make test, push the fix, and verify the deployed service.
---
author: oompah
created: 2026-07-28 23:18
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-07-28 23:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 23:20
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 10
- Tokens: 814.0K in / 4.0K out [818.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 2s
- Log: OOMPAH-535__20260728T231844Z.jsonl
---
author: oompah
created: 2026-07-28 23:39
---
Implementation complete on branch OOMPAH-535. Focused lifecycle/capability regressions pass (278 tests), and the full make test gate passes (13,082 passed, 7 skipped). Preparing the reviewed branch for push and deployment; the project remains paused until the corrected service is running.
---
author: oompah
created: 2026-08-05 00:41
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-05 00:42
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 00:42
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 01:04
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 1d7735f35a4a14976456fd029e46b1811ea1f42d
- merge_pr: #569
- merge_date: 2026-07-28 18:46:53 -0500
- implementation_commit: 20dd1e42be7c99e7e9044021ebb0c05a852006b8
- files_changed: 15 files, +864 -58
- ancestry_check: 20dd1e42b is-ancestor HEAD (main)
- core_files: oompah/orchestrator.py, oompah/agent.py, oompah/duplicate_screening.py, oompah/acp_tools.py, oompah/acp_backends/codex.py, oompah/focus.py, oompah/api_agent.py
- regression_test_file: tests/test_duplicate_preflight.py (40+ tests including reconcile/termination/markdown/restart cases)
- read_only_test_files: tests/test_acp_project_tools.py, tests/test_acp_codex_backend.py (read_only tool catalogs)
- age_days_since_merge: ~7
---
author: oompah
created: 2026-08-05 01:05
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 82, Tool calls: 62
- Tokens: 68 in / 12.3K out [12.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 23m 21s
- Log: OOMPAH-535__20260805T004240Z.jsonl
---
<!-- COMMENTS:END -->
