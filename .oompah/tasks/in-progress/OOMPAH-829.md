---
id: OOMPAH-829
type: bug
status: In Progress
priority: 1
title: Migrate legacy equivalent Done-override fingerprints for structural maintenance
  tasks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T13:24:24.014858Z'
updated_at: '2026-08-05T18:43:52.466169Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1551768186f6e7b315b12d3550594c1936f9f224777cfb8422e99a4316fd63d5
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T18:25:26.053098+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active peer task in the authoritative corpus describes\
    \ this migration. Closest tasks OOMPAH-156, OOMPAH-162, and OOMPAH-165 are terminal\
    \ and address different fingerprint-deduplication or epic-merge behaviors.\nFocus\
    \ handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \n\
    Matches: none\n\nEvidence: No active peer task in the authoritative corpus describes\
    \ this migration. Closest tasks OOMPAH-156, OOMPAH-162, and OOMPAH-165 are terminal\
    \ and address different fingerprint-deduplication or epic-merge behaviors."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d3fabe44-0203-4ac9-96ea-01f088528f3a
oompah.task_costs:
  total_input_tokens: 48324
  total_output_tokens: 274
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 48324
      output_tokens: 274
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 48324
    output_tokens: 274
    cost_usd: 0.0
    recorded_at: '2026-08-05T18:25:26.042207+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-829__20260805T181841Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: duplicate_detector
    source_branch: OOMPAH-829
    source_sha: b53bdbc77c7a50d332a97096ebc85d7923280854
    completed_at: '2026-08-05T18:25:26.100920+00:00'
---
## Summary

Triggered by: OOMPAH-825

Live acceptance failure after deploying OOMPAH-825 on exact main 7978ec91b5532784c5dd6f18bc028954fd3696a9: OOMPAH-662 repaired from Merged to Done, but OOMPAH-660 remains Merged with lifecycle_repair_not_applied. OOMPAH-660 is the original OOMPAH-663 fingerprint-canonicalization reproduction. Its current integrated issue fingerprint and original integration-staged Done audit are ab40139d2035 at exact integrated SHA 793bcc7969d39634dab560ed0a10b9dcad7a9716, while its applied authorized Done override and duplicate no-auditor request carry legacy normalized/API fingerprint 62954f9b5fdc. OOMPAH-825's live-shaped test incorrectly modeled the override as already equal to the current fingerprint, so the promised 660 repair cannot occur. Implementation scope: add a bounded, explicit legacy-equivalence migration for structurally Done-only direct epic maintenance rows. Reconstruct both known canonical snapshot shapes from durable integration metadata (integration-staged integrated base/head/contributor shape and legacy normalized API/work-branch shape); accept an applied Done override only when its digest equals one reconstructed shape, the current digest equals the other, exact project/task/target/authorized/applied fields match, immutable integrated SHA/branch evidence is unchanged, current state is Merged, and the Merged validator still rejects it as Done-only under the project lock. Persist the equivalence/migration version before the one Done write, then retire only the exact child's incompatible Merged metadata. Never accept arbitrary fingerprint drift, comment/reason text, missing integration evidence, CI-fix/merge-conflict tasks, retired/superseded overrides, or SCM outage. Relevant code: terminal_audit.py canonical fingerprint variants/history from OOMPAH-663; terminal_audit_enforcement.py lifecycle authority and locked repair; live OOMPAH-660 metadata. Required tests: exact production-shaped OOMPAH-660 ab401↔62954 pair repairs once; OOMPAH-662 current-match control; one-field changes to integrated SHA, base branch, task identity, target, override authority/application, or structural classification fail closed; restart/crash intent recovery and cross-project isolation. Acceptance: OOMPAH-660 alone moves Merged to Done exactly once without manual task/ledger edits, row completes/reconciled and stays idempotent, unrelated historical overrides remain rejected, lifecycle warning converges clear, focused fingerprint/enforcement/coordinator tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 18:18
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-05 18:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 18:25
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 48.3K in / 274 out [48.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 7m 2s
- Log: OOMPAH-829__20260805T181841Z.jsonl
---
author: oompah
created: 2026-08-05 18:29
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-05 18:29
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-05 18:30
---
Understanding: Treating this as a CI repair on the existing OOMPAH-829 branch. I will inspect the current review head and actual failing job logs, reproduce the failure, apply the smallest covered fix, run focused project checks, then push and verify the rerun before submission.
---
author: oompah
created: 2026-08-05 18:36
---
Discovery: No PR or Actions run exists for OOMPAH-829; the branch is a clean origin/main head, so the reported live acceptance case is the concrete failure. In terminal_audit_enforcement.py, _lifecycle_terminal_authorities requires an applied override to equal compute_issue_evidence_fingerprint(), which rejects OOMPAH-660's durable legacy digest. I inspected the read-only native task metadata and reproduced the exact pair from the same issue/integration record: canonical integrated ab40139d20357c96... versus legacy work-branch 62954f9b5fdcde92.... The two shapes differ only by the OOMPAH-729 integrated canonicalization (base/integrated SHA plus task-branch contributor versus work-branch/head SHA).
---
author: oompah
created: 2026-08-05 18:43
---
Implementation: Added an explicit integrated-evidence fingerprint-variant reconstruction in terminal_audit.py and a v1 legacy Done-override equivalence fence in terminal_audit_enforcement.py. Only one active/applied, schema-valid Done override with exact project/task/target/authorized fields and the reconstructed legacy digest can qualify; current evidence must equal the reconstructed integrated digest and the task must remain a non-CI/non-conflict direct epic rebase helper. Under the project lock, the Merged conflict is revalidated, the complete equivalence/integration intent is durably checkpointed before the Done write, and restart recovery re-derives the marker before finalizing only the exact child's incompatible Merged metadata.
---
<!-- COMMENTS:END -->
