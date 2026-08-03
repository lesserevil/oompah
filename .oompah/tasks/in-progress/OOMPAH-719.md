---
id: OOMPAH-719
type: bug
status: In Progress
priority: 1
title: Keep oversized auditor run_command output inside the authority boundary
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T14:01:56.950921Z'
updated_at: '2026-08-03T14:06:55.164971Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9a37eb9b4c7585618306f307644e8e4d19b95e34cc765b76f0d9d0ddd57fa9e5
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T14:03:23.401376+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector

    Duplicate preflight verdict: no_duplicate

    Matches: none

    Evidence: ** OOMPAH-719 describes a unique problem: preventing large `run_command`
    output from forcing the auditor to read provider-private absolute paths by truncating
    output and providing approved MCP-based read operations. The closest related task,
    OOMPAH-710 (archived), explicitly covers oversized `read_file`/`search` responses,
    not `run_command` output. No active task in the corpus matches this scope. This
    is a novel ACP transport and authority boundary issue distinct from prior read/search
    truncation work.

    I''ll investigate whether OOMPAH-719 is a duplicate of an existing issue by carefully
    comparing it with the active task corpus.


    Let me first understand what OOMPAH-719 describes:

    - **Problem**: Large output from `run_command` invocations in the Claude ACP transport
    causes the auditor to be instructed to read provider-private absolute paths (~/.claude/projects/.../tool-results),
    violating the authority boundary

    - **Scope**: Bound and page run_command output, keep continuations inside approved
    MCP channels or audit-scoped temp roots, provide approved read-result operations
    for truncated output

    - **Related**: OOMPAH-710 covers oversized read_file/search responses but explicitly
    NOT run_command output


    Now let me review the active task corpus for potential matches:


    Examining the provided task corpus (all tasks from OOMPAH-1 through OOMPAH-175):

    - **OOMPAH-710**: Related but archived; explicitly covers "oversized read_file/search
    responses" per the issue description, NOT the run_command output problem

    - **OOMPAH-713, OOMPAH-716**: Referenced in issue as deployed; no full details
    in corpus

    - **OOMPAH-160** (Make native task writes atomic): Authority boundary / file handling,
    but focused on task file atomicity, not ACP output truncation

    - **OOMPAH-166+ (Epic standardization, release addendums)**: Different domain
    entirely

    - Earlier GitHub intake, validation, and infrastructure tasks: Orthogonal problems


    All visible tasks in the corpus are in "Archived" or terminal state. No active
    (Open/In Progress/In Review) task describes:

    - Handling oversized run_command output at the Claude ACP transport level

    - Keeping output within authority boundaries instead of exposing provider-private
    paths

    - Providing approved MCP continuation/read-result operations for the auditor


    ---


    **Focus handoff: duplicate_detector**


    **Duplicate preflight verdict: no_duplicate**


    **Matches: none**


    **Evidence:** OOMPAH-719 describes a unique problem: preventing large `run_command`
    output from forcing'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 53e4bbe5-009f-4c16-a342-ce69769f30c1
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1755
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1755
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1755
    cost_usd: 0.0
    recorded_at: '2026-08-03T14:03:23.400115+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-719__20260803T140233Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-719
    source_sha: fe1412ca98447e0d21307844056a860c1b385f36
    completed_at: '2026-08-03T14:03:23.415868+00:00'
---
## Summary

Production reproduction on current main b97187ab (2026-08-03): EXOCOMP-171 terminal audit audit-bad47351b510, attempt attempt-180165c919ab, correctly invoked the project configured make test command. The Claude transport persisted the oversized command result under ~/.claude/projects/.../tool-results and told the auditor to read that provider-private absolute path. The auditor then attempted grep/tail against that path, the strict read-only authority boundary denied it repeatedly, and the otherwise-valid completion audit was terminated. NODEVIRT-8 audit retries are also exhausting on policy denials. OOMPAH-710 covers oversized read_file/search responses, but not oversized output from an allowed run_command, so this remains reproducible after OOMPAH-710/713/716 are deployed.

Implementation scope:
- Bound and page output from configured auditor run_command invocations before provider transport, including make test and other approved Makefile gates.
- Keep every continuation inside the approved MCP result channel or an audit-scoped read-only temp root; never expose or instruct the model to read ~/.claude/provider-private result paths.
- Provide an approved continuation/read-result operation for truncated command output, and make the completion-auditor prompt use it instead of grep, pipes, or arbitrary absolute paths.
- Preserve accurate policy-incompatibility classification, candidate rotation, lifecycle counters, and alert clearing when a candidate encounters a provider output persistence failure.

Relevant code/context: oompah/acp_backends/claude.py; ACP run_command result bridging and truncation; oompah/api_agent.py; oompah/authority_boundary.py; terminal-audit retry/health bookkeeping in oompah/orchestrator.py and server snapshots.

Required tests:
- Reproduce more than 1 MB of output from an allowed configured run_command under the Claude transport and prove every continuation stays within the audit authority boundary.
- Prove the auditor can page/search the saved result through an approved read-only tool and submit a verdict without a policy denial.
- Cover candidate rotation after a forced continuation failure, exact queued/running/process-liveness counters, and clearing transport/policy alerts after recovery.
- Run focused ACP/auditor suites and the project Makefile gate.

Acceptance criteria:
- Large output from an allowed audit test command can never force a compliant auditor toward a provider-private path or disallowed shell pipeline.
- The live EXOCOMP-171/NODEVIRT-8 failure class completes through ordinary independent auditing without owner override.
- Audit lifecycle counters and web alerts remain truthful during retry and clear after resolution.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 14:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 14:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 14:03
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.8K out [1.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 56s
- Log: OOMPAH-719__20260803T140233Z.jsonl
---
author: oompah
created: 2026-08-03 14:06
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 14:06
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 14:06
---
Understanding: oversized output from an allowed auditor run_command must be bounded before provider persistence, with approved continuation/read access that stays within the audit authority boundary. I will trace the ACP/Claude result bridge, auditor prompt/tool handling, and lifecycle alert/counter paths; then implement focused tests and verify the relevant suites.
---
<!-- COMMENTS:END -->
