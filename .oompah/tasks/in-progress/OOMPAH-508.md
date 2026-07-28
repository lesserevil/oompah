---
id: OOMPAH-508
type: feature
status: In Progress
priority: 1
title: Run focused checks at handoff and one full quality gate per ready branch
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:06:08.389229Z'
updated_at: '2026-07-28T15:47:05.239353Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 8ff14fbc-cb6e-4168-b77e-4f4e6eb88f8b
oompah.work_branch: epic-OOMPAH-502
---
## Summary

Problem: every specialist focus currently runs the entire 12k-test suite because project instructions require make test before each commit. A multi-focus shared branch repeats the same four-minute gate several times, but Oompah can open the epic review without a single branch-head quality record after all children finish.

Implementation: introduce branch-head quality-gate evidence keyed by repository identity, target branch, work branch, head SHA, and configured command. Intermediate focus instructions require tests covering changed behavior plus relevant neighboring suites, not the full suite. When a standalone branch or complete epic branch becomes review-ready, run the configured full Makefile quality gate exactly once outside the scheduler event loop; cache PASS only for the exact head SHA and invalidate it on new commits/rebase/command changes. On failure, do not create a PR/MR; post concise failure evidence and route the task/epic to the existing CI-fix workflow. Keep the terminal auditor plan independent and preserve final review-readiness rechecks. Configuration belongs in .env/.env.example.

Tests: multiple focus handoffs on one unchanged branch cause zero full gates; readiness causes one; repeated ticks are idempotent; head changes invalidate; concurrent ticks claim once; nested epics and standalone tasks; pass/fail/timeout/restart recovery; scheduler HTTP responsiveness while tests run; GitHub/GitLab provider neutrality. Update AGENTS.md, generated integration instructions, WORKFLOW.md, and operator docs consistently.

Acceptance criteria: intermediate agents run focused checks; every review has one passing full gate for its exact head; failures cannot create reviews; no unchanged branch reruns the full suite.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:06
---
Claimed for manual implementation by the current Codex session. Held in Backlog while the shared epic branch is built so Oompah does not dispatch another agent; status will move to In Progress and Done as this session completes the slice.
---
author: oompah
created: 2026-07-28 15:36
---
Implementation started on epic-OOMPAH-502. Adding persistent branch-head quality-gate evidence at the review-creation boundary, changing worker guidance to focused checks, and covering idempotence, invalidation, failure, timeout, recovery, concurrency, and provider-neutral review flows.
---
author: oompah
created: 2026-07-28 15:46
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 15:46
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-28 15:47
---
Understanding: Dispatched as CI Failure Fixer on branch epic-OOMPAH-502. The branch has 6 commits ahead of main implementing the quality-gate feature (OOMPAH-505, drain/restart, stale storage, ACP model tiers, startup prompt compaction, duplicate detection fix). Will run make test to identify CI failures, then apply minimal fixes.
---
<!-- COMMENTS:END -->
