---
id: OOMPAH-866
type: bug
status: Ready to Integrate
priority: 1
title: Honor canonical child mappings after direct epic conflict rebases
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T20:39:34.818552Z'
updated_at: '2026-08-06T21:35:59.897501Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-866
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f6fa104c55944a49b854bbec75c62de4274454d3c9988840d226afcba8e0b265
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T20:50:25.063281+00:00'
  matched_identifiers: []
  evidence: 'Project-owner forensic review found no active duplicate. OOMPAH-866 is
    a distinct regression of completed OOMPAH-757: direct epic conflict-rebase canonical
    evidence is persisted on helper records but not mapped to affected child landing
    validation, reproducing d3cc87e to 0321c898 and a false descendant OOMPAH-745
    block.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-06T20:50:25.063281+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: 'Project-owner forensic review found no active duplicate.
    OOMPAH-866 is a distinct regression of completed OOMPAH-757: direct epic conflict-rebase
    canonical evidence is persisted on helper records but not mapped to affected child
    landing validation, reproducing d3cc87e to 0321c898 and a false descendant OOMPAH-745
    block.'
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-866
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-866
  base_branch: epic-OOMPAH-763
  base_sha: a5d1973d043ff2375d56d89d0ea8bd5326e24f63
  head_sha: ee05a0ad8fbdf4459bf710a29a9926b088b70d10
  submitted_at: '2026-08-06T21:35:44.775334+00:00'
  updated_at: '2026-08-06T21:35:44.775334+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 3166
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 3166
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 3166
    cost_usd: 0.0
    recorded_at: '2026-08-06T20:41:56.235275+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-866__20260806T204102Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-866
    source_sha: 72cc4481c3eee5605345a4a36c3fe688149572b8
    completed_at: '2026-08-06T20:41:56.240837+00:00'
---
## Summary

Fix the shared-epic landing gate regression reproduced by OOMPAH-740 PR 731: child OOMPAH-741 original head d3cc87e was authoritatively conflict-rebased to canonical 0321c898 while preserving current-main validation telemetry, but child validation recognizes only ancestry or git-cherry patch equivalence and reports both OOMPAH-741 and descendant OOMPAH-745 as unlanded. During direct epic rebase, persist durable per-affected-child old range to canonical range evidence with project, epic, child, base, source, target, and generation fencing; consume and validate that evidence in _child_has_durable_landing_evidence and _child_landing_evidence_block_reason without accepting stale, tampered, foreign-epic, tree-only, or unverified mappings. Preserve original SHA provenance and do not require child-ref rewrites. Relevant code: oompah/orchestrator.py direct rebase/canonical landing evidence and shared-child landing validators; existing tests/test_canonical_landing_evidence.py and epic landing suites. Required tests: conflict-resolved direct epic rebase maps the affected child; a descendant shared child does not inherit a false unlanded ancestor; exact unchanged commits still use normal evidence; restart persists mapping; stale/tampered/wrong project or epic evidence fails closed; OOMPAH-740 d3cc87e to 0321c898 scenario allows the epic PR only when every child range is accounted for. Acceptance: PR 731 topology passes landing validation without rewriting child branches, while any genuinely missing child work still blocks merge with an actionable identity.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 20:40
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 20:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 20:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 3.2K out [3.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 21s
- Log: OOMPAH-866__20260806T204102Z.jsonl
---
author: oompah
created: 2026-08-06 20:42
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861, OOMPAH-862, OOMPAH-863, OOMPAH-864, OOMPAH-865. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
author: oompah
created: 2026-08-06 20:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 20:54
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 20:54
---
Understanding: trace direct epic rebase landing-evidence persistence and shared-child validation; implement canonical old-range to target mappings with project/epic/child/base/source/target/generation validation, preserve normal ancestry/cherry evidence, and add regression tests including restart and fail-closed cases.
---
author: oompah
created: 2026-08-06 20:55
---
Discovery: existing direct maintenance completion writes one epic-level CanonicalLandingEvidence record using base as both old range endpoints; child validators only inspect IntegrationRecord/queue ancestry or cherry equivalence. This lacks per-child project/epic/source/target/generation identity and explains the regression.
---
author: oompah
created: 2026-08-06 21:11
---
Implementation: added CanonicalChildLandingEvidence with project/epic/child identity, original base/source SHAs, canonical target range, deterministic generation, freshness, and fingerprint validation. Direct epic completion now records verified affected-child mappings in atomic service state; validators consume them only after normal ancestry/cherry checks and require exact scope generation, real commits, ancestry, and current container range proof. Child refs and original metadata are preserved.
---
author: oompah
created: 2026-08-06 21:16
---
Verification: focused canonical landing, parallel epic-child, terminal-audit, and worker submission suites pass (145 passed, 1 expected xfail). Compileall and git diff --check also pass.
---
author: oompah
created: 2026-08-06 21:19
---
Completion: direct epic rebases now persist project/epic/child-scoped, generation-fenced old-to-canonical child range mappings; validators consume only fresh, identity-matched, real-commit, current-ref-proven mappings. Original child SHAs and refs remain unchanged, restart restoration is covered, and the branch is pushed at ee05a0ad8.
---
author: oompah
created: 2026-08-06 21:19
---
Implemented durable canonical child landing mappings for direct epic conflict rebases with fail-closed validation and restart persistence; focused suites pass.
---
author: oompah
created: 2026-08-06 21:19
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 172
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 25m 27s
- Log: OOMPAH-866__20260806T205418Z.jsonl
---
author: oompah
created: 2026-08-06 21:20
---
Integration could not verify `epic-OOMPAH-763--task-OOMPAH-866`: epic worktree head 72cc4481c3eee5605345a4a36c3fe688149572b8 differs from the published epic head a5d1973d043ff2375d56d89d0ea8bd5326e24f63; refusing to reset a preserved recovery snapshot

Fetch the private branch, preserve its commits, push a clean current head, and submit it again.
---
author: oompah
created: 2026-08-06 21:20
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 21:20
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 21:21
---
Recovery/understanding: the prior implementation is present at ee05a0ad8 and the task branch now matches origin. I am revalidating canonical child evidence, shared-epic landing, restart/fail-closed cases, then will resubmit against the exact pushed head.
---
author: oompah
created: 2026-08-06 21:35
---
Completion: revalidated the pushed ee05a0ad8 implementation. Focused canonical/epic/parallel-child/merged/worker/terminal suites: 568 passed in 11:28; compileall, diff check, and check-secrets passed. git pull --rebase was up to date, push was up to date, and the worktree is clean.
---
author: oompah
created: 2026-08-06 21:35
---
Honor canonical child mappings after direct epic conflict rebases; focused suites and static checks pass at ee05a0ad8.
---
author: oompah
created: 2026-08-06 21:35
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 33
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 15m 17s
- Log: OOMPAH-866__20260806T212059Z.jsonl
---
<!-- COMMENTS:END -->
