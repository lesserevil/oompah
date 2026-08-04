---
id: OOMPAH-750
type: bug
status: Ready to Integrate
priority: 1
title: Make stalled-task watchdog prefer current evidence over handoff wording
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T00:46:06.960272Z'
updated_at: '2026-08-04T01:56:47.258783Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: de09fa5b7e244e1be1585a6fb3ce8f55415afaf2edb7900a917d67eaa2eca6ae
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T00:48:42.362254+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The stalled-task watchdog evidence-preference bug is\
    \ specific and not covered by any task in the corpus. All 34 similarity candidates\
    \ address different concerns: epic/task workflow improvements, release delivery\
    \ infrastructure, dashboard UI, error deduplication, tracker robustness, and recovery\
    \ mechanics. No existing task describes using comment wording as proof of task\
    \ blockage or the evidence-ordering problem that OOMPAH-750 targets. This is a\
    \ unique bug fix work item.\n**Understanding the duplicate screening task:**\n\
    \nOOMPAH-750 describes a specific bug in the stalled-task watchdog where it incorrectly\
    \ classifies tasks as `human_blocked` based solely on the presence of handoff-syntax\
    \ comments, even when current evidence (merged PRs, passing gates, resolvable\
    \ branches, technical failures) clearly shows the task is actionable. The fix\
    \ requires the watchdog to evaluate current tracker/audit/branch/CI/provider evidence\
    \ *before* considering comment wording, and never allow comment wording alone\
    \ to prove human blockage.\n\n**Reviewing the supplied task corpus:**\n\nI've\
    \ systematically reviewed all 34 non-terminal similarity candidates and the core\
    \ tasks in the corpus:\n\n- **OOMPAH-156\u2013212** (Archived): These address\
    \ error deduplication, UI controls, intake normalization, epic workflows, release-addendum\
    \ infrastructure, dashboard filtering, and recovery mechanics. None describe watchdog\
    \ classification logic or evidence-preference issues.\n- **OOMPAH-10, OOMPAH-12**:\
    \ Tracker sync robustness and native task creation; not watchdog-related.\n- **OOMPAH-1,\
    \ OOMPAH-2, OOMPAH-18, OOMPAH-20**: CI/release/docs fixes; unrelated to watchdog\
    \ classification.\n- **OOMPAH-100**: Webhook error (archived as duplicate of OOMPAH-58);\
    \ unrelated.\n\nNo task in the corpus addresses:\n1. Stalled-task watchdog decision\
    \ logic\n2. Handoff-comment misinterpretation as proof of human blockage\n3. Preference\
    \ of current evidence (merged PRs, CI state, branch state) over comment wording\n\
    4. False positive human_blocked classifications causing recovery failures\n\n\
    The bug is narrowly scoped to watchdog maintenance telemetry and is not described\
    \ by any existing open or recently-closed task.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: The\
    \ stalled-task watchdog evidence-preference bug is specific and not covered by\
    \ any task in the corpus. All 34 similarity candidates address different concerns:\
    \ epic/task workflow improvements"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1312
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1312
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1312
    cost_usd: 0.0
    recorded_at: '2026-08-04T00:48:42.361821+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-750__20260804T004746Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-750
    source_sha: 4ea94b151a09758c57a93c8710c05f28a49bcc2a
    completed_at: '2026-08-04T00:48:42.364373+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-750
  head_sha: 92bf56563a2803a4a3df0e146739634da6caa48a
  submitted_at: '2026-08-04T01:06:32.087031+00:00'
  updated_at: '2026-08-04T01:06:32.087031+00:00'
---
## Summary

Triggered by: OOMPAH-736

