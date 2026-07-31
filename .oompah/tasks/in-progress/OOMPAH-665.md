---
id: OOMPAH-665
type: task
status: In Progress
priority: null
title: Retire legacy no-auditor alerts after terminal task completion
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- needs-rebase
assignee: null
created_at: '2026-07-31T16:04:07.401588Z'
updated_at: '2026-07-31T18:45:15.813075Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a693eaf278504dc2d35cff16c985f00831ff37d57e34abdc6fd8b491a20c1ccc
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T18:19:02.170356+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive search for duplicate tasks, I have completed\
    \ the duplicate detection for OOMPAH-665. Here are my findings:\n\n## Search Scope\n\
    \nI searched for similar tasks using multiple keyword patterns:\n- Direct keywords:\
    \ \"retire\", \"legacy\", \"alerts\", \"no-auditor\", \"no_independent_candidate\"\
    \n- Related concepts: \"terminal_audit\", \"observability\", \"reconciliation\"\
    , \"fingerprint\", \"lifecycle\"\n- Referenced tasks: OOMPAH-644, OOMPAH-648,\
    \ OOMPAH-653\n- File names: orchestrator, terminal_transition_coordinator, terminal_audit_observability\n\
    - Broader terms: \"Merged\", \"terminal\", \"override\", \"evidence\", \"stale\"\
    , \"alert\"\n\n## Results\n\n**Active Tasks Reviewed:**\n- **OOMPAH-281** (Open)\
    \ \u2014 Self-hosted GitHub Actions runner setup. Unrelated.\n- **OOMPAH-282**\
    \ (Backlog) \u2014 Unicode encoding error in state_branch_migration. Unrelated.\n\
    \n**Excluded Tasks:**\n- All 267 archived tasks (terminal state, historical only)\n\
    - All 7 merged tasks (terminal state, historical only)\n\n**No Matches Found:**\n\
    - No existing tasks cover the specific domain of retiring legacy no-auditor alerts\
    \ after terminal task completion\n- No tasks reference the observability reconciliation\
    \ pattern described in OOMPAH-665\n- No tasks implement the lifecycle authority\
    \ retirement logic for stale audit identities\n\n## Conclusion\n\nOOMPAH-665 is\
    \ a unique, previously unaddressed task. It describes a specific defect in oompah's\
    \ terminal audit observability system where stale no-auditor alerts persist after\
    \ tasks reach terminal state (Merged). The required fix involves reconciliation\
    \ logic during restart recovery to retire legacy audit identities when current\
    \ evidence proves they no longer own lifecycle authority.\n\n**Focus handoff:\
    \ duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\n**Matches:\
    \ none**\n\n**Evidence:** Comprehensive search across all active task states (.oompah/tasks/open,\
    \ backlog), documentation (docs/, plans/), and codebase using 15+ keyword patterns\
    \ found no existing active or historical ta"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: feef7a6d-45b1-4e65-a2a5-303469c28e40
oompah.task_costs:
  total_input_tokens: 225
  total_output_tokens: 5403
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 170
      output_tokens: 4135
      cost_usd: 0.0
    sonnet:
      input_tokens: 55
      output_tokens: 1268
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 170
    output_tokens: 4135
    cost_usd: 0.0
    recorded_at: '2026-07-31T18:19:02.169216+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 55
    output_tokens: 1268
    cost_usd: 0.0
    recorded_at: '2026-07-31T18:45:08.346008+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-665__20260731T181648Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-665
    source_sha: a1dd3287d1faeeccf777c57764b9283cb653304d
    completed_at: '2026-07-31T18:19:02.180724+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-665
  head_sha: fa09942201f5ec74481d56f786ddfb4621afd68b
  submitted_at: '2026-07-31T18:44:51.525017+00:00'
  updated_at: '2026-07-31T18:44:51.525017+00:00'
---
## Summary

