---
id: OOMPAH-988
type: bug
status: Merged
priority: 1
title: Reuse exact branch gates after the accepted head lands and its branch is deleted
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T05:18:40.854524Z'
updated_at: '2026-08-10T06:43:16.896572Z'
work_branch: OOMPAH-988
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-988
  head_sha: 2028162ed44c38137ac41b57d1286fe58e0d4ce7
  submitted_at: '2026-08-10T05:47:12.827963+00:00'
  updated_at: '2026-08-10T05:47:12.827963+00:00'
oompah.work_branch: OOMPAH-988
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-fd8343e499be
    project_id: proj-14849f1b
    task_id: OOMPAH-988
    digest: 9124f988919b1af1c551b3046845e3778f4aefe54755f8ff76b6d956ff95d818
  - version: 1
    audit_id: audit-6faade084e7b
    project_id: proj-14849f1b
    task_id: OOMPAH-988
    digest: 9124f988919b1af1c551b3046845e3778f4aefe54755f8ff76b6d956ff95d818
  oompah.terminal_override_records:
  - version: 1
    override_id: override-d9a9490f4361
    project_id: proj-14849f1b
    task_id: OOMPAH-988
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9124f988919b1af1c551b3046845e3778f4aefe54755f8ff76b6d956ff95d818
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: '[REDACTED]'
    created_at: '2026-08-10T06:43:04.656306+00:00'
    selected_ref: 2028162ed44c38137ac41b57d1286fe58e0d4ce7
    selected_sha: 2028162ed44c38137ac41b57d1286fe58e0d4ce7
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-988
    target_state: Merged
    evidence_fingerprint: 9124f988919b1af1c551b3046845e3778f4aefe54755f8ff76b6d956ff95d818
    audit_ids:
    - audit-fd8343e499be
    - audit-6faade084e7b
    kind: override
    applied: true
    retired_at: '2026-08-10T06:43:15.321068+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-fd8343e499be
    project_id: proj-14849f1b
    task_id: OOMPAH-988
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9124f988919b1af1c551b3046845e3778f4aefe54755f8ff76b6d956ff95d818
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-10T06:42:56.887416+00:00'
    selected_ref: 2028162ed44c38137ac41b57d1286fe58e0d4ce7
    selected_sha: 2028162ed44c38137ac41b57d1286fe58e0d4ce7
    updated_at: '2026-08-10T06:43:15.321025+00:00'
  - version: 1
    audit_id: audit-6faade084e7b
    project_id: proj-14849f1b
    task_id: OOMPAH-988
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9124f988919b1af1c551b3046845e3778f4aefe54755f8ff76b6d956ff95d818
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-10T06:42:56.887416+00:00'
    selected_ref: 2028162ed44c38137ac41b57d1286fe58e0d4ce7
    selected_sha: 2028162ed44c38137ac41b57d1286fe58e0d4ce7
    updated_at: '2026-08-10T06:43:15.321053+00:00'
  attempt_history: []
---
## Summary

