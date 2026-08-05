---
id: OOMPAH-740
type: epic
status: Open
priority: 1
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
- epic:stale
assignee: null
created_at: '2026-08-03T22:55:28.610952Z'
updated_at: '2026-08-05T04:29:30.197543Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
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