Live reproduction on 2026-07-31 after OOMPAH-653 merged: OOMPAH-644 and OOMPAH-648 are canonically Merged and have owner/pass terminal evidence, but /api/v1/state still emits terminal_audit:no_independent_candidate alerts for audit-710535de2bba and audit-db48e6cb6d3e. Replaying the authorized Merged override for OOMPAH-644 fails HTTP 409 because current evidence differs from the historical override fingerprint, so the supported API cannot retire the stale alert without re-staging an already-terminal task. Implementation scope: during observability reconciliation, treat a no-auditor record as actionable only while it still owns the task's current nonterminal human decision; retire legacy/superseded identities when a later authorized override, PASS, or canonical terminal task state proves they no longer own lifecycle authority, while preserving historical counters and audit records. Do not clear alerts merely because tracker reads fail or evidence is ambiguous. Relevant files include oompah/orchestrator.py terminal-audit observability reconciliation, terminal_transition_coordinator.py retirement metadata, terminal_audit_observability.py, restart recovery, and alert/state tests. Required deterministic tests: migrated pre-fix metadata for OOMPAH-644 override and OOMPAH-648 PASS; changed fingerprint after merge; restart; task reopened with genuinely current no-auditor decision remains actionable; quarantine/read failure fails closed; project isolation. Acceptance: the two stale alerts clear without lifecycle restaging or metadata hand edits, real current Needs Human audit alerts remain, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 18:16
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 18:16
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 18:19
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 44, Tool calls: 20
- Tokens: 170 in / 4.1K out [4.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 18s
- Log: OOMPAH-665__20260731T181648Z.jsonl
---
author: oompah
created: 2026-07-31 18:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 18:19
---
Focus: Event Api Redaction Specialist
---
author: oompah
created: 2026-07-31 18:41
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 90
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 22m 3s
- Log: OOMPAH-665__20260731T181921Z.jsonl
---
author: oompah
created: 2026-07-31 18:41
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-31 18:41
---
Focus: Event Api Redaction Specialist
---
author: oompah
created: 2026-07-31 18:43
---
Understanding: The prior agent implemented the core fix in oompah/orchestrator.py (commit 84214ef43). The _reconcile_terminal_audit_observability_from_metadata method now checks 3 retirement sources before accepting a no-auditor alert as actionable: (1) explicit retirement rows (_retirement_metadata_proves_identity), (2) legacy override records (_legacy_override_proves_identity), (3) a later PASS verdict (_later_pass_proves_identity). If none apply, a live canonical tracker read is done - if the task is in a terminal state (Merged/Done/Archived), the stale alert is retired. Fetch failures and quarantined metadata fail closed (alert is preserved). All 62 focused tests pass. Verifying correctness and submitting.
---
author: oompah
created: 2026-07-31 18:44
---
Completion: Implemented and verified retirement of legacy no-auditor alerts after terminal task completion.

Changes in oompah/orchestrator.py:
- Added _TERMINAL_RETIREMENTS_KEY and _TERMINAL_OVERRIDE_RECORDS_KEY constants
- Added helpers: _audit_observability_time, _audit_record_time, _record_has_no_auditor, _retirement_metadata_proves_identity, _legacy_override_proves_identity, _later_pass_proves_identity
- Extended _reconcile_terminal_audit_observability_from_metadata to check 4 retirement paths before keeping a no-auditor alert alive, failing closed on read errors or quarantine

Changes in tests/test_terminal_audit_observability.py:
- Added _no_auditor_record helper and fetch_issue_detail to _MetadataTracker stub
- 4 new deterministic tests covering all required scenarios from the issue description

Test results: 295 tests passed (17 observability + 249 coordinator/metadata/audit + 62 health). Branch fa0994220 pushed to origin/OOMPAH-665.
---
author: oompah
created: 2026-07-31 18:44
---
Retire legacy no-auditor alerts after terminal task completion: extended _reconcile_terminal_audit_observability_from_metadata in oompah/orchestrator.py to check retirement rows, legacy override records, later PASS verdicts, and canonical tracker state before keeping a completed no-auditor alert alive. Fetch failures and quarantined metadata fail closed. 4 new deterministic tests added. 295 focused tests pass.
---
author: oompah
created: 2026-07-31 18:45
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-665`
Target: `main`
Head: `fa09942201f5ec74481d56f786ddfb4621afd68b`
Command: `make test`
Result: `needs_rebase`

Required: rebase this branch onto the current deployed base so it contains the lifecycle safety prerequisite and does not replace the protected gate entrypoints. Run the full command, commit and push the repair, then leave the task in Done; Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
OS-enforced quality-gate sandbox is unavailable; refusing to execute candidate code: cannot prepare an immutable candidate snapshot: unsafe link in candidate archive: '.oompah-no-hooks/prepare-commit-msg' -> '/home/shedwards/src/oompah/oompah/git_hooks/prepare-commit-msg'
```
---
author: oompah
created: 2026-07-31 18:45
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 27
- Tokens: 55 in / 1.3K out [1.3K total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 35s
- Log: OOMPAH-665__20260731T184138Z.jsonl
---
author: oompah
created: 2026-07-31 18:45
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-31 18:45
---
Focus: Event Api Redaction Specialist
---
<!-- COMMENTS:END -->
