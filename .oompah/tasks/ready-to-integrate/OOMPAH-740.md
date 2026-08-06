---
id: OOMPAH-740
type: epic
status: Ready to Integrate
priority: 0
title: Make dashboard alerts compact, truthful, and non-blocking
parent: null
children:
- OOMPAH-741
- OOMPAH-742
- OOMPAH-743
- OOMPAH-744
- OOMPAH-745
- OOMPAH-755
- OOMPAH-761
- OOMPAH-762
- OOMPAH-857
blocked_by: []
start_blocked_by: []
labels:
- rebase-requested
- merge-conflict
- epic:rebasing
assignee: null
created_at: '2026-08-03T22:55:28.610952Z'
updated_at: '2026-08-06T20:35:01.060387Z'
work_branch: epic-OOMPAH-740
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/731
review_number: '731'
review_head: 46e5857a9ad886e5cd4647cac496bf6ce29eb276
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/731
oompah.review_number: '731'
oompah.work_branch: epic-OOMPAH-740
oompah.target_branch: main
oompah.agent_run_id: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-740
  base_branch: main
  head_sha: 46e5857a9ad886e5cd4647cac496bf6ce29eb276
  submitted_at: '2026-08-06T19:55:16.110555+00:00'
  updated_at: '2026-08-06T19:55:16.110555+00:00'
oompah.task_costs:
  total_input_tokens: 45
  total_output_tokens: 5514
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 45
      output_tokens: 5514
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 45
    output_tokens: 5514
    cost_usd: 0.0
    recorded_at: '2026-08-06T08:44:39.453301+00:00'
oompah.review_head: 46e5857a9ad886e5cd4647cac496bf6ce29eb276
---
## Summary

The main dashboard currently lets warnings and health panels consume the browser viewport before the Kanban board. The production screenshot captured on 2026-08-03 showed a raw EXOCOMP-147 rebase transcript twice, terminal-audit facts in both the global alert list and a dedicated health panel, a full-width branch-gate panel for routine state, and healthy repository telemetry below it. Some rendered facts had already recovered in the authoritative server snapshot.

This epic extends rather than duplicates OOMPAH-666, which fixed bottom reachability; OOMPAH-691 through OOMPAH-695, which added sequenced WebSocket convergence; and OOMPAH-735, which classifies integration failures under active recovery.

Implementation scope:
- Establish a shared contract separating current operator-actionable faults from workflow progress, healthy status, historical diagnostics, and automatically recovering conditions.
- Present actionable alerts once in a compact, collapsed alert center with bounded height and details on demand.
- Prevent raw multiline command output from entering headers or always-visible banners while retaining sanitized diagnostics in task or alert details.
- Make every alert-derived DOM region atomically reflect the latest authoritative state so recovered facts disappear without refresh.
- Preserve accessibility, keyboard operation, responsive behavior, board horizontal and vertical scrolling, and complete diagnostics.

Relevant code includes oompah/templates/dashboard.html, alert producers and health snapshot builders in oompah/, WebSocket state reconciliation in oompah/server.py and dashboard JavaScript, and focused tests under tests/.

