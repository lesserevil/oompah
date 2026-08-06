---
id: OOMPAH-843
type: task
status: In Progress
priority: null
title: Make auditor validation targets and command deadlines mutually feasible
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T02:39:33.484875Z'
updated_at: '2026-08-06T02:42:05.066525Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 284462f7bcc885e4ac065d8b276d6524a4a03c242330e763e67d48d068c87aae
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T02:40:41.068881+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active peer task in the supplied corpus covers auditor\
    \ validation-target authorization, command-deadline compatibility, or queued validation\
    \ budgets. Closest reviewed tasks were OOMPAH-156 and OOMPAH-175, but both are\
    \ Archived and address unrelated deduplication and release-branch catalog behavior.\n\
    Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: No active peer task in the supplied corpus covers\
    \ auditor validation-target authorization, command-deadline compatibility, or\
    \ queued validation budgets. Closest reviewed tasks were OOMPAH-156 and OOMPAH-175,\
    \ but both are Archived and address unrelated deduplication and release-branch\
    \ catalog behavior."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: c82c5ecd-3eb1-49b2-a89c-fbd587d22806
oompah.task_costs:
  total_input_tokens: 46935
  total_output_tokens: 259
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46935
      output_tokens: 259
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46935
    output_tokens: 259
    cost_usd: 0.0
    recorded_at: '2026-08-06T02:40:41.067434+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-843__20260806T024029Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-843
    source_sha: fe6257b596f79296b11dd4870a62bdbc79159d27
    completed_at: '2026-08-06T02:40:41.085595+00:00'
---
## Summary

Live OOMPAH-796 audit attempt attempt-bf484b85b4ed on 2026-08-06 exposed an impossible validation contract. The auditor correctly requested the focused Make target for the workflow domain, but policy rejected it because only make test, make test-serial, and make check-secrets were configured. It then ran permitted make test, which the agent command wrapper killed at the default 720-second deadline even though this repository's canonical full suite consistently needs roughly 1,080 seconds. The auditor next selected slower make test-serial, guaranteeing another timeout and consuming its bounded session without verdict evidence.\n\nImplementation scope:\n- Validate at project load/startup that every configured auditor validation target has a command deadline compatible with its observed/configured gate budget; fail closed with a truthful configuration action instead of launching an impossible audit.\n- Allow project-scoped focused Make targets required by the audited domain while preserving the exact allowlist, no arbitrary shell expansion, read-only authority, secret redaction, and validation-resource serialization.\n- Derive or configure per-target deadlines rather than applying one shorter global default to every permitted target; queued validation time must not consume execution time.\n- Teach the auditor prompt/tool response to prefer compatible focused targets and not fall back from a timed-out parallel full suite to a predictably slower serial suite.\n- Preserve independent verdict requirements and classify an impossible validation contract separately from provider transport failure or code failure.\n\nRelevant code: oompah/api_agent.py run-command deadline resolution, oompah/acp_tools.py command execution, oompah/auditor.py validation-target contract/prompt, project configuration and .env.example, validation-resource lease/liveness reporting.\n\nRequired tests:\n- A configured full target with expected duration above 720 seconds receives a compatible deadline and completes; true overruns remain bounded.\n- A domain-focused Make target is permitted only when explicitly configured for that project and remains shell-safe.\n- Auditor queued behind an exact gate retains its full execution budget after acquisition.\n- Reproduce OOMPAH-796: focused target denied plus 1,080-second full target under a 720-second default must fail configuration before launch or choose a feasible target, never loop into test-serial.\n- Multi-project targets/deadlines stay isolated; invalid targets, mutation, redirection, and credential access remain fatal.\n\nAcceptance criteria:\n- Every advertised auditor validation command can finish within its effective execution budget under the project's configured gate duration.\n- No auditor burns an attempt cycling through targets that are structurally unable to finish.\n- State and alerts identify configuration incompatibility with the exact target/deadline evidence.\n- Focused auditor/ACP/liveness/validation-resource/config tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 02:39
---
Immediate operator mitigation staged in .env: OOMPAH_AGENT_COMMAND_TIMEOUT_SECONDS=2400, safely above the observed ~1,080-second canonical gate and below the one-hour audit session. It requires a later make restart after active gates/audits drain; no unsafe live restart was attempted. The code fix must still validate target/deadline compatibility and support explicitly configured focused targets.
---
author: oompah
created: 2026-08-06 02:40
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 02:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 02:40
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.9K in / 259 out [47.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 34s
- Log: OOMPAH-843__20260806T024029Z.jsonl
---
author: oompah
created: 2026-08-06 02:41
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 02:42
---
Focus: Oompah Tests Auth Specialist
---
<!-- COMMENTS:END -->
