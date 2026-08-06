---
id: OOMPAH-740
type: epic
status: In Progress
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
blocked_by: []
start_blocked_by: []
labels:
- rebase-requested
- merge-conflict
- epic:rebasing
assignee: null
created_at: '2026-08-03T22:55:28.610952Z'
updated_at: '2026-08-06T07:13:35.520112Z'
work_branch: epic-OOMPAH-740
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/731
review_number: '731'
review_head: null
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/731
oompah.review_number: '731'
oompah.work_branch: epic-OOMPAH-740
oompah.target_branch: main
oompah.agent_run_id: 963162d8-a3a6-4642-a3dc-e4fe284295fc
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
<!-- COMMENTS:END -->