Acceptance criteria:
- At common desktop viewport sizes the board remains immediately visible and usable even when several alerts exist.
- One underlying condition has one always-visible representation.
- Only a current condition requiring operator action is styled and positioned as a warning or error.
- Normal queued, running, retrying, recovered, intentional-denial, and healthy states do not displace the board.
- Alert summaries are single-line and bounded; full sanitized context remains available on demand.
- An authoritative snapshot removes or reclassifies stale alert UI without a manual refresh.
- Focused regression suites and make test pass on the exact review-ready heads.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 07:09
---
Branch quality gate passed for `b08a12057afed4e7af5080e7e47522eed16dc2ce` using `make test` in 429.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-06 07:10
---
YOLO: Merge conflict detected on MR #731. Rebase `epic-OOMPAH-740` onto main and resolve conflicts.
---
author: oompah
created: 2026-08-06 07:10
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-06 07:10
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-08-06 07:11
---
Understanding: this pass is limited to rebasing epic-OOMPAH-740 onto origin/main, preserving every existing epic commit while reconciling conflicts with current main. I will inspect both conflict sides, run focused dashboard alert/state tests, force-push with lease, verify the exact post-push diff and branch status, then submit the rebased head.
---
author: oompah
created: 2026-08-06 07:11
---
Discovery: the first conflict is in Orchestrator._serialize_state. Current main added validation-resource health/status, while OOMPAH-741 added quality-gate facts plus normalization of the combined dashboard alert contract. Both are independent and required, so the resolution keeps validation resource telemetry/actionability and feeds quality-gate, credential, auth-health, and stored alerts through normalize_alerts exactly once.
---
author: oompah
created: 2026-08-06 07:13
---
Implementation: rebased all eight branch-specific dashboard commits onto current origin/main. The sole content conflict was resolved by preserving main's validation-resource snapshot/degraded-health additions alongside the epic's aggregated quality-gate alerts and normalize_alerts presentation boundary. Three OOMPAH-760 patches were skipped only because git verified patch-equivalent versions already exist in main; git cherry confirms the eight unique epic patches remain.
---
author: oompah
created: 2026-08-06 07:15
---
Verification: focused dashboard alert/contract/safety/credential/full-sync/scroll/recovery plus terminal-audit validation-resource suites pass: 71 passed in 11.12s. The directly affected Makefile setup contract also passes: 14 passed in 0.36s. Initial attempts were blocked by the managed validation shim targeting a read-only lease path; rerunning with the provisioned Python 3.12 environment and real /usr/bin Node executed the tests successfully. No product changes were made beyond conflict resolution.
---
author: oompah
created: 2026-08-06 07:16
---
Completion: rebased epic-OOMPAH-740 onto current origin/main, reconciled the dashboard-state conflict without dropping branch-specific work, and force-pushed exact head 4cdcc7e6e4f2f13087bce5942edf6a19821b9979. Remote and local heads match; status is clean/up to date; the review diff is 19 expected dashboard/alert/docs/test files with eight unique epic commits and no whitespace errors. Focused verification: 71 dashboard/health tests plus 14 setup-contract tests passed.
---
author: oompah
created: 2026-08-06 07:16
---
Rebased epic onto origin/main, preserved all eight unique dashboard-alert commits, reconciled validation-resource health with normalized alert state, passed 85 focused tests, and force-pushed verified head 4cdcc7e6e.
---
author: oompah
created: 2026-08-06 07:16
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 40
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 52s
- Log: OOMPAH-740__20260806T071051Z.jsonl
---
author: oompah
created: 2026-08-06 08:23
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-06 08:23
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-08-06 08:41
---
Understanding: this pass is limited to rebasing epic-OOMPAH-740 onto origin/main. On inspection, HEAD (03087ebf2 — includes OOMPAH-857) is already a direct linear descendant of origin/main (f2b319c11); \`git rebase origin/main\` reports 'Current branch epic-OOMPAH-740 is up to date.' The 9 epic commits and 20 expected dashboard/alert/docs/test files are preserved. I will run the focused dashboard alert/contract/safety/credential/full-sync/scroll/recovery + terminal-audit + setup-contract suites, then submit the current HEAD as-is (no force-push required since no rewrite occurred).
---
author: oompah
created: 2026-08-06 08:43
---
Verification: branch head 03087ebf2 is already a linear descendant of origin/main tip f2b319c11 — \`git rebase origin/main\` reports 'Current branch epic-OOMPAH-740 is up to date.' No conflicts, no rewrites, no force-push required. Focused suites (test_alert_safety, test_auth_health, test_dashboard_alert_center, test_dashboard_alert_contract, test_dashboard_alert_experience, test_dashboard_alert_safety, test_dashboard_credential_warning, test_dashboard_full_sync_atomic_replacement, test_dashboard_vertical_scroll, test_integration_retry_alert_recovery, test_makefile_setup, test_terminal_audit_health, test_terminal_audit_health_api) all pass: 171 passed in 13.72s. Diff vs origin/main is 20 expected dashboard/alert/docs/test files across 9 epic commits (OOMPAH-741, 742×3, 743, 744, 745×2, 857).
---
author: oompah
created: 2026-08-06 08:43
---
Completion: rebase pass on epic-OOMPAH-740 verified idempotent. Local and remote branch heads match at 03087ebf2fb2e0c3ba3bca5cc11fcbdfc3196bd0, a direct descendant of origin/main f2b319c11. No conflict resolution, no rewrite, no force-push was needed — the previous rebase already reconciled OOMPAH-741 quality-gate/normalize_alerts with main's validation-resource additions. 9 epic commits and 20 dashboard/alert/docs/test files preserved. Focused verification: 171 tests passed.
---
author: oompah
created: 2026-08-06 08:43
---
Rebase pass verified idempotent: epic-OOMPAH-740 HEAD 03087ebf2 is already a linear descendant of origin/main f2b319c11 with 9 epic commits and 20 files preserved. No conflicts, no force-push required. Focused suites (dashboard alert center/contract/experience/safety/credential/full-sync/scroll, alert_safety, auth_health, integration retry recovery, terminal_audit_health, makefile_setup) pass: 171 tests in 13.72s.
---
author: oompah
created: 2026-08-06 08:44
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Claude/opus]
- Turns: 0, Tool calls: 27
- Tokens: 45 in / 5.5K out [5.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 21m 3s
- Log: OOMPAH-740__20260806T082342Z.jsonl
---
author: oompah
created: 2026-08-06 19:55
---
Repaired blocked PR #731 exact CI failure: the Chrome DOM browser regression now has a narrow 35s pytest bound around its existing 30s subprocess kill bound, while the global timeout remains 5s; removed nine trailing-whitespace failures. Independent review accepted, the exact failing browser test passes, check-secrets and diff checks pass. Pushed exact PR head 46e5857a9ad886e5cd4647cac496bf6ce29eb276.
---
author: oompah
created: 2026-08-06 20:34
---
Branch quality gate passed for `46e5857a9ad886e5cd4647cac496bf6ce29eb276` using `make test` in 650.8s. Review creation may proceed.
---
<!-- COMMENTS:END -->
