---
id: OOMPAH-179
type: task
status: In Progress
priority: 2
title: Reconcile release-addendum pull-request outcomes and controls
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-178
labels: []
assignee: null
created_at: '2026-07-13T02:35:55.903478Z'
updated_at: '2026-07-13T05:36:36.416020Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: f666b1cb-d09b-4d75-9975-0a1875b8abb4
---
## Summary

Read sections 6 and 8 of plans/release-branch-addendums.md. Add PR polling that changes an in_review addendum to merged only after its target PR is merged and records completion evidence. A closed-unmerged PR must remain nonterminal until explicit retry; retry may change blocked or closed-unmerged in_review to open without changing commits. Add archive support for open/blocked only. Implement the retry/archive API endpoints, transition validation, cache invalidation, and oompah-authored source-task comments for state changes and errors. Tests: merged/open/closed PR outcomes; retry and archive authorization/transition errors; immutable snapshots across retries; duplicate poll idempotency; and comments. Acceptance: lifecycle controls are explicit and no replacement PR is opened automatically after a close.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 05:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 05:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 05:20
---
Understanding: OOMPAH-179 is NOT a duplicate. Searched all 13 OOMPAH-172 epic children and other tasks. No other task covers PR polling (in_review→merged on PR merge, closed-unmerged handling), retry/archive API endpoints, or lifecycle controls. OOMPAH-178 covers execution (creating PRs), OOMPAH-177 covers queue claiming. OOMPAH-179 covers what happens AFTER a PR is created: polling its outcome, explicit retry/archive controls, and oompah-authored source-task comments for all state changes. Proceeding with implementation.
---
author: oompah
created: 2026-07-13 05:25
---
Discovery: OOMPAH-179 scope confirmed. Key existing code: oompah/release_addendum_schema.py (AddendumRepository.transition(), VALID_TRANSITIONS with in_review→merged and in_review→open already defined), oompah/release_addendum_executor.py (_post_source_comment, _find_existing_pr with PR state check), oompah/release_addendum_queue.py (AddendumRepository), oompah/server.py (POST /release-addendums at line 3331, GET at 3633, _api_cache.invalidate_prefix pattern, invalidate_release_branch_catalog). SCM.find_pr_for_branch returns ReviewRequest.state in {open, closed, merged}. Orchestrator._do_merged_labels at line 7711 has sweep pattern. Plan: (1) oompah/release_addendum_poller.py with poll_addendum_pr (merged→MERGED+comment, closed→in-place error update+comment, open→noop, idempotent); (2) POST /retry and /archive endpoints in server.py with 409 on invalid transition; (3) _reconcile_addendum_pr_outcomes_sweep in orchestrator._do_merged_labels; (4) tests for all outcomes, idempotency, snapshot immutability, comments, retry/archive errors.
---
author: oompah
created: 2026-07-13 05:36
---
Implementation: Created oompah/release_addendum_poller.py with:\n- poll_addendum_pr(): polls in_review addendum PR state; merged→MERGED+completed_at+comment; closed→error-field update+comment (no status change, no replacement PR); open/unknown→noop; idempotent; swallows SCM/tracker failures\n- _handle_merged(), _handle_closed(): per-state handlers with conflict-safe InvalidTransitionError handling\n- _update_addendum_evidence(): updates execution-evidence fields without status change (uses dataclasses.replace + repo.write)\n- _post_source_comment(): posts with author=oompah, swallows exceptions\n- CLOSED_UNMERGED_ERROR_PREFIX constant for idempotency sentinel\n\nAdded to oompah/server.py:\n- POST /api/v1/issues/{id}/release-addendums/{addendum_id:path}/retry — transitions blocked|in_review→open, clears lease fields, publishes wake-up event, invalidates cache, posts oompah comment; 409 for invalid transitions\n- POST /api/v1/issues/{id}/release-addendums/{addendum_id:path}/archive — transitions open|blocked→archived, posts oompah comment, invalidates cache; 409 for invalid transitions\n- Both use {addendum_id:path} to handle slash-containing IDs (e.g. FOO-10/release/1.0)\n- _load_addendum_for_control() and _invalidate_addendum_caches() helpers\n\nAdded to oompah/orchestrator.py:\n- _reconcile_addendum_pr_outcomes_sweep() sweep in _do_merged_labels(); skips no-repo-url/no-provider projects; catches per-addendum failures; calls poll_addendum_pr for each in_review addendum\n\nTests: 51 poller tests + 43 server control tests + 10 orchestrator tests = 104 new tests.
---
<!-- COMMENTS:END -->
