---
id: OOMPAH-887
type: task
status: Open
priority: null
title: Revalidate Done-child landing before Needs Human escalation
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T12:49:52.129482Z'
updated_at: '2026-08-07T13:02:29.770455Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4bfc7a4793eddc7d2c72bcd997c6cd3662c69bebde2381b05f16da880b32ca0c
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 0785bfa1-8872-4315-b620-28b6133594dd
  claim_owner: 0c3fdd32-3af4-41c2-89eb-bba40d25c9aa
  claimed_at: '2026-08-07T13:02:25.763311+00:00'
  claim_expires_at: '2026-08-07T13:32:25.763311+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

Live false escalation on OOMPAH-779 at 2026-08-07 12:32 UTC: the task was audited Done on exact commit 40e46bf8e41c and shares parent epic OOMPAH-765's branch. OOMPAH-765's accepted merge/audit records target epic-OOMPAH-763, and 40e46bf8e41c is now an exact ancestor of origin/epic-OOMPAH-763, yet _mark_epic_merged moved OOMPAH-779 to Needs Human with a stale claim that the commit was unlanded. Implementation scope: make Done-child landing reconciliation use one exact refreshed target/candidate ref generation; detect target movement or stale ancestry evidence before emitting recovery instructions; retry/recompute from durable integration, parent merge/audit, and current remote ancestry rather than persisting Needs Human from an obsolete snapshot. Cover shared child work_branch equal to the parent epic branch and nested epic targets. Preserve fail-closed escalation for genuinely unlanded commits and failed authoritative refreshes. Relevant code: orchestrator._mark_epic_merged, _child_has_durable_landing_evidence, _child_landing_evidence_block_reason, target/candidate ref refresh, and nested epic landing records. Required tests: exact O779 topology; target advances between refresh and block-reason computation; restart after stale snapshot; exact and patch-equivalent containment; genuinely unlanded child; refresh failure defers without Needs Human. Acceptance: a proven-contained Done child cannot be moved to Needs Human due to a stale/mixed Git snapshot, and each escalation cites evidence from the same current generation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 12:50
---
In-flight workaround applied: project-owner terminal override restored OOMPAH-779 to Done only after exact merge-base ancestry proof for 40e46bf8e41c in origin/epic-OOMPAH-763 and parent audit evidence. No branch was mutated.
---
<!-- COMMENTS:END -->
