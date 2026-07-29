---
id: OOMPAH-472
type: feature
status: Done
priority: 1
title: Collect target-landing evidence for Merged audits
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-471
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:12.977543Z'
updated_at: '2026-07-29T01:56:51.597466Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ee2de8e4b05f7994081f063147b5bd36b38754fc06a14d8f81fb617cb98259c8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:21:00.553916+00:00'
  matched_identifiers: []
  evidence: "My duplicate investigation is complete. Here is the summary:\n\n**Search\
    \ coverage:**\n- All `.oompah/tasks/` states: `open` (OOMPAH-281), `backlog` (OOMPAH-282),\
    \ `merged` (OOMPAH-271\u2013280), `archived` (200+ tasks, OOMPAH-1\u2013276)\n\
    - Patterns searched: `MergedEvidence`, `evidence.*collector`, `target.landing`,\
    \ `landing.*evidence`, `audit`, `completion.fingerprint`, `fingerprint`, `merge.*commit`,\
    \ `stranded.*commit`, `wrong.*target`, `Merged.*audit`\n- Source tree (plans/,\
    \ docs/, entire repo): same patterns \u2014 zero matches\n\n**Active tasks reviewed:**\n\
    - **OOMPAH-281** (Open): Containerized GitHub Actions runner using Podman \u2014\
    \ completely unrelated to audit evidence collection.\n- **OOMPAH-282** (Backlog):\
    \ UnicodeEncodeError in state_branch_migration \u2014 completely unrelated.\n\n\
    No archived or merged task covers `MergedEvidenceCollector`, target-landing evidence,\
    \ completion fingerprints, or any aspect of the Merged audit evidence collection\
    \ described in OOMPAH-472. The referenced blockers OOMPAH-471 and OOMPAH-457 do\
    \ not appear in the task files at all (they are likely in the live tracker above\
    \ the current file-commit range), confirming this is a fresh feature on an active\
    \ epic.\n\n---\n\nFocus handoff: duplicate_detector  \nDuplicate preflight verdict:\
    \ no_duplicate  \nMatches: none  \nEvidence: Exhaustive search of all `.oompah/tasks/`\
    \ states (open, backlog, merged, archived \u2014 200+ tasks) and the full repository\
    \ source tree found zero matches for any of the key concepts in OOMPAH-472: `MergedEvidenceCollector`,\
    \ target-landing evidence, completion fingerprint, stranded commits, wrong-target\
    \ merge detection, or Merged-audit evidence collection. The only two active (non-terminal)\
    \ tasks \u2014 OOMPAH-281 (GitHub Actions runner) and OOMPAH-282 (latin-1 UnicodeEncodeError)\
    \ \u2014 cover entirely unrelated topics. OOMPAH-472 is a unique, first-of-its-kind\
    \ feature task."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 8b27b52d-3400-4831-b724-408181bee5d4
oompah.work_branch: epic-OOMPAH-458
oompah.task_costs:
  total_input_tokens: 13
  total_output_tokens: 3514
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 13
      output_tokens: 3514
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 13
    output_tokens: 3514
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:21:00.553010+00:00'
---
## Summary

Implementation scope

Build a read-only MergedEvidenceCollector. Require a current passed Done audit for the same completion fingerprint. Resolve the source branch/review, intended target branch, reviewed source SHA, merge commit/result, target HEAD, CI status, and commit/content containment. Detect wrong-target merges, open or closed-unmerged reviews, failed CI, stale branch tips, deleted branches with authoritative merged-review evidence, and unique commits stranded outside the target. For epic and nested-epic rollups, include child Done audit IDs and prove the complete branch chain landed on the configured target.

Tests

Use Git and fake SCM fixtures for correct landing, wrong target, open review, closed without merge, failed/pending CI, squash/rebase/merge commits, deleted branch, source advanced after review, stranded commits, shared epic, and nested epic target chains. Run focused tests and make test.

Acceptance criteria

A Merged audit can distinguish actual correct-target landing from tracker labels or stale review history alone and reports precise evidence for every failure mode.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:18
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-29 01:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:21
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 27, Tool calls: 19
- Tokens: 13 in / 3.5K out [3.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 44s
- Log: OOMPAH-472__20260729T011820Z.jsonl
---
author: oompah
created: 2026-07-29 01:44
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 01:44
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-29 01:44
---
Understanding: This task (OOMPAH-472) requires building a MergedEvidenceCollector that verifies actual target-landing for Merged audits. I'm in the CI Failure Fixer role. Let me examine what exists on this branch and what tests are failing.
---
author: oompah
created: 2026-07-29 01:50
---
Discovery: OOMPAH-471 (DoneEvidenceCollector) is complete and tests pass. OOMPAH-472 requires creating merged_evidence_collector.py and its tests from scratch. The feature must: (1) require a passed Done audit, (2) resolve source branch/review/SHA/merge commit/target HEAD/CI/containment via SCMProvider, (3) detect wrong-target merges, open/unmerged reviews, failed CI, stale tips, deleted branches, stranded commits, (4) support epic rollups with child audit chains. Implementing now.
---
author: oompah
created: 2026-07-29 01:56
---
Implementation: Created oompah/merged_evidence_collector.py with MergedEvidenceCollector and FakeSCMProvider, plus tests/test_merged_evidence_collector.py with 61 tests. All tests pass. Key design: requires a passed Done audit, resolves review/SHA/CI/containment via SCM protocol, detects all 10+ failure modes (wrong target, open/unmerged reviews, failed CI, stale tips, stranded commits, etc), supports epic/nested-epic rollups. Uses get_review_head_sha to distinguish the SHA at review time from the current branch HEAD, enabling stale-tip detection.
---
author: oompah
created: 2026-07-29 01:56
---
Verification: 61 tests pass in tests/test_merged_evidence_collector.py. Related suites (done_evidence_collector, terminal_audit, landing_gate, independently_merged, auditor_contract, terminal_audit_enforcement, terminal_audit_metadata) all pass — 89 tests total, no regressions.
---
author: oompah
created: 2026-07-29 01:56
---
Completion: Delivered MergedEvidenceCollector (oompah/merged_evidence_collector.py) with 61 passing tests. The collector distinguishes actual correct-target landing from tracker labels alone by: (1) requiring a passing Done audit, (2) resolving the PR/MR and its CI status, (3) checking commit containment via git, (4) detecting 10+ precise failure modes. Epic rollups validate child branch chains. FakeSCMProvider enables hermetic testing of all failure modes without network access. Branch pushed to epic-OOMPAH-458.
---
author: oompah
created: 2026-07-29 01:56
---
Implemented MergedEvidenceCollector: read-only collector for Merged audits that verifies actual target-branch landing via SCM review state, CI status, and git containment. 61 tests covering all specified failure modes (wrong target, open/unmerged review, failed/pending CI, stale tip, stranded commits, deleted branches, epic rollups, nested epic chains). Branch epic-OOMPAH-458 updated.
---
<!-- COMMENTS:END -->
