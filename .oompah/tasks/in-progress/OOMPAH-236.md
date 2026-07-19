---
id: OOMPAH-236
type: task
status: In Progress
priority: null
title: Replace Release Delivery commit pagination with an item-centric release backlog
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
- needs:feature
assignee: null
created_at: '2026-07-19T00:33:24.455215Z'
updated_at: '2026-07-19T00:38:07.498191Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 27932a92-e8ba-4cc6-b49a-004830803fc5
oompah.task_costs:
  total_input_tokens: 25
  total_output_tokens: 6708
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 25
      output_tokens: 6708
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 25
    output_tokens: 6708
    cost_usd: 0.0
    recorded_at: '2026-07-19T00:37:51.087571+00:00'
---
## Summary

Problem
The Release Delivery overlay currently pages through individual main-branch commits. Its “Load next page” action is commit-history pagination, which does not match the operator workflow: choosing which completed tasks and epics should be delivered to one release branch.

Required behavior
- Require the operator to select one configured supported release branch before loading the backlog.
- Display one row per task or epic that has individually merged to the project default branch and is not already delivered to the selected release branch.
- A row represents the source task/epic, not each constituent commit. Show the identifier, title, source-main merge evidence, and current release-delivery state.
- Selecting one or more rows queues delivery of every associated source commit to the selected release branch through the existing release-delivery ledger and executor. Do not create child merge tasks.
- If an item is already queued, in progress, in review, blocked, or delivered to the selected branch, render that state on the row and prevent duplicate queueing.
- Remove the commit-history “Load next page” control from this primary workflow. The ordinary release backlog must load as a complete bounded list. If an implementation limit is necessary, use explicit search/filtering with an explanatory count, not cursor-based history pages.
- Preserve the ability to inspect item-level commit evidence in a details drawer; commits are subordinate detail, not top-level rows.
- Do not present unassociated direct-to-main commits as normal candidates in this item-centric view. If retained for diagnostics, show them in a clearly separate, non-primary section.

Implementation notes
Replace or adapt the current commit-inventory API and dashboard overlay. Reuse the project release-delivery ledger, ancestry checks, and delivery executor; do not rewrite delivery execution. Update plans/release-delivery-commit-inventory.md and docs/release-addendums.md to describe the item-centric backlog and remove commit-page terminology.

Tests
- Unit-test candidate derivation for merged tasks, merged epics, already-delivered items, active deliveries, and items with multiple associated commits.
- API tests verify a selected branch returns complete item rows with the required status/evidence and does not return a next cursor.
- Dashboard tests verify branch-first selection, no “Load next page” control, item-row rendering, duplicate-queue prevention, and queue request construction from associated commits.
- Regression-test that an item already present on the target by ancestry is not queueable.

Acceptance criteria
- An operator selecting release/0.11 sees a single understandable backlog of merged tasks and epics still absent from release/0.11.
- Each row can be queued once and creates the correct existing ledger delivery records for its associated commits.
- No commit-history pagination is visible in the primary Release Delivery workflow.
- Existing delivery states and historical evidence remain inspectable.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-19 00:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-19 00:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-19 00:35
---
Understanding: I am the Duplicate Investigator for OOMPAH-236. This issue requests replacing the Release Delivery commit-pagination model with an item-centric backlog (one row per task/epic, not per commit). I will now search for existing tasks that cover the same ground before any implementation begins.
---
author: oompah
created: 2026-07-19 00:37
---
Discovery: Duplicate screening complete for OOMPAH-236. No duplicate found.

Candidates reviewed:
- OOMPAH-192 (Merged): Epic 'Replace release-branch inspector with commit-centric release delivery' — this is the PREDECESSOR. It implemented the commit-centric model that OOMPAH-236 is now asking to replace. Not a duplicate; OOMPAH-236 supersedes it.
- OOMPAH-197 (Merged): 'Build the default-branch commit inventory service' — implements the commit inventory that OOMPAH-236 replaces.
- OOMPAH-198 (Merged): 'Expose the read-only release delivery inventory API' — the existing API OOMPAH-236 will adapt.
- OOMPAH-199 (Merged): 'Add commit-selection release delivery queue API' — the queue API OOMPAH-236 will reuse (not rewrite).
- OOMPAH-200 (Merged): 'Replace the Release branches overlay with Release delivery UI' — the commit-centric UI OOMPAH-236 will replace with item-centric.
- OOMPAH-208 (Merged): 'Exclude already-landed commits from release delivery targets' — a bug fix within the old model; OOMPAH-236 addresses the same concern via item-centric ancestry checks.
- OOMPAH-209 (Merged): 'Group tracker-only commits in release delivery inventory' — a grouping UX improvement within the old model; OOMPAH-236 goes further by making tasks/epics the primary row unit.
- OOMPAH-216 (Merged): 'Make Release Delivery show reconciled branch status and actionable retries' — added retry/state surface to the commit-centric model; OOMPAH-236 will carry this state display forward in the item-centric model.

Conclusion: OOMPAH-236 is a genuinely new task — it replaces the commit-centric design (shipped in OOMPAH-192 + follow-ups) with an item-centric backlog. No existing open or in-progress task covers this same scope.
---
author: oompah
created: 2026-07-19 00:37
---
Focus handoff: duplicate_detector

1. Outcome: OOMPAH-236 is NOT a duplicate. No existing task covers replacing the commit-centric release delivery model with an item-centric backlog. The closest candidates are all Merged predecessors that built the current commit-centric system (OOMPAH-192 epic and its children OOMPAH-197/198/199/200, OOMPAH-208, OOMPAH-209, OOMPAH-216).

2. Relevant files and evidence:
   - plans/release-delivery-commit-inventory.md — describes the current commit-centric design (what to replace/update per OOMPAH-236 impl notes)
   - docs/release-addendums.md — user-facing doc to update
   - The existing release delivery ledger, ancestry checks, and executor must be REUSED not rewritten
   - OOMPAH-192 children (OOMPAH-193–202, 206) implemented the current ledger, API, and UI
   - OOMPAH-209 (Merged) already handles tracker-only commit grouping — may interact with the new item-centric view's 'unassociated direct-to-main commits' section
   - OOMPAH-216 (Merged) added reconciled state display and retry controls — the item-centric UI should carry these forward

3. Remaining work:
   - Replace/adapt the commit inventory API to return item rows (one per task/epic) instead of commit rows
   - Replace the dashboard overlay with branch-first selection and item-row rendering
   - Add unit tests, API tests, and dashboard tests per the issue description
   - Update plans/release-delivery-commit-inventory.md and docs/release-addendums.md
   - Verify make test passes

4. Recommended next focus: feature (significant new behavior replacing existing commit-centric API + UI)
---
author: oompah
created: 2026-07-19 00:37
---
Agent completed successfully in 145s (6733 tokens)
---
author: oompah
created: 2026-07-19 00:37
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 53, Tool calls: 42
- Tokens: 25 in / 6.7K out [6.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 25s
- Log: OOMPAH-236__20260719T003531Z.jsonl
---
author: oompah
created: 2026-07-19 00:38
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
<!-- COMMENTS:END -->
