---
id: OOMPAH-1010
type: bug
status: Merged
priority: 1
title: Do not stage shared-epic children for invalid Merged audits
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T01:48:19.145541Z'
updated_at: '2026-08-11T08:08:45.738308Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: oompah-1007-shared-child-merged-staging
  request_fingerprint: 52ea41240b5c2fed7d8b1b7fbf99afb2a6a75ad0b9449b1e9acc47eaa65775ee
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-e78509ba3fc8
    project_id: proj-14849f1b
    task_id: OOMPAH-1010
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 409fc64ab0a6f89cc30823d849b4a9557291a05248aecfb7da1034e75f85a19e
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Protected PR #806 and hosted Python 3.11/3.12/3.13 gates are green; deployed
      build 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17 contains merge 62c3cda3ea602b614a3a3dfc92c66468b5c34a4b;
      independent audit verified that every exact reviewed branch change is patch-equivalent
      to or composition-equivalent with the protected merge and no unique branch changes
      remain.'
    created_at: '2026-08-11T08:08:22.292114+00:00'
    selected_ref: origin/OOMPAH-1010
    selected_sha: 65bf488993796b483ccf5351c0f80feac942b799
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1010
    target_state: Merged
    evidence_fingerprint: 409fc64ab0a6f89cc30823d849b4a9557291a05248aecfb7da1034e75f85a19e
    workflow_revision: null
    selected_ref: origin/OOMPAH-1010
    selected_sha: 65bf488993796b483ccf5351c0f80feac942b799
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-11T08:08:33.433179+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-1007

Live reproduction after PR #805 merged OOMPAH-1007 directly to main: the forge webhook commented 'Queued for terminal transition to Merged' and moved the shared-epic child into In Validation. Its first exact audit correctly passed the topology-valid Done stage, then a second Merged-stage auditor was launched; the callback was fenced stale, and an owner Merged override was rejected because parent epic OOMPAH-940 has not landed. This creates unnecessary auditor work and contributed tracker churn to OOMPAH-1009. Scope: when protected delivery lands a shared-epic child while its parent epic remains nonterminal, resolve and stage the topology-valid child terminal target (Done) instead of blindly staging Merged from the PR target. Preserve true standalone/root task Merged handling, nested epic topology, direct-main delivery evidence, webhook idempotency, Done-to-Merged ordering when the parent later lands, and exact terminal audit authority. Relevant code: merged pull-request webhook staging, review/workflow terminal target resolution, TaskTransitionService topology guard, and terminal coordinator chain construction. Required tests: merged PR for a shared child with nonterminal parent stages one Done audit and no Merged audit; parent landing later permits normal rollup; root/standalone tasks still stage Merged; nested parent ambiguity fails closed; duplicate webhook delivery is idempotent. Acceptance: OOMPAH-1007-like delivery reaches Done after one audit with no invalid Merged callback or owner workaround, while OOMPAH-940 remains the sole parent responsible for final Merged topology.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 02:16
---
Claimed for direct-owner implementation in the current systemic workflow recovery program. Work will be isolated on this task branch, covered by focused regression tests, independently reviewed, fully gated, pushed, and submitted through the protected delivery path.
---
author: oompah
created: 2026-08-11 02:34
---
Implementation is committed and pushed at exact head c71b7f57d500fefa9343c72b3c42fe2d62fa6582. Landed standalone/root and nested-epic reviews target Merged, while shared ordinary children target Done; unreadable or invalid parent topology fails closed across direct and merge-group webhooks, durable review recovery, and decision projection. Validation passed 1,317 unique focused tests plus a 68-test changed-path rerun, mutation scan 21/21, secret scan, compile, diff, and commit hooks. Independent exact-head review is active before protected integration.
---
author: oompah
created: 2026-08-11 03:05
---
Independent re-review accepted exact head 65bf488993796b483ccf5351c0f80feac942b799. The follow-up closes the topology ABA window by re-resolving the terminal target from the freshly locked issue; direct and merge-group race regressions fail closed without staging an audit. The combined four-fix branch passed 827 changed-path tests.
---
author: oompah
created: 2026-08-11 08:08
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Protected PR #806 and hosted Python 3.11/3.12/3.13 gates are green; deployed build 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17 contains merge 62c3cda3ea602b614a3a3dfc92c66468b5c34a4b; independent audit verified that every exact reviewed branch change is patch-equivalent to or composition-equivalent with the protected merge and no unique branch changes remain.
---
author: oompah
created: 2026-08-11 08:08
---
Delivered through protected PR #806 and verified on healthy deployed build 5e2288c47738bcf8b441d0f6f71bbc2ab878ac17.
---
<!-- COMMENTS:END -->
