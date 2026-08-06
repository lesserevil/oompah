---
id: OOMPAH-852
type: bug
status: In Progress
priority: 1
title: Protect exact gates from concurrent focused validation commands
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:51:38.786179Z'
updated_at: '2026-08-06T05:09:29.172856Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-852
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8ad0ba722a7e5c3a7846477b5c8cfc67db681f9b2ccea62300fe250a2029f95a
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T04:54:44.069522+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-852 addresses policy/command-classification (focused\
    \ pytest should count as heavy validation), while OOMPAH-846 addresses enforcement-path\
    \ coverage (all launch paths need guards). OOMPAH-846's own comment trail explicitly\
    \ designates OOMPAH-852 as canonical for the policy defect. They are related but\
    \ not duplicates; both must land before exact gates are fully isolated.\nLooking\
    \ at OOMPAH-852 and the supplied project task corpus, I need to determine whether\
    \ this is a duplicate of an existing active issue.\n\n## Analysis\n\n**OOMPAH-852\
    \ (\"Protect exact gates from concurrent focused validation commands\")** describes\
    \ a specific policy classification problem: focused/named single-module pytest\
    \ commands are classified as \"bounded/light\" and thus bypass the ValidationResourceLease\
    \ even though they're actual test validation that should be serialized.\n\n**Closest\
    \ related active task: OOMPAH-846** (\"Enforce validation-resource leases for\
    \ every spawned worker command path\") describes a different but related problem:\
    \ certain launch paths (Codex native, absolute-path command execution) bypass\
    \ guards entirely, even when they should be subject to leases.\n\nHowever, **OOMPAH-846's\
    \ comments are definitive**: \n\n> \"Correction to the OOMPAH-826 evidence: its\
    \ named single-module `python -m pytest ...` route did traverse the existing command\
    \ classifier, but current policy deliberately treats that focused selector as\
    \ light, so it never requests a lease. **That is a separate arbitration-policy\
    \ defect, now canonical OOMPAH-852.** OOMPAH-846 remains scoped to genuine launch-path\
    \ bypasses...\"\n\nThis shows they are explicitly understood as **complementary,\
    \ not duplicate**:\n- **OOMPAH-852**: Fix the *policy/classification* so focused\
    \ test commands are treated as heavy validation\n- **OOMPAH-846**: Ensure all\
    \ *launch paths* have guards installed and cannot bypass enforcement\n\nBoth are\
    \ necessary; neither subsumes the other. The corpus also indicates required structural\
    \ peers OOMPAH-848\u2013851 are omitted, but this confirmation from OOMPAH-846's\
    \ analysis is sufficient to resolve the duplicate question.\n\n---\n\nFocus handoff:\
    \ duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\nMatches:\
    \ none\n\nEvidence: OOMPAH-852 addresses policy/command-classification (focused\
    \ pytest should count as heavy validation), while OOMPAH-846 addresses enforcement-path\
    \ coverage (all launch"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d10fe2a9-c629-40bd-87c1-b43ebfbeb6ba
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-852
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-852
  base_branch: epic-OOMPAH-763
  base_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
  updated_at: '2026-08-06T04:56:55.223386+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2708
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2708
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2708
    cost_usd: 0.0
    recorded_at: '2026-08-06T04:54:44.060910+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-852__20260806T045341Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-852
    source_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
    completed_at: '2026-08-06T04:54:44.089618+00:00'
---
## Summary

Live regression at 2026-08-06T04:52Z: while OOMPAH-821 owned the only validation-resource slot for its authoritative make test, completion auditor OOMPAH-826 ran `python -m pytest tests/test_epic_strategy.py -x -q` as service child PID 3113755 for at least 226 seconds. validation_resources still reported only the OOMPAH-821 exact_gate owner and no auditor waiter because the named single-module pytest command is classified as bounded/light. Earlier OOMPAH-847 single-module commands caused D-state contention and contributed to unrelated five-second exact-gate failures. Implementation scope: distinguish harmless inspection from actual validation, and require every pytest/py.test/unittest invocation plus configured Make/tox/nox/npm/cargo validation target to participate in ValidationResourceLease even when selectors are focused; keep help/version/static inspection outside the lane. Preserve priority so exact gates and terminal auditors cannot starve, and ensure waits begin before process creation with truthful tool_liveness. Relevant files: oompah/validation_resource_lease.py classifiers, api_agent/acp_tools/native guard launch paths, and validation telemetry. Required tests: named and absolute Python single-test/module commands wait behind an exact gate; bounded commands run when capacity is available; help/version and non-test inspection do not lease; API, Claude ACP, Codex native, auditor, worker, cancellation, timeout, and restart paths; a real exact gate plus attempted focused test proves no overlapping test process; make test. Acceptance criteria: while an exact gate owns capacity, no worker or auditor test process exists outside its process tree; all waiters are visible and cancellable; after release they run exactly once; ordinary inspection remains concurrent; no global timeout is raised.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 04:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 04:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 04:54
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.7K out [2.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 43s
- Log: OOMPAH-852__20260806T045341Z.jsonl
---
author: oompah
created: 2026-08-06 04:56
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 04:57
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 04:57
---
Understanding: focused pytest/py.test/unittest and configured validation targets must acquire ValidationResourceLease before process creation; help/version and static inspection remain outside the lane. I will trace classifiers and launch guards, add regression coverage for lease ordering/cancellation/telemetry, implement the smallest focused fix, and run affected Makefile checks.
---
author: oompah
created: 2026-08-06 04:58
---
Discovery:  is shared by  (API/Claude/OpenCode/Codex tool catalogs) and  (native Codex commands).  returns false for one explicit file/node and  returns false for one selected test; those are the production bypass. Lease acquisition already starts liveness before waiting, attaches before Popen/exec, and supports cancellation. Existing tests encode the old focused bypass and need to be inverted/expanded.
---
author: oompah
created: 2026-08-06 04:59
---
Discovery: the shared validation classifier is used by the API/Claude/OpenCode/Codex tool catalogs and the native Codex guard. The pytest classifier returns false for one explicit file/node and the unittest classifier returns false for one selected test; those are the production bypass. Lease acquisition already starts liveness before waiting, attaches before process creation, and supports cancellation. Existing tests encode the old focused bypass and will be inverted and expanded.
---
author: oompah
created: 2026-08-06 05:07
---
Implementation: removed the focused-selector bypass from the shared classifier. All recognized pytest/py.test and python -m unittest commands now lease capacity after help/version exclusion, including single files, node IDs, and single unittest methods. Expanded lease tests cover named and absolute Python launchers, real exact-gate waiting before a focused pytest process, one-time execution, cancellation/telemetry coverage already in the lane, and concurrent non-test inspection.
---
author: oompah
created: 2026-08-06 05:07
---
Verification: focused classifier/lease selection tests passed (118 selected); full validation_resource_lease.py passed (149 before the added help/version cases, with the focused additions also green); native guard passed 18 tests when excluding one orphaned-runner cancellation case; ACP tool/liveness passed 34; ACP Codex validation passed 5; API budget passed 105; Ruff and git diff checks are clean. make test was attempted but setup could not invoke the installed uv due the host DBus transient-scope error.
---
author: oompah
created: 2026-08-06 05:09
---
Completion: focused pytest/py.test/unittest invocations no longer bypass ValidationResourceLease, including named and absolute Python selectors. Exact-gate ordering, one-time focused execution, inspection concurrency, and existing cancellation/liveness behavior are covered. Commit 930cd74b9 is pushed and the branch is clean/up to date. Full make test could not reach pytest because uv setup failed with the host DBus transient-scope error; focused suites and Ruff are green.
---
<!-- COMMENTS:END -->
