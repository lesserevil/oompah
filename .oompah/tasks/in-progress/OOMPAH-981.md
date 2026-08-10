---
id: OOMPAH-981
type: bug
status: In Progress
priority: 1
title: Route post-landing epic follow-ups to the live target branch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T02:42:39.740073Z'
updated_at: '2026-08-10T03:15:12.797567Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-980

Triggered by OOMPAH-980 under already-landed epic OOMPAH-940. OOMPAH-940's reviewed epic branch had already merged to main, but submitting the newly created follow-up OOMPAH-980 still selected the stale epic-OOMPAH-940 base and routed mergeable direct-main work to Needs Rebase. Scope: resolve the effective integration target for a child created after its parent epic has authoritatively landed; route that follow-up to the current live target branch or a supported addendum/recovery lane without mutating or reusing the stale epic branch; preserve existing shared and nested active-epic routing, exact submitted-head authority, dependency ordering, and fail-closed behavior when landing evidence is absent or contradictory. Relevant code includes submit/integration target resolution, parent epic landing evidence, queue record creation, and direct-main reconciliation. Required tests: active shared-epic child still targets the epic branch; landed parent follow-up targets the current default or immediate target; parent-landing race; pruned/stale epic refs; nested epic target; exact submitted head; restart/idempotence; and an already merged direct-main PR reconciles without false Needs Rebase. Acceptance: an OOMPAH-980-shaped submission enters the correct live integration path without a manual PR, rebase workaround, or terminal override; focused tests and the complete project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 02:58
---
Forward invariant added from the live parent decision: a service-authorized post-landing standalone child must project its accepted task branch and live target into EpicFactCollector. Otherwise the already-landed parent remains blocked on the stale epic branch even after the child review lands. Regression coverage now includes that parent rollup flow as well as submit routing.
---
author: oompah
created: 2026-08-10 03:15
---
Direct-owner implementation remains active on branch OOMPAH-981. End-to-end post-parent landing routing is implemented and expanded race/restart/direct-delivery regressions are being completed before review. No product blocker is outstanding.
---
<!-- COMMENTS:END -->
