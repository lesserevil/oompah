---
id: OOMPAH-685
type: task
status: Open
priority: null
title: Forward project forge credentials through integration verification
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T21:46:41.297124Z'
updated_at: '2026-08-01T21:57:44.798121Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a1169e9f2f5e13abe47cf960e9eddb34ea17f34369d50924d731a5a052558a80
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 9064cea0-538f-4b71-848a-073b8fd2d80a
  claim_owner: 9c8dda42-c87b-429a-bdb1-42da8ebebe7e
  claimed_at: '2026-08-01T21:57:36.763139+00:00'
  claim_expires_at: '2026-08-01T22:27:36.763139+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 77974f0f-42b1-4664-a78c-fc74bb350c13
oompah.task_costs:
  total_input_tokens: 114
  total_output_tokens: 4306
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 114
      output_tokens: 4306
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 114
    output_tokens: 4306
    cost_usd: 0.0
    recorded_at: '2026-08-01T21:56:04.124953+00:00'
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
<!-- COMMENTS:END -->