Live reproduction: the 2026-08-04 stalled-task watchdog classified OOMPAH-736 and EXOCOMP-130 as human_blocked with the sole evidence that a recent comment contained an explicit question or human handoff. OOMPAH-736 already had merged PR 692, a passing full gate, and an implementation head on main; EXOCOMP-130 had a resolvable canonical epic branch and a technical terminal-audit resolver failure. The required Needs Human handoff syntax was mistaken for proof of a continuing human dependency, so the watchdog took no recovery action. Implementation scope: classify from current tracker, audit, branch, review, CI, and provider evidence before using comment wording; distinguish a required handoff comment from an unresolved human decision; recognize superseded questions and machine-remediable technical blockers; remain fail closed when evidence is ambiguous. Record the decisive evidence and why any question is still current. Relevant code is oompah/stalled_task_watchdog.py plus orchestrator evidence collection and maintenance telemetry. Required tests: merged PR plus stale handoff becomes actionable; missing audit branch with canonical ref is technical rather than human; genuinely unanswered product or authority question remains human_blocked; stale versus newer comments; provider failures; ambiguous SCM state; idempotent restart. Acceptance criteria: handoff wording alone can never prove human_blocked; stronger current evidence safely recovers or accurately classifies the task; genuine human decisions remain untouched.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 00:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 00:47
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 00:48
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 6s
- Log: OOMPAH-750__20260804T004746Z.jsonl
---
author: oompah
created: 2026-08-04 00:49
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 00:49
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-04 00:49
---
Understanding: The watchdog must classify from current tracker, audit, branch, review, CI, and provider evidence before relying on comment wording. I will trace the evidence pipeline, add regressions for stale handoffs, technical blockers, genuine human decisions, stale/new comments, provider/SCM ambiguity, and idempotent restart, then run focused checks and submit the branch.
---
author: oompah
created: 2026-08-04 00:50
---
Discovery: The current classifier gives any recent question or handoff wording immediate human_blocked precedence, and run_watchdog_audit supplies only status plus comments. This explains the live false negatives; I am mapping existing Issue/tracker/audit/provider APIs before changing the evidence contract.
---
author: oompah
created: 2026-08-04 01:01
---
Implementation: Added WatchdogEvidence normalization and precedence-aware classification. Current merged review/audit pass/target-head evidence reopens safely; provider failures, missing audit branches with resolvable canonical refs, and ambiguous SCM state become technical insufficient_evidence; only the newest explicit product/authority question remains human_blocked. Orchestrator now collects tracker metadata, reviews/merged branches, branch heads, CI, and provider health.
---
author: oompah
created: 2026-08-04 01:04
---
Verification: Focused watchdog tests pass: 90 passed. Adjacent SCM, orchestrator tick telemetry, and terminal-audit metadata suites pass: 346 passed. Syntax compilation and git diff --check also pass. make setup could not create the task venv because the environment's astral-uv helper failed with a DBus transient-scope error, so tests ran with the existing Python runtime and importlib mode.
---
author: oompah
created: 2026-08-04 01:05
---
Verification update: Final focused run passes (90 tests), and the adjacent SCM/orchestrator/terminal-audit run passes (346 tests). Both were rerun after the final precedence and audit-envelope fixes.
---
author: oompah
created: 2026-08-04 01:06
---
Completion: Delivered and pushed commit 92bf56563. The watchdog now prioritizes current review/audit/branch/CI/provider evidence, distinguishes technical ambiguity from human decisions, honors newest comment timestamps, and remains idempotent across restarts. Focused and adjacent verification is green (90 + 346 tests); branch is clean and tracks origin/OOMPAH-750.
---
author: oompah
created: 2026-08-04 01:06
---
Prefer current tracker, SCM, audit, CI, and provider evidence over stale handoff wording; preserve genuine human decisions and fail closed on technical ambiguity. Verified with 90 focused and 346 adjacent tests.
---
author: oompah
created: 2026-08-04 01:07
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 110
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 38s
- Log: OOMPAH-750__20260804T004934Z.jsonl
---
author: oompah
created: 2026-08-04 01:56
---
Branch quality gate passed for `92bf56563a2803a4a3df0e146739634da6caa48a` using `make test` in 411.6s. Review creation may proceed.
---
<!-- COMMENTS:END -->
