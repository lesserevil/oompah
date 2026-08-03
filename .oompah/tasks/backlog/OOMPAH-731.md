---
id: OOMPAH-731
type: task
status: Backlog
priority: null
title: Complete direct epic rebases without self-invalidating submission
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T17:45:33.391967Z'
updated_at: '2026-08-03T17:46:35.420449Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction: EXOCOMP-244 is an auto-filed direct rebase task for epic-EXOCOMP-135. Its implementation agent correctly rebased the shared epic onto origin/main, verified the patch series with range-diff, and force-pushed the published epic from 333c3b81 to 98e26f09. The subsequent task submission entered ordinary child integration, whose worktree-head validator compared the intentionally pre-rebase preserved epic checkout with the newly published epic ref and rejected the task. This leaves a successful maintenance task Open with an integration_retry alert and invites duplicate work.\n\nImplementation scope:\n- Give direct shared-epic maintenance/rebase tasks a completion path that recognizes the task itself has authoritatively published the recorded epic work_branch.\n- After a successful lease-protected publish, atomically record old/new epic SHAs and reconcile a clean registered epic checkout to the published SHA, while preserving dirty, divergent-unproven, active-operation, recovery, and concurrent-update states.\n- Do not enqueue the maintenance helper as an ordinary child merge back into the epic it just rewrote; transition it through the Done-only audited maintenance lifecycle.\n- Make restart/recovery idempotently recognize an already-published exact head and resume completion without rerunning the rebase or emitting a permanent integration_retry alert.\n- Preserve branch protection, exact force-with-lease semantics, recovery reachability, auxiliary-worktree cleanup, and normal child integration behavior.\n\nRelevant code: epic staleness maintenance dispatch and completion, task submit routing, integration worktree head validation, ProjectStore registered epic worktree reconciliation, terminal transition coordination, and alert reconciliation.\n\nRequired tests:\n- Reproduce EXOCOMP-244 with a clean old registered epic checkout and a successfully force-with-lease published rebased epic; prove completion realigns safely and reaches audited Done without ordinary child integration.\n- Cover clean fast-forward publication, history-rewriting rebase with equivalent recorded range, dirty checkout, active rebase, stable recovery ref, lease loss/concurrent remote movement, missing publication evidence, restart between push and completion, repeated recovery, and ordinary child submissions.\n- Assert no unique commit or recovery ref is deleted, no reset occurs for unproven divergence, and stale integration alerts clear once exact completion is reconciled.\n- Run focused epic-rebase, maintenance, integration executor/queue, worktree recovery, terminal lifecycle, alert, and restart suites plus make test.\n\nAcceptance criteria:\n- A successful direct epic rebase cannot invalidate its own submission by construction.\n- EXOCOMP-244-style tasks converge to audited Done exactly once after the published epic is proven.\n- Unsafe or ambiguous checkout states remain preserved with actionable diagnostics.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 17:46
---
Live workaround applied safely: verified EXOCOMP-244 had no running agent; preserved old clean epic-EXOCOMP-135 head 333c3b81 under local recovery/epic-EXOCOMP-135-pre-rebase-333c3b81; detached and repointed the local epic branch to already-published 98e26f09 without reset or deletion; verified both authoritative epic and assigned task worktrees clean at 98e26f09; resubmitted from the required derived task checkout. A submit from the direct epic checkout was rejected because expected_work_branch remains epic-EXOCOMP-135--task-EXOCOMP-244, confirming the branch-model mismatch in scope.
---
<!-- COMMENTS:END -->
