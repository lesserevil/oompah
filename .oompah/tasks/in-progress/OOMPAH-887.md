---
id: OOMPAH-887
type: task
status: In Progress
priority: null
title: Revalidate Done-child landing before Needs Human escalation
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T12:49:52.129482Z'
updated_at: '2026-08-07T22:37:16.714506Z'
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
  verdict: no_duplicate
  checked_at: '2026-08-07T13:05:11.677560+00:00'
  matched_identifiers: []
  evidence: Authoritative corpus review found related landed work (especially OOMPAH-632,
    OOMPAH-696, and OOMPAH-866), but no active duplicate. Those tasks cover candidate-ref
    refresh, durable integrated-SHA proof, and canonical rebase mappings. OOMPAH-887
    specifically covers a later target movement producing a mixed/stale generation
    between refresh and Needs Human escalation, reproduced live on OOMPAH-779; its
    single-generation revalidation and defer-on-refresh-failure acceptance criteria
    remain unimplemented.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-07T13:05:11.677560+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: Authoritative corpus review found related landed work (especially
    OOMPAH-632, OOMPAH-696, and OOMPAH-866), but no active duplicate. Those tasks
    cover candidate-ref refresh, durable integrated-SHA proof, and canonical rebase
    mappings. OOMPAH-887 specifically covers a later target movement producing a mixed/stale
    generation between refresh and Needs Human escalation, reproduced live on OOMPAH-779;
    its single-generation revalidation and defer-on-refresh-failure acceptance criteria
    remain unimplemented.
oompah.agent_run_id: e44f2ef8-503f-4bff-9311-fe4a7037a5af
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
author: oompah
created: 2026-08-07 13:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 13:03
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 11s
---
author: oompah
created: 2026-08-07 13:03
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-848, OOMPAH-849, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861, OOMPAH-862, OOMPAH-863, OOMPAH-864, OOMPAH-865, OOMPAH-866, OOMPAH-877, OOMPAH-878, OOMPAH-879, OOMPAH-880, OOMPAH-881, OOMPAH-882, OOMPAH-884, OOMPAH-885, OOMPAH-886. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
author: oompah
created: 2026-08-07 13:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-07 13:11
---
Agent failed: Epic worktree epic-OOMPAH-763 is dirty; drain or repair shared-mode work before dispatching private children. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-07 13:11
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 9s
---
author: oompah
created: 2026-08-07 13:18
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-07 13:18
---
Agent failed: Epic branch epic-OOMPAH-763 diverged from origin/epic-OOMPAH-763; reconcile both heads before dispatching more children. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-07 13:18
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 11s
---
author: oompah
created: 2026-08-07 13:20
---
Temporary owner sequencing claim 8fc0649fb1b64409baee48fb030929cb applied after two provider-free dispatch failures correctly reported that epic-OOMPAH-763 is dirty/diverged during OOMPAH-877's exact repair. This is not an implementation failure. Release the claim immediately after OOMPAH-877's exact CAS push so the server can implement OOMPAH-887 from the repaired epic head without retry churn.
---
author: oompah
created: 2026-08-07 22:07
---
Direct-owner takeover supersedes the old sequencing note: OOMPAH-877 is complete, but the operator subsequently directed that all remaining nonterminal Oompah work be claimed and implemented directly. Claim 8fc0649fb1b64409baee48fb030929cb is therefore intentionally retained; implementation will proceed in an isolated branch from the current OOMPAH-763 composition, with the OOMPAH-779 exact ancestry topology and stale-generation race covered before handoff.
---
author: oompah
created: 2026-08-07 22:37
---
Direct implementation complete on pushed branch OOMPAH-887-direct at exact commit 8bd96dd5389d6d3c13004f27365eb5f080fb8be6 (base 3a1928d6bb7d7b47a48a90a7d0e0a56e147bb96c). Done-child reconciliation now freezes one target/candidate remote advertisement, threads immutable commit IDs through durable, trusted-completion, canonical-mapping, and branch containment proofs, retries once when the generation moves, and revalidates immediately before both Merged and Needs Human mutations. Deterministic coverage includes the OOMPAH-779/OOMPAH-765/OOMPAH-763 topology, exact and patch-equivalent containment, restart from stale refs, both stale escalation and stale promotion movement races, genuine unlanded work, and refresh failure. Evidence: brokered focused suite 122 passed; python compilation and git diff checks passed; make check-secrets passed. Branch is clean and matches origin.
---
<!-- COMMENTS:END -->
