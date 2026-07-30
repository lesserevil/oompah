---
id: OOMPAH-621
type: task
status: Open
priority: 1
title: Document and integration-test CLI credential precedence
parent: OOMPAH-619
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-620
labels: []
assignee: null
created_at: '2026-07-30T21:25:29.809048Z'
updated_at: '2026-07-30T21:36:45.483588Z'
work_branch: epic-OOMPAH-619--task-OOMPAH-621
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 68fdf53f98a9611a0720923e0f8379c33be3aeea57435594c0cf11ee3a964fdd
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T21:36:41.217821+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Searched `.oompah/tasks`, docs, and plans for CLI\
    \ authentication, credentials, netrc, password-file, and precedence terms. The\
    \ only active candidate, OOMPAH-281, concerns self-hosted CI runners. Archived\
    \ OOMPAH-26, OOMPAH-8, OOMPAH-42, and OOMPAH-6 cover general CLI compatibility,\
    \ installation smoke tests, release verification, or GitHub intake authentication\u2014\
    not direct CLI credential precedence."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 10e83b92-afc5-497f-b349-824d45829745
oompah.work_branch: epic-OOMPAH-619--task-OOMPAH-621
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-619--task-OOMPAH-621
  base_branch: epic-OOMPAH-619
  base_sha: c048ba706cbe9b1342b80a67576a49b82887e84a
  updated_at: '2026-07-30T21:35:26.024048+00:00'
oompah.task_costs:
  total_input_tokens: 871086
  total_output_tokens: 3139
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 871086
      output_tokens: 3139
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 871086
    output_tokens: 3139
    cost_usd: 0.0
    recorded_at: '2026-07-30T21:36:41.216663+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-621__20260730T213528Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-619--task-OOMPAH-621
    source_sha: c048ba706cbe9b1342b80a67576a49b82887e84a
    completed_at: '2026-07-30T21:36:41.227519+00:00'
---
## Summary

Implementation scope: update the user-facing authentication and CLI installation guides plus environment reference for direct CLI credentials, environment credentials, default user netrc discovery, exact precedence, hostname selection, and secure usage. Clearly state that command-line passwords are process-visible and recommend netrc or a mode-0600 password file for unattended operation. Add documentation contract and parser/help tests that keep task and admin surfaces aligned, ensure examples contain placeholders only, and verify password redaction. Add an end-to-end compatibility check that installs the standalone task CLI from an exact git revision in an isolated environment and authenticates it against the matching server revision through both task view and a safe admin read operation. Relevant files include docs/authentication.md, docs/cli-install.md, .env.example, tests/test_docs_authentication_contract.py, and CLI packaging/install tests. Begin from the integrated credential resolver behavior rather than inventing a second precedence contract. Acceptance criteria: operator docs and help agree exactly with implementation; examples cover argv, environment, password-file, and default netrc; install-from-revision compatibility is automated; focused documentation and packaging tests plus the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:35
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 21:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 21:36
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 17
- Tokens: 871.1K in / 3.1K out [874.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 23s
- Log: OOMPAH-621__20260730T213528Z.jsonl
---
<!-- COMMENTS:END -->