Live regression after deployed OOMPAH-980 on server revision 2dde7ad. OOMPAH-983 exact accepted head 2a10a77a32b2b38e11b78b3137e13d289dc866d9 has a durable passing make test gate in .oompah/quality_gates.json (169.47 seconds) and is contained in origin/main through merge commit 0b1b035c882ffc5f1fe411168b425f3eaf127bae. Its terminal Done audit nevertheless reran the complete suite (19,279 tests), and the following Merged audit launched a second complete suite. Root cause: Orchestrator._terminal_audit_quality_gate_evidence resolves issue_exact_head correctly after OOMPAH-980, but requires the mutable work branch to still resolve to that accepted head. Normal post-merge branch cleanup deletes the remote branch, so exact immutable gate evidence is rejected even though the accepted SHA is durably bound to the audit and contained in the target branch. OOMPAH-981 is another live post-landing audit exposed to the same failure. Implementation scope: add a narrow repository-backed post-integration authority path that accepts the exact persisted branch-gate result when the work branch is absent only if the audit target is a post-review terminal transition, the accepted head and immutable audit binding agree, and git proves the accepted head is contained in the authoritative target/default branch. Preserve the existing branch-head equality proof while a work branch exists. Never reuse for an advanced mismatching branch, missing/invalid accepted SHA, stale fingerprint/attempt, absent gate record, failed gate, unlanded/non-ancestor commit, unavailable target branch, or ambiguous repository state. Relevant code: oompah/orchestrator.py terminal-audit gate evidence and live reuse revalidation, terminal audit revision binding/dispatch context only if needed, and tests/test_quality_gate.py. Required tests: OOMPAH-983-shaped deleted branch plus exact accepted head contained in target reuses make test for Done and Merged; existing branch exact match still reuses; advanced branch remains fail-closed; deleted branch with non-ancestor remains full_gate_required; stale fingerprint/attempt and incompatible gate remain denied; live authority recheck preserves the same proof; no extra full-suite command launches. Acceptance: post-landing OOMPAH-983/OOMPAH-981-shaped audits reuse the exact authoritative gate without a redundant complete run, while every unlanded or ambiguous case remains fail closed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 05:31
---
Root cause reproduced from live OOMPAH-983 evidence: .oompah/quality_gates.json contains a passing exact make test result for accepted head 2a10a77 (169.47s), while the managed repository has neither local nor remote OOMPAH-983 refs and git proves 2a10a77 is an ancestor of origin/main. OOMPAH-980 fixed review_head selection but retained mutable work-branch equality as mandatory authority, so both post-review terminal stages fall back to full_gate_required after normal branch deletion. A narrow fix is in progress on branch OOMPAH-988: preserve the durable audit revision binding in the auditor contract, accept deleted-branch fallback only for Done/Merged from In Review with matching review head/ID and exact selected SHA, refresh the target ref, and require Git ancestry. Advanced branches, absent/ambiguous refs, mismatched bindings, and non-ancestors remain fail closed. Compile/diff checks pass; focused pytest is deferred while two authoritative full gates own the validation resource.
---
author: oompah
created: 2026-08-10 05:39
---
Implementation is pushed at exact head 2028162ed44c38137ac41b57d1286fe58e0d4ce7 after rebasing onto main through OOMPAH-984. Verification: 43 focused landing/gate-selection regressions passed; 157 auditor contract/bridge/API tests passed; post-rebase combined affected selection passed 193 tests; py_compile, git diff --check, terminal mutation scan, paranoid secret scan, gitleaks, private-key, merge-conflict, and large-file hooks passed. The repository-wide trailing-whitespace hook was skipped because it rewrites pre-existing unrelated whitespace throughout oompah/auditor.py; git diff --check passes for this patch. Independent exact-head review is running.
---
author: oompah
created: 2026-08-10 05:47
---
Independent exact-head review ACCEPTED 2028162ed44c38137ac41b57d1286fe58e0d4ce7 with no correctness blockers. The reviewer independently confirmed both OOMPAH-983 and OOMPAH-981 passing gate records, deleted local/tracking/remote source refs, and accepted-head ancestry on origin/main; all selected binding, review identity, source absence, target freshness/ancestry, live ABA, and fail-closed negative surfaces are covered.
---
author: oompah
created: 2026-08-10 05:47
---
Preserved immutable terminal-audit revision bindings and reuse exact passing branch gates after normal post-review branch deletion only when review identity, remote absence, and target ancestry all prove the same accepted head. Added fail-closed regression coverage; 193 post-rebase affected tests passed and independent exact-head review accepted.
---
author: oompah
created: 2026-08-10 06:33
---
Exact full branch gate passed at unchanged pushed head 2028162ed44c38137ac41b57d1286fe58e0d4ce7: make test completed with 19,306 passed, 7 skipped, 2 xfailed, 48 warnings in 1,376.55s. Worktree is clean, origin/OOMPAH-988 resolves to the same exact head, and ahead/behind is 0/0. Proceeding to protected PR CI against main through OOMPAH-982.
---
author: oompah
created: 2026-08-10 06:36
---
Branch quality gate passed for `2028162ed44c38137ac41b57d1286fe58e0d4ce7` using `make test` in 168.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-10 06:43
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-10 06:43
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: [REDACTED]
---
<!-- COMMENTS:END -->
