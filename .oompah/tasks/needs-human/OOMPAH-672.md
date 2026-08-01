---
id: OOMPAH-672
type: task
status: Needs Human
priority: null
title: Preserve logging format placeholders during secret redaction
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T00:18:06.952783Z'
updated_at: '2026-08-01T00:35:18.723229Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5f652cb7d6eca5414cb48d9d1f328cf08af6ba4d6f93a4585b29437504747aa3
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T00:20:19.843569+00:00'
  matched_identifiers: []
  evidence: 'Based on my comprehensive investigation, I have searched through all
    task categories and directories:


    ## Investigation Summary


    **Search Scope:**

    - All `.oompah/tasks/` directories (archived: 1-276, backlog: 282, merged: 271-280,
    open: 281)

    - Multiple pattern searches: "redaction", "logging", "secret", "SecretRedactionFilter",
    "htpasswd", "placeholder", "TypeError", "format error", "regression", specific
    commit hash "72f8e706"

    - Documentation files: `docs/` and `plans/` directories

    - Related tasks: OOMPAH-651 and OOMPAH-671 (mentioned in issue description) do
    not exist in the tracker


    **Findings:**

    - No existing tasks covering secret redaction, logging format errors, or logging
    TypeError issues

    - No tasks referencing SecretRedactionFilter behavior or regressions

    - The codebase contains `oompah/secrets.py` with the SecretRedactionFilter class
    mentioned in the issue description

    - No prior similar logging/redaction integration bugs in the task history

    - OOMPAH-672 describes a novel regression: SecretRedactionFilter rewrites `record.msg`
    (replacing placeholders with [REDACTED]) while leaving `record.args` intact, causing
    Python''s %-formatting to fail with "TypeError: not all arguments converted during
    string formatting"


    **Closest Candidates Reviewed:**

    None found. The only logging-related tasks in the archive are infrastructure/CI
    tasks (OOMPAH-281 about GitHub Actions runners, OOMPAH-272 about merge conflicts),
    which are unrelated.


    ---


    **Focus handoff: duplicate_detector**


    **Duplicate preflight verdict: no_duplicate**


    **Matches: none**


    **Evidence:** Systematic search of all 280+ tracked tasks, documentation, and
    codebase revealed no existing duplicate. OOMPAH-672 describes a unique regression
    in the logging redaction boundary introduced by OOMPAH-651 (external reference
    not yet in this tracker). The issue is novel: percent-style logging format placeholder
    mismatches when SecretRedactionFilter redacts format strings but leaves args populated.
    No prior task addres'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 8d72b422-9130-465c-b9f5-990ac6ca3df0
oompah.task_costs:
  total_input_tokens: 146
  total_output_tokens: 5345
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 146
      output_tokens: 5345
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 146
    output_tokens: 5345
    cost_usd: 0.0
    recorded_at: '2026-08-01T00:20:19.842035+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-672__20260801T001834Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-672
    source_sha: 72f8e7061ab5a6ae37b08b23c9e75190cf746a87
    completed_at: '2026-08-01T00:20:19.854501+00:00'
---
## Summary

Regression observed on the first production restart after OOMPAH-651 merged at main revision 72f8e7061ab5a6ae37b08b23c9e75190cf746a87. Startup logger.info calls such as 'HTTP Basic authentication enabled (htpasswd: %s)' emit 'TypeError: not all arguments converted during string formatting'. The SecretRedactionFilter rewrites record.msg so the sensitive-label rule replaces the %s placeholder with [REDACTED], while record.args remains populated; logging then formats a message with no placeholder against one argument. Implementation scope: update the centralized logging redaction boundary in oompah/secrets.py so percent-style and supported logging format placeholders retain valid message/argument arity while both format strings and values remain secret-safe; keep fail-closed behavior and process-wide plus handler/filter idempotency. Add regression tests using configured secret values and sensitive labels for tuple args, mapping args, repeated filter/factory passes, exceptions, and the real bootstrap/server htpasswd log messages. Assert no plaintext reaches formatted output and no logging error is written to stderr. Run focused redaction/logging tests and the full Makefile gate. Acceptance: startup logs render safely with [REDACTED], SecretRedactionFilter never causes logging formatting exceptions, all existing sentinel non-persistence guarantees remain intact, and restart remains healthy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 00:18
---
Filed from the production restart at 2026-08-01T00:15Z. The service recovered and is healthy; this is a nonfatal but real redaction-boundary regression. Opened for normal Oompah dispatch while direct operator work remains focused on OOMPAH-671 and the stranded Exocomp audits.
---
author: oompah
created: 2026-08-01 00:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 00:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 00:20
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 54, Tool calls: 29
- Tokens: 146 in / 5.3K out [5.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 50s
- Log: OOMPAH-672__20260801T001834Z.jsonl
---
author: oompah
created: 2026-08-01 00:20
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 00:20
---
Focus: Event Api Redaction Specialist
---
author: oompah
created: 2026-08-01 00:20
---
Understanding: SecretRedactionFilter must keep percent-style logging message/argument arity valid while redacting both templates and values, including tuple/mapping args, repeated filter/factory passes, exceptions, and bootstrap htpasswd logs. I will inspect oompah/secrets.py and existing redaction/bootstrap tests, implement a focused fix, run focused tests plus the Makefile gate, then commit, push, and submit.
---
author: oompah
created: 2026-08-01 00:32
---
Oompah could not durably preserve this worker's task worktree before retry. The worktree was left in place and no reset, clean, or retry was started. Reconcile the workspace and recovery evidence manually before resuming the task. Error: could not stage recovery snapshot for OOMPAH-672: The following paths are ignored by one of your .gitignore files:
.oompah-no-hooks
hint: Use -f if you really want to add them.
hint: Disable this message with "git config set advice.addIgnoredFile false"
---
author: oompah
created: 2026-08-01 00:35
---
Direct operator takeover after recovery snapshot failed on the ignored .oompah-no-hooks path. The worker is stopped; its worktree is intact and has only staged changes to oompah/secrets.py and tests/test_secrets.py. I am reviewing and validating that partial implementation in place; keep Needs Human as the scheduler hold.
---
<!-- COMMENTS:END -->
