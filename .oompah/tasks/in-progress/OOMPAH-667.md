---
id: OOMPAH-667
type: bug
status: In Progress
priority: 1
title: Keep Makefile virtualenv PATH from defeating canonical CLI cutover
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T21:32:57.017227Z'
updated_at: '2026-07-31T22:59:10.486784Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7599962d7e4882dd14f44d8ceea52fc73864838b17354027b56d93f81b9e7418
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T22:58:51.200342+00:00'
  matched_identifiers: []
  evidence: "Based on my thorough investigation of the task database, I can now render\
    \ my duplicate screening verdict.\n\n## Investigation Summary\n\nI searched the\
    \ oompah task tracker across all states (open, merged, archived) using multiple\
    \ keyword combinations:\n- \"OOMPAH-619\" (the triggering issue mentioned) \u2014\
    \ not found in the database\n- \"sync-cli\", \"sync_canonical_cli\" \u2014 not\
    \ found\n- \"canonical\", \"launcher\", \"activation\" \u2014 not found\n- \"\
    Makefile\", \"virtualenv\", \"PATH\" \u2014 not found in task descriptions or\
    \ code context\n- Task ID ranges 600-669 (to capture 619 and 667) \u2014 no such\
    \ tasks exist\n\nThe only open task found was **OOMPAH-281** (self-hosted GitHub\
    \ Actions runner setup), which is unrelated to this PATH/CLI cutover issue.\n\n\
    ## Problem Analysis\n\nI confirmed the bug exists by examining the actual source\
    \ code:\n\n1. **Makefile** (line 4-5): Exports `PATH := $(abspath $(VENV)/bin):$(PATH)`\
    \ globally\n2. **sync_canonical_cli.py** (lines 450-481): The `synchronize()`\
    \ function validates that `command -v oompah` resolves to the canonical user launcher\
    \ at `~/.local/bin/oompah` using the operator's real PATH\n3. **The conflict**:\
    \ When `make sync-cli` is invoked, it runs the validation script with the Makefile-enhanced\
    \ PATH, causing `shutil.which(\"oompah\")` to find `.venv/bin/oompah` instead,\
    \ triggering the error: `refusing CLI synchronization: command -v oompah resolves\
    \ to .venv/bin/oompah; expected ~/.local/bin/oompah`\n\nThe issue is a unique,\
    \ reproducible problem with no existing duplicate task covering it.\n\n---\n\n\
    **Focus handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:** Comprehensive scan of .oompah/tasks across\
    \ all states (archived, merged, open) using multiple search patterns (sync-cli,\
    \ canonical, launcher, PATH, Makefile, virtualenv, cutover) yielded no results.\
    \ OOMPAH-619 (referenced as the triggering issue) does not exist in the task database.\
    \ OOMPAH-281 (the only open task touching CLI infrastructure) covers self-hosted\
    \ GitHub A"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: a5c1ccde-9a95-4ff1-ab7f-1ad7b0150519
oompah.task_costs:
  total_input_tokens: 186
  total_output_tokens: 4766
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 186
      output_tokens: 4766
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 186
    output_tokens: 4766
    cost_usd: 0.0
    recorded_at: '2026-07-31T22:58:51.200004+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-667__20260731T225718Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-667
    source_sha: d96740a6ecdca353e40ef87e94a4ee91b8828df0
    completed_at: '2026-07-31T22:58:51.212689+00:00'
---
## Summary

Triggered by: OOMPAH-619

Production reproduction on merged main revision 16362384be835d1485d1121ce3c8329743391c79: running make sync-cli with the normal Makefile environment fails with "refusing CLI synchronization: command -v oompah resolves to .venv/bin/oompah; expected ~/.local/bin/oompah". Makefile globally prepends the project virtualenv to PATH so its internal Python and tools are available, but scripts/sync_canonical_cli.py correctly treats that same effective PATH as the operator command-resolution contract. The supported operational workaround make PATH="$PATH" sync-cli and make PATH="$PATH" restart succeeds, proving the selected revision and cutover logic are sound. Fix the Makefile and/or lifecycle scripts so internal virtualenv tool resolution is separated from validation of the caller/canonical CLI PATH; do not weaken detection of a genuinely shadowing noncanonical oompah executable. Add regression tests that invoke the real sync-cli and restart target environment with isolated HOME, UV tool directories, virtualenv, and canonical launcher; cover initial activation, already-current no-op, a true wrong-PATH refusal, install failure rollback, and successful server/CLI revision equality. Acceptance: unqualified make sync-cli and normal make restart work from a standard operator shell, command -v oompah still resolves to the canonical user launcher after cutover, CLI/server revisions match, and the focused lifecycle suites plus full project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 22:57
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 22:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 22:58
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 51, Tool calls: 25
- Tokens: 186 in / 4.8K out [5.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 39s
- Log: OOMPAH-667__20260731T225718Z.jsonl
---
author: oompah
created: 2026-07-31 22:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 22:59
---
Focus: Event Api Redaction Specialist
---
<!-- COMMENTS:END -->
