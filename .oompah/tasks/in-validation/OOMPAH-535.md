---
id: OOMPAH-535
type: bug
status: In Validation
priority: 1
title: Prevent orphaned duplicate-preflight workers and phantom claims
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T23:18:01.725169Z'
updated_at: '2026-08-05T00:42:29.411771Z'
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
  total_input_tokens: 814000
  total_output_tokens: 4016
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 814000
      output_tokens: 4016
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 814000
    output_tokens: 4016
    cost_usd: 0.0
    recorded_at: '2026-07-28T23:20:37.757056+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/569
oompah.review_number: '569'
oompah.work_branch: OOMPAH-535
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-1f5fb9f467fc
    project_id: proj-14849f1b
    task_id: OOMPAH-535
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 732538e0d13f16f1c5520e87466005bcaf2552949b4390708ff36d5bd33d9101
    attempts:
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
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T00:41:07.984647+00:00'
    updated_at: '2026-08-05T00:42:20.608601+00:00'
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
<!-- COMMENTS:END -->
