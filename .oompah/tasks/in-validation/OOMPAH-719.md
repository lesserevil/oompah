---
id: OOMPAH-719
type: bug
status: In Validation
priority: 1
title: Keep oversized auditor run_command output inside the authority boundary
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T14:01:56.950921Z'
updated_at: '2026-08-03T15:04:46.821741Z'
work_branch: OOMPAH-719
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/680
review_number: '680'
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
oompah.agent_run_id: null
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
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-719
  head_sha: 13aed584ad06674017d1c4ee1a50eef68d9c570e
  submitted_at: '2026-08-03T14:42:58.418146+00:00'
  updated_at: '2026-08-03T14:42:58.418146+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/680
oompah.review_number: '680'
oompah.work_branch: OOMPAH-719
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a256e600cde0
    project_id: proj-14849f1b
    task_id: OOMPAH-719
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fb4fa08d0ea52a1d320c1873edca5e9e7e022f38f1457885df0db98338443b1d
    attempts:
    - version: 1
      attempt_id: attempt-9649b01db16e
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: fb4fa08d0ea52a1d320c1873edca5e9e7e022f38f1457885df0db98338443b1d
      created_at: '2026-08-03T15:04:41.019351+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T15:04:41.019351+00:00'
      branch_key: OOMPAH-719
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T15:04:18.035758+00:00'
    updated_at: '2026-08-03T15:04:41.019351+00:00'
  - version: 1
    audit_id: audit-bcdb15e45d93
    project_id: proj-14849f1b
    task_id: OOMPAH-719
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fb4fa08d0ea52a1d320c1873edca5e9e7e022f38f1457885df0db98338443b1d
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T15:04:18.035758+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-9649b01db16e
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fb4fa08d0ea52a1d320c1873edca5e9e7e022f38f1457885df0db98338443b1d
    created_at: '2026-08-03T15:04:41.019351+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T15:04:41.019351+00:00'
    branch_key: OOMPAH-719
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
author: oompah
created: 2026-08-03 14:10
---
Discovery: OOMPAH-710 already bounds read_file/search_files at the shared api_agent helper, but _exec_run_command still returns unbounded stdout/stderr. Claude, Codex, and OpenCode ACP catalogs all call that helper; auditor catalogs currently expose only read_file/list_files/search_files/run_command/submit_audit_result. I will add a per-session opaque command-output store plus read_command_output paging/search, wire it through all ACP bridges and API tool execution, and update the trusted auditor prompt so continuations never mention filesystem/provider paths.
---
author: oompah
created: 2026-08-03 14:15
---
Implementation: added CommandOutputStore with bounded 32K pages and opaque session-local result IDs; oversized run_command output now stops before provider transport and offers read_command_output paging/regex search. Wired the operation through Claude/Codex/OpenCode ACP auditor catalogs and API auditor sessions, enforced auditor_policy on API dispatch, and updated the trusted auditor prompt. Added >1 MB make-test coverage proving page/search and submit_audit_result stay path-free.
---
author: oompah
created: 2026-08-03 14:16
---
Verification: focused transport/auditor suites pass (26 tests), broader ACP/API/project-tool suites pass (165 tests), and terminal-audit health/dashboard/cleanup suites pass (91 tests). Ruff reports existing baseline violations outside this change; git diff --check and Python compilation are clean. Starting the complete Makefile gate next.
---
author: oompah
created: 2026-08-03 14:41
---
Verification complete: full equivalent pytest gate passed 15099 tests, 7 skipped, 1 xfailed, 40 existing warnings. Focused ACP/auditor, API, terminal-audit health/dashboard/cleanup suites all pass. make[1]: Entering directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-719'
make[1]: Leaving directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-719' was attempted twice but stopped before tests because astral-uv could not create a transient systemd scope in this environment; no project test failure occurred.
---
author: oompah
created: 2026-08-03 14:42
---
Completion: delivered and pushed commit 13aed584. Oversized auditor run_command output is bounded before provider transport; auditor-only read_command_output pages/searches opaque saved results; Claude/Codex/OpenCode/API paths share the guard; auditor prompt and API policy wiring prevent provider-private path recovery. Full equivalent gate passed 15099 passed, 7 skipped, 1 xfailed. Branch is clean and up to date with origin/OOMPAH-719.
---
author: oompah
created: 2026-08-03 14:43
---
Bound oversized auditor run_command output with opaque approved paging/search continuations; updated ACP/API auditor policy and prompt; added transport-boundary and verdict-flow tests.
---
author: oompah
created: 2026-08-03 14:43
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 115
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 36m 54s
- Log: OOMPAH-719__20260803T140625Z.jsonl
---
author: oompah
created: 2026-08-03 14:51
---
Branch quality gate passed for `13aed584ad06674017d1c4ee1a50eef68d9c570e` using `make test` in 404.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-03 15:04
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-03 15:04
---
YOLO: merged PR #680.
---
author: oompah
created: 2026-08-03 15:04
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 15:04
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
