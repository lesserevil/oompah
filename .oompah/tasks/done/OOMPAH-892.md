---
id: OOMPAH-892
type: task
status: Done
priority: null
title: Publish rebased epic branch through server-owned CAS capability
parent: OOMPAH-879
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-891
labels: []
assignee: null
created_at: '2026-08-07T13:30:27.249055Z'
updated_at: '2026-08-07T16:21:59.258172Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-8e55db75bb62
    project_id: proj-14849f1b
    task_id: OOMPAH-892
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e7adb657d72086903f4744395dbcc192caafda7b98110fe6ab438b5e764cfb40
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Direct-owner implementation at pushed head f4053078b7c5ce02d6fa4629edc05d520615c1e9
      passed focused and matrix validation plus independent security review.
    created_at: '2026-08-07T16:21:46.738539+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-892
    target_state: Done
    evidence_fingerprint: e7adb657d72086903f4744395dbcc192caafda7b98110fe6ab438b5e764cfb40
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-07T16:21:57.524574+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Add a server-owned epic-rebase publish capability. Accept only task/project/candidate commit identity from the worker; under authority then project locks resolve remote ref strings, verify current exact authority, candidate equals locked shared-worktree HEAD, target ancestry, and remote lease SHA; execute exact argv force-with-lease push and verify remote outcome with idempotent lost-response handling. Add tamper, restart, CAS-race, and authority-revocation tests. Acceptance: no worker shell command can publish a remote ref; only the server capability can publish the exact authorized candidate.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 15:07
---
Direct owner implementation started atop validated safety commit 28c0729e in the OOMPAH-879 worktree. Project remains paused. This final child will move all epic-rebase publication into a server-owned exact-CAS capability and leave workers with task/project/candidate identity only. No remote push is authorized from the worker path.
---
author: oompah
created: 2026-08-07 16:05
---
Implemented server-owned epic-rebase CAS publication and pushed commit 635f91617a2187c980a362378261352d109fcf5c to task branch epic-OOMPAH-763--task-OOMPAH-879. Validation: exact regression nodes 5/5 passed; six-module matrix 679/679 passed with 2 warnings; git diff --check, py_compile, make terminal-audit-scan, and make check-secrets passed. The worker-facing tool accepts candidate SHA only; server re-resolves authority/project/remote/ref state under authority-then-project locks, verifies trusted-repo object/HEAD/target ancestry with replace refs disabled, performs exact force-with-lease CAS against the canonical remote, verifies the result, and durably supports idempotent recovery. No shared epic branch was pushed.
---
author: oompah
created: 2026-08-07 16:07
---
Submission handoff:  returned HTTP 400 because this delegated implementation checkout is branch epic-OOMPAH-763--task-OOMPAH-879 while the task expects work branch OOMPAH-892. The committed head is pushed and exactly matches origin/epic-OOMPAH-763--task-OOMPAH-879. No unrequested branch creation, rebase, composition, shared-epic push, or terminal-status override was performed.
---
author: oompah
created: 2026-08-07 16:07
---
Submission handoff correction: the task submission command returned HTTP 400 because this delegated implementation checkout is branch epic-OOMPAH-763--task-OOMPAH-879 while the task expects work branch OOMPAH-892. The committed head is pushed and exactly matches origin/epic-OOMPAH-763--task-OOMPAH-879. No unrequested branch creation, rebase, composition, shared-epic push, or terminal-status override was performed.
---
author: oompah
created: 2026-08-07 16:21
---
Final independent security review ACCEPTed pushed head f4053078b7c5ce02d6fa4629edc05d520615c1e9. Verified server-owned trusted repo/URL/Git environment, replacement-free candidate and ancestry validation, exact force-with-lease plus post-push target revalidation, complete durable prepared/published recovery evidence, exact current winner/generation gates, stripped worker credentials, denied remote shell pushes, and authority propagation through Claude/Codex/OpenCode rebuilt catalogs. Validation: focused 5/5, publish matrix 679/679, rebase/authority 235/235, ACP/session/boundary 224/224; secret scan clean.
---
author: oompah
created: 2026-08-07 16:21
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Direct-owner implementation at pushed head f4053078b7c5ce02d6fa4629edc05d520615c1e9 passed focused and matrix validation plus independent security review.
---
<!-- COMMENTS:END -->
