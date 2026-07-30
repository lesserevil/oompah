---
id: OOMPAH-589
type: bug
status: Open
priority: 1
title: Validate auditor provider endpoints before candidate dispatch
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:20.256845Z'
updated_at: '2026-07-30T14:31:13.216633Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-589
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5959c896665e6c4f26f1aecbff8cf62fb2974c3e9536790adddc03a5eb144815
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T14:20:39.700229+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation, I have searched all task states\
    \ (open, merged, archived, backlog) across the oompah task tracker and found **no\
    \ existing tasks that duplicate OOMPAH-589**.\n\n**Search evidence:**\n- **Keywords\
    \ searched**: auditor, completion_auditor, provider, endpoint, endpoint_validation,\
    \ validate, dispatch, transport_config, OpenAI, completion, LLM_provider, and\
    \ OOMPAH-585/590/591/592\n- **Scopes searched**: \n  - `.oompah/tasks/open/` \u2014\
    \ 1 task found (OOMPAH-281 about GitHub Actions runners, unrelated)\n  - `.oompah/tasks/merged/`\
    \ \u2014 7 tasks found, none match auditor/endpoint/provider keywords\n  - `.oompah/tasks/archived/`\
    \ \u2014 270+ tasks found, none match auditor/endpoint/provider keywords\n  -\
    \ `.oompah/tasks/backlog/` \u2014 1 task found (OOMPAH-282 about state branch\
    \ migration error, unrelated)\n  - `docs/` and `plans/` directories \u2014 no\
    \ matches for auditor/provider/endpoint patterns\n  - Code search for `auditor_dispatch`\
    \ and related modules \u2014 no matches in task metadata\n\n**Closest reviewed\
    \ active tasks:**\n- OOMPAH-281 (Open): GitHub Actions self-hosted runner setup\
    \ \u2014 completely different scope\n- No other open, merged, or backlog tasks\
    \ contain references to completion auditors, provider endpoint validation, or\
    \ related concepts\n\n**Evidence:** OOMPAH-589 addresses a specific gap in validation\
    \ of auditor provider transport configurations (ensuring OpenAI-compatible endpoints\
    \ resolve to absolute HTTP(S) URLs). This is distinct from all existing tracked\
    \ work. The task references an epic parent (OOMPAH-585) and siblings (OOMPAH-590,\
    \ 591, 592) that do not yet exist in the tracker, suggesting this is a fresh decomposition\
    \ of new work.\n\n**Final Verdict:**\n\nFocus handoff: duplicate_detector\n\n\
    Duplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: Comprehensive\
    \ search across all task states (open/merged/archived/backlog) using keywords\
    \ auditor, endpoint, provider, validate, dispatch, OpenAI, completion found zero\
    \ matching tasks. Only 1 open task exists"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 129a22d4-dc50-4cfb-9bf5-1196a69ff1ed
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-589
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-589
  base_branch: epic-OOMPAH-585
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T14:21:06.762940+00:00'
oompah.task_costs:
  total_input_tokens: 146
  total_output_tokens: 4538
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 146
      output_tokens: 4538
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 146
    output_tokens: 4538
    cost_usd: 0.0
    recorded_at: '2026-07-30T14:20:39.699057+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-589__20260730T141852Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-585--task-OOMPAH-589
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T14:20:39.705139+00:00'
---
## Summary

Implementation scope

Validate every completion-auditor candidate transport configuration before launch. OpenAI-compatible endpoints must resolve to an absolute HTTP(S) base URL; a missing base must never become the relative URL /chat/completions. Exclude invalid candidates from dispatch, retain independence/provider filtering, and emit a redacted actionable reason without secrets. Relevant areas include provider configuration/loading, oompah/auditor_dispatch.py, the completion-auditor session factory, and health state serialization.

Tests

Add unit/integration regressions for absent, relative, malformed, and valid base URLs; mixed candidate pools; provider fallback; credential redaction; and startup/runtime configuration changes. Run focused provider/auditor tests and make test.

Acceptance criteria

No auditor launch can reach unknown URL type /chat/completions; valid independent candidates still dispatch; invalid candidates are safely skipped and visible through structured health evidence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 14:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 14:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 14:20
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 53, Tool calls: 23
- Tokens: 146 in / 4.5K out [4.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 57s
- Log: OOMPAH-589__20260730T141852Z.jsonl
---
author: oompah
created: 2026-07-30 14:21
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 14:21
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-30 14:21
---
**Understanding & Security Analysis**

Security Issue: OpenAI-compatible endpoints must validate base URLs before dispatch.

Attack Vector: Missing/relative base URLs could be resolved to attacker-controlled paths (e.g., /chat/completions on localhost or uncontrolled domains). This violates the OWASP Top 10 (A03:2021 Injection, A06:2021 Vulnerable & Outdated Components).

Planned approach:
1. Locate provider configuration loading and auditor dispatch code
2. Identify current endpoint validation gaps
3. Implement validation layer checking: absolute HTTP(S) URLs, no relative paths
4. Add credential redaction in error messages
5. Create unit/integration tests for absent/relative/malformed/valid URLs
6. Verify invalid candidates are skipped with health evidence, not silently ignored

Starting code exploration...
---
author: oompah
created: 2026-07-30 14:23
---
**Discovery: Critical Missing Validation**

Found multiple vulnerable code paths constructing OpenAI-compatible endpoints:

1. **oompah/api_agent.py** - `self._url = f"{self.base_url}/chat/completions"`
2. **oompah/completion_verifier.py** - No HTTP(S) validation before constructing URL
3. **oompah/focus.py** - Constructs endpoint without base_url validation
4. **oompah/issue_enhancer.py** - Similar pattern
5. **oompah/orchestrator.py** - Task decomposition endpoint construction
6. **oompah/provider_health.py** - Checks for empty base_url BUT NOT absolute HTTP(S)

**Root Cause**: Endpoint construction uses f-string concatenation without validating:
- base_url must be absolute HTTP(S) URL
- base_url must not be relative (e.g., "/chat/completions")
- base_url must not be malformed

**Security Impact**: Missing base or relative URL could resolve to:
- localhost:/chat/completions (SSRF)
- /chat/completions (relative path injection)
- Unknown destination (unvalidated redirect)

Current test coverage: test_provider_health.py checks for empty base_url but not URL format validation.

**Plan**: Create URL validator utility, integrate into provider creation/update, validate in auditor dispatch paths, add comprehensive tests.
---
<!-- COMMENTS:END -->
