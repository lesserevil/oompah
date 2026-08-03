---
id: OOMPAH-716
type: bug
status: In Progress
priority: 1
title: Do not exhaust auditor policy budget on read-only awk and sed inspection
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T03:02:02.962763Z'
updated_at: '2026-08-03T03:04:28.266794Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ca6711b3db90a70ee9ccb0f22c07a68e76eaacdbcd18aa40230fb994cd5dc834
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T03:04:07.271503+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** The project task corpus contains only OOMPAH-716 in\
    \ an active state (Open). All 175 peer tasks are archived or completed. Among\
    \ the archived tasks, none address the specific problem of classifying read-only\
    \ `awk` and `sed` commands as recoverable validation responses in the auditor\
    \ policy boundary. This is a fresh bug that emerged from OOMPAH-714 terminal-audit\
    \ evidence and requires dedicated implementation. No active duplicate exists.\n\
    # Duplicate Investigation: OOMPAH-716\n\nI am investigating whether OOMPAH-716\
    \ is a duplicate of an existing active task by examining the provided project\
    \ task corpus.\n\n## Investigation Findings\n\n**Scope of Review**: The task corpus\
    \ contains 176 task entries (OOMPAH-1 through OOMPAH-175, plus current OOMPAH-716).\n\
    \n**Active Tasks**: Only **OOMPAH-716** has status \"Open\". All other 175 tasks\
    \ have terminal status: Archived (165 tasks), Done, or Merged.\n\n**Exclusion\
    \ of Terminal Tasks**: Per the instructions, I exclude all archived/terminal tasks\
    \ as duplicate targets. A completed task is historical context, not an active\
    \ duplicate.\n\n**Topic Coverage**:\n- OOMPAH-716 addresses a specific ACP auditor\
    \ policy issue: read-only `awk` and `sed` inspection commands exhausting the fatal\
    \ denial budget\n- The relevant code areas are: `oompah/auditor.py`, `oompah/authority_boundary.py`,\
    \ `oompah/acp_tools.py`, `oompah/api_agent.py`, and orchestrator policy-denial\
    \ accounting\n- Archived related tasks (OOMPAH-160, OOMPAH-162, OOMPAH-163) address\
    \ other orchestrator and epic-workflow bugs, not auditor policy classification\n\
    - No other task corpus entry\u2014archived or otherwise\u2014describes the problem\
    \ of auditors consuming the fatal denial budget on demonstrably read-only shell\
    \ inspection commands\n\n---\n\nFocus handoff: duplicate_detector\n\nDuplicate\
    \ preflight verdict: no_duplicate\n\nMatches: none\n\n**Evidence:** The project\
    \ task corpus contains only OOMPAH-716 in an active state (Open). All 175 peer\
    \ tasks are archived or completed. Among the archived tasks, none address the\
    \ specific problem of classifying read-only `awk` and `sed` commands as recoverable\
    \ validation responses in the auditor policy boundary. This is a fresh bug that\
    \ emerged from OOMPAH-714 terminal-audit evidence and requires dedicated implementation.\
    \ No active duplicate exists."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 5e361a50-38cf-4471-9c2f-d96fc394de45
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1325
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1325
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1325
    cost_usd: 0.0
    recorded_at: '2026-08-03T03:04:07.270294+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-716__20260803T030345Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-716
    source_sha: fc79579d42968c99a1130275dd40b5cc84c89526
    completed_at: '2026-08-03T03:04:07.282323+00:00'
---
## Summary

Triggered by: OOMPAH-714

Triggered by OOMPAH-714 Done-audit attempt #1 at 2026-08-03 02:57-02:59 UTC (log OOMPAH-714__20260803T025707Z.jsonl). The deployed OOMPAH-713 behavior correctly returned a recoverable validation response for a grep expression, but equally read-only single commands `awk 'NR>=7790 && NR<=7900' oompah/orchestrator.py` and `sed -n '7790,7900p' oompah/orchestrator.py` were treated as fatal policy denials. The Opus auditor exhausted its denial budget and rotated after 2m23s despite making no mutation attempt. A second candidate continued, so completion was not stranded, but this wastes auditor capacity and can still exhaust all candidates under repeated tool-choice variance.

Implementation scope:
- Classify demonstrably read-only but unsupported inspection commands as recoverable validation responses that do not consume the fatal auditor policy-denial budget; they do not need to be executed.
- Cover at least non-mutating awk range/print and sed print-only forms, while keeping awk system()/write primitives, sed -i/-e write forms, output redirection, shell escape, process control, and state-changing git fail-closed and fatal.
- Keep prompt/tool guidance steering auditors to search_files and bounded read_file, and make the validation response name those alternatives.
- Ensure candidate rotation, terminal-audit health, and transport counters distinguish repeated local tool-policy incompatibility from provider failure.

Relevant code: oompah/auditor.py, oompah/authority_boundary.py, oompah/acp_tools.py, oompah/api_agent.py, oompah/orchestrator.py policy-denial accounting, auditor prompts/tool catalogs, and terminal-audit health classification.

Required tests:
- Replay the exact OOMPAH-714 awk and sed commands and prove neither invokes the fatal denial handler nor rotates the candidate.
- Prove the auditor can recover with search_files/read_file and submit an accepted verdict.
- Verify awk system()/redirection, sed -i, chained mutation, shell escape, and state-changing git remain fatal.
- Verify no launch/transport alert is recorded for recoverable validation, while genuine provider failures still are.

Acceptance criteria:
- Replaying OOMPAH-714 attempt #1 reaches submit_audit_result without candidate rotation solely because of the read-only awk/sed requests.
- No write-capable command is admitted.
- Focused authority-boundary, auditor-contract, backend tool, orchestrator denial-budget, and terminal-audit health tests pass; make test/check-secrets pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 03:03
---
Filed from live OOMPAH-714 terminal-audit evidence: read-only awk/sed inspection commands consumed the fatal policy budget and rotated an otherwise healthy auditor. Promoting for automatic dispatch while OOMPAH-714 finishes validation.
---
author: oompah
created: 2026-08-03 03:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 03:03
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 03:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 27s
- Log: OOMPAH-716__20260803T030345Z.jsonl
---
author: oompah
created: 2026-08-03 03:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 03:04
---
Focus: Software Engineer
---
<!-- COMMENTS:END -->
