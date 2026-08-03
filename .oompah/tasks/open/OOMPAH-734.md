---
id: OOMPAH-734
type: bug
status: Open
priority: 1
title: Prevent auditor turn exhaustion after PASS from stranding terminal transitions
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T19:06:11.095695Z'
updated_at: '2026-08-03T19:09:40.018256Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: bef57ad9a792d097e5a56960af511f86d2370426c2d6472ae28549bd276dc6a3
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 04e9717b-14a7-4a10-add9-220e9a5094cc
  claim_owner: 8a58fb27-42d0-40cf-8dc2-70615b9783dc
  claimed_at: '2026-08-03T19:09:27.888753+00:00'
  claim_expires_at: '2026-08-03T19:39:27.888753+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: cf40d993-9162-4f24-8816-1de62175bc9a
---
## Summary

Triggered by: OOMPAH-729

Production regression observed on OOMPAH-729. Its first independent auditor reached the 100-turn ceiling after posting an Audit PASS — Done comment, but before the authoritative terminal result was committed. The task remained In Validation and the scheduler launched a redundant second auditor. An owner override was required to cancel that run and apply the already-supported terminal outcome.

Implementation scope:
- Reproduce an auditor reaching its configured turn ceiling after deciding PASS but before submitting the coordinator terminal result.
- Make the authoritative terminal-result commit occur before any human-readable PASS or FAIL comment, or otherwise reserve a non-starvable finalization path outside the model turn/tool budget.
- Ensure a provider exit, timeout, or policy denial cannot leave a misleading PASS comment while the durable audit remains In Progress.
- Preserve fail-closed authority: never infer a terminal result from comment text alone.
- Ensure a committed PASS atomically retires same-target/same-fingerprint sibling audits and prevents redispatch.
- Ensure an owner override or other authority revocation promptly retires the redundant auditor process and its persisted attempt.
- Add observability that distinguishes an uncommitted verdict/finalization failure from provider transport and auditor command-policy failures.

Required tests:
- Boundary test where the auditor consumes its final ordinary turn while deciding PASS and still commits the terminal result exactly once.
- Crash ordering tests proving commit-before-comment recovery is idempotent and that comment-before-commit cannot occur.
- Scheduler race test proving no second auditor launches after a committed PASS for the same target and fingerprint.
- Exit-before-commit test proving the task remains fail-closed with an actionable finalization alert and no misleading PASS comment.
- Authority-revocation test proving the active auditor is stopped and cannot later overwrite the terminal decision.
- Focused terminal coordinator, audit scheduler, agent lifecycle, and dashboard health tests; run make test.

Acceptance criteria:
- An auditor that reaches its normal turn ceiling after reaching a verdict cannot strand the task in In Validation.
- Dashboard comments and tracker state cannot disagree by showing PASS — Done while the durable result is incomplete.
- Duplicate auditor dispatch is prevented or automatically retired without operator intervention.
- Terminal authority, fingerprint fencing, audit history, and independent-candidate requirements remain intact.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 19:09
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
