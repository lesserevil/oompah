---
id: OOMPAH-685
type: task
status: In Progress
priority: null
title: Forward project forge credentials through integration verification
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T21:46:41.297124Z'
updated_at: '2026-08-01T22:13:02.627132Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a1169e9f2f5e13abe47cf960e9eddb34ea17f34369d50924d731a5a052558a80
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T22:00:53.063141+00:00'
  matched_identifiers: []
  evidence: 'Based on my comprehensive investigation as a Duplicate Investigator,
    let me provide my findings:


    ## Investigation Summary


    I have systematically searched the entire task tracker across all states (open,
    merged, archived) using multiple search patterns related to the core issue:


    **Search patterns used:**

    - Direct references: `OOMPAH-680`, `OOMPAH-685`

    - Topic keywords: `forge credentials`, `git_credential`, `integration verification`,
    `credential forward`

    - Related functionality: `integration execution`, `epic integration`, `rebase
    fetch`, `git askpass`, `subprocess environment`

    - Specific case: `NodeVirt`, `NODEVIRT`, `access_token`, `gitlab`


    **Results:**

    - **No task found** covering "Forward project forge credentials through integration
    verification"

    - **No existing task** about integration queue credential forwarding

    - **No active task** about git credential environment in subprocess plumbing

    - **No reference** to OOMPAH-680 in the tracker (though task description references
    it as merged)

    - **No matching open/active task** in any state


    **Relevant tasks reviewed:**

    - OOMPAH-281 (GitHub Actions runners) - unrelated

    - All archived tasks (270+) - searched for integration/credential/verification
    patterns, none matched

    - Both merged and open directories - only OOMPAH-281 in open state, irrelevant
    to this issue


    **Conclusion:**

    OOMPAH-685 addresses a distinct problem not covered by any existing open or in-progress
    task. While it references OOMPAH-680 as a predecessor, this is a regression issue
    requiring new implementation work specifically targeting credential forwarding
    through integration queue operations (verification, rebase, fetch, push, branch-head
    verification, cleanup).


    ---


    Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Comprehensive search across .oompah/tasks/ (open, merged, archived),
    docs/, plans/, and repository root for keywords related to forge credentials,
    integration verification, git credent'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: edc3772c-6e83-47fa-88f1-216608359366
oompah.task_costs:
  total_input_tokens: 252
  total_output_tokens: 9009
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 252
      output_tokens: 9009
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 114
    output_tokens: 4306
    cost_usd: 0.0
    recorded_at: '2026-08-01T21:56:04.124953+00:00'
  - profile: default
    model: haiku
    input_tokens: 138
    output_tokens: 4703
    cost_usd: 0.0
    recorded_at: '2026-08-01T22:00:53.061055+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-685__20260801T215316Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-685
    source_sha: 3d50e86c334e8a6318b767b281bc254fa6d93cc2
    completed_at: '2026-08-01T21:56:04.143138+00:00'
  - run_id: OOMPAH-685__20260801T215745Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-685
    source_sha: 3d50e86c334e8a6318b767b281bc254fa6d93cc2
    completed_at: '2026-08-01T22:00:53.075154+00:00'
---
## Summary

Regression of merged OOMPAH-680 observed on NODEVIRT-7 on 2026-08-01. The NodeVirt GitLab project has a valid configured access_token: a one-shot push and authenticated fetch using oompah.git_credentials.git_credential_environment both succeed, and local/remote task heads match at bb916af. The server integration executor nevertheless failed while verifying the submitted branch with GitLab HTTP Basic access denied and changed integration state to blocked/Open. Installing a token-free private repository credential helper backed by the same configured project token immediately made the identical fetch succeed.

Implementation scope:
- Trace integration queue verification/rebase/fetch/push operations and ensure every Git network subprocess receives git_credential_environment for the resolved Project, including subprocesses spawned after leases, retries, conflict checks, epic integration, branch-head verification, and cleanup.
- Remove any path that resolves only repo_path/URL while dropping the Project credential context.
- Preserve token redaction and noninteractive behavior: no token in URLs, argv, repository config, logs, comments, or persisted queue records.
- Detect absent/invalid token separately from missing credential forwarding so operator diagnostics are accurate.
- Ensure credential lifetime covers the complete network operation but is removed immediately afterward.
- Keep the integration executor compatible with GitHub and GitLab username conventions.

Relevant code: integration executor/queue, ProjectStore and Workspace Git helpers, epic integration/rebase verification, git_credentials.py, subprocess environment plumbing, and integration retry/error reporting.

Required tests:
- Private GitLab task submission reaches branch verification/rebase/push using a configured project token when no global/repository credential helper exists.
- All nested integration Git subprocesses receive the ephemeral askpass environment.
- Missing token fails noninteractively with an actionable credential-configuration error; an invalid token reports authentication failure.
- Token and encoded token never appear in captured argv, output, logs, task comments, queue persistence, or repo config.
- GitHub project token behavior remains correct.
- Retrying the exact blocked NODEVIRT-7 generation succeeds once credential forwarding is restored without changing its head.

Acceptance criteria:
- The NODEVIRT-7 integration sequence succeeds without an operator-installed repository credential shim.
- Every managed integration network operation uses the project forge credential boundary shipped by OOMPAH-680.
- Focused integration/credential tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 21:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 21:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 21:56
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 44, Tool calls: 19
- Tokens: 114 in / 4.3K out [4.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 53s
- Log: OOMPAH-685__20260801T215316Z.jsonl
---
author: oompah
created: 2026-08-01 21:57
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 21:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 22:00
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 42, Tool calls: 21
- Tokens: 138 in / 4.7K out [4.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 11s
- Log: OOMPAH-685__20260801T215745Z.jsonl
---
author: oompah
created: 2026-08-01 22:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 22:01
---
Focus: Callback Auth Validation Specialist
---
author: oompah
created: 2026-08-01 22:01
---
Understanding: trace all managed integration Git subprocesses and credential-context resolution, then centralize project-scoped ephemeral credential propagation with tests for nested operations, error classification, lifetime, and redaction.
---
author: oompah
created: 2026-08-01 22:13
---
Discovery: the integration executor and orchestrator had project credentials available only at submission boundaries, while nested fetch/push/ls-remote subprocesses in integration verification, worktree preparation, cleanup, landing, staleness, and unpushed checks bypassed the ephemeral askpass context. OOMPAH-680 supplies the credential helper; this task is wiring that boundary through every managed integration network operation and classifying missing versus rejected credentials.
---
<!-- COMMENTS:END -->
