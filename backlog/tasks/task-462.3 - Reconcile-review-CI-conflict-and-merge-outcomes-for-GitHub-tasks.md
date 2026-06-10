---
id: TASK-462.3
title: 'Reconcile review, CI, conflict, and merge outcomes for GitHub tasks'
status: In Progress
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 03:25'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-462.2
  - TASK-461.5
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - tests/test_orchestrator_merged.py
parent_task_id: TASK-462
priority: high
ordinal: 147000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update review polling and webhook-driven reconciliation so open PRs mark tasks In Review, failed CI marks Needs CI Fix, conflicts mark Needs Rebase or Needs Human, merged PRs mark Merged, and closed-unmerged PRs reopen or escalate with comments.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Default-branch and release-branch PR outcomes are reconciled explicitly.
- [ ] #2 Closed-unmerged reviews never leave tasks indefinitely In Review.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 03:10
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-10 03:18
---
Understanding: This task requires implementing review/PR status reconciliation. Key behaviors needed: (1) open PRs → In Review, (2) failed CI → Needs CI Fix, (3) conflicts → Needs Rebase or Needs Human, (4) merged PRs → Merged, (5) closed-unmerged PRs → reopen/escalate. Dispatched as CI Failure Fixer — will check for CI failures first, then implement what's missing. Modified files per task: oompah/orchestrator.py, oompah/server.py, tests/test_orchestrator_merged.py.
---

author: oompah
created: 2026-06-10 03:22
---
Discovery: The existing code handles some PR reconciliation but is missing: (1) webhook-driven In Review marking when PRs are opened/reopened, (2) periodic poll reconciliation for CI failures and merge conflicts on In Review tasks (YOLO-only today), (3) webhook-driven Merged marking for direct PR closes (only merge_group is handled). Will add: _reconcile_in_review_pr_outcomes() in orchestrator.py to mark Needs CI Fix/Needs Rebase based on reviews cache; webhook handlers in server.py for PR open→In Review and PR merged→Merged; tests in test_orchestrator_merged.py and test_server_webhooks.py.
---

author: oompah
created: 2026-06-10 03:25
---
Implementation: Added three features across orchestrator.py and server.py. (1) orchestrator._reconcile_in_review_pr_outcomes() — iterates In Review tasks against _reviews_cache; marks Needs CI Fix when PR ci_status==failed, Needs Rebase when has_conflicts==True and CI not failed; CI failure takes priority over conflicts; called from _do_merged_labels maintenance lane. (2) server._mark_task_in_review_from_webhook() — background thread handler for PR opened/reopened events; marks task In Review and writes review metadata. (3) server._label_task_merged_from_pr() — background thread handler for PR closed+merged events; marks task Merged. _handle_webhook_event now launches these threads for pull_request and Merge Request Hook events. Tests: 10 new tests in TestReconcileInReviewPrOutcomes and 7 new tests in TestWebhookInReviewReconciliation/TestWebhookMergedReconciliation. All 171 tests pass.
---
<!-- COMMENTS:END -->
