---
id: OOMPAH-535
type: bug
status: Backlog
priority: 1
title: Prevent orphaned duplicate-preflight workers and phantom claims
parent: null
children: []
blocked_by: []
labels:
- needs:backend
- needs:test
assignee: null
created_at: '2026-07-28T23:18:01.725169Z'
updated_at: '2026-07-28T23:18:01.725169Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

