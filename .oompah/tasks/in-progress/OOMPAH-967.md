---
id: OOMPAH-967
type: bug
status: In Progress
priority: 1
title: Honor retained terminal provenance in canonical workflow decisions
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T18:04:59.855533Z'
updated_at: '2026-08-09T18:14:06.070750Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by the live OOMPAH-940 rollout at workflow snapshot generation 728: 68 exact-current workflow-managed integration_landing_refresh jobs for legacy Done tasks exhausted because exact landing evidence is unavailable. OOMPAH-871 already provides an authenticated project-owner terminal-provenance retain action for completed records that are intentionally historical, but the universal workflow fact/decision path ignores that durable authority and continues scheduling landing refreshes. Implementation scope: project the current validated provenance-suppression marker into canonical workflow facts; bind it to the exact project/task, schema, owner identity, and authority generation; make a Done task with a healthy retained marker terminal as provenance-only with no delivery effect or status mutation; make malformed/unreadable markers fail closed with a named operator action; ensure an owner-authorized new revision/generation restores ordinary workflow evaluation; and let the existing exact-publication retirement path supersede and retire prior exhausted landing-refresh authority. Do not add SQLite edits, generic mass overrides, or trust unvalidated tracker prose. Relevant files include oompah/orchestrator.py, oompah/workflow_facts.py or the terminal-audit fact adapter, oompah/work_decision.py, workflow runtime/liveness integration, and focused tests. Required tests: retained Done task produces a project/task/generation-bound terminal zero-job decision; incomplete, cross-task, malformed, or unreadable markers do not become delivery proof; new-revision authority resumes normal landing evaluation; an exact exhausted integration_landing_refresh row is retired after publication of the retained zero-job decision; restart preserves the result; unaffected Done tasks still require exact landing evidence. Acceptance: after deployment, apply the supported owner retain action only to the 68 currently exhausted legacy Done records, observe their exact old jobs retire without rerun, reach complete workflow liveness with current divergence=0 and current exhausted=0, pass make workflow-rollout-check, and close OOMPAH-940 without direct database edits or broad status overrides.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 18:05
---
Accepted for direct-owner implementation as the final live OOMPAH-940 rollout blocker.
---
author: oompah
created: 2026-08-09 18:14
---
Root cause and bounded recovery confirmed. The universal workflow fact source ignored OOMPAH-871's authenticated terminal-provenance marker, so historical Done records continued to schedule exact landing refreshes until exhaustion. Current implementation projects a project/task/generation/actor-bound marker into terminal-audit facts; retained Done records produce a terminal zero-job decision, malformed or status-conflicting markers fail closed to a named operator action, and a healthy new-revision marker resumes ordinary evaluation. The existing exact-publication retirement path is exercised end to end, including restart persistence. Live manifest: 6/68 already retained, 57/68 have durable applied owner overrides, OOMPAH-755 has exact ancestry, and OOMPAH-505/523/526/804 require the explicit owner decision that they are historical rather than a false landing claim. Validation: 474 focused provenance/decision/fact/integration/runtime/job tests pass; independent reviews are in progress.
---
<!-- COMMENTS:END -->
