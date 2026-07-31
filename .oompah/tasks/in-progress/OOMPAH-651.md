---
id: OOMPAH-651
type: bug
status: In Progress
priority: 1
title: Redact secrets from agent tool inputs, outputs, and JSONL event logs
parent: null
children: []
blocked_by:
- OOMPAH-652
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T08:57:13.236209Z'
updated_at: '2026-07-31T09:07:02.787043Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0e9a5db29b45c78c6e68a8ad86b68bf52f79076c1703d73ce9af52a1e07f6993
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T09:02:29.889903+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive search of the oompah task database, I have\
    \ completed the duplicate investigation for OOMPAH-651.\n\n**Search Results:**\n\
    \nI searched systematically through:\n1. **All task directories** (`.oompah/tasks/open`,\
    \ `.oompah/tasks/merged`, `.oompah/tasks/archived`)\n2. **Keywords searched**:\
    \ secret, redact, password, credential, token, authorization, JSONL, log, expose,\
    \ exposure, leak, vulnerability, sanitize, telemetry, agent-log, tool-log\n3.\
    \ **Documentation**: README.md, WORKFLOW.md, docs/, plans/\n4. **Open tasks**:\
    \ Only OOMPAH-281 exists (GitHub Actions self-hosted runner \u2014 completely\
    \ unrelated)\n5. **Merged/archived tasks**: 200+ tasks scanned with no matches\
    \ for security/logging/secret keywords\n\n**Findings:**\n\nNo existing active\
    \ or completed task addresses secret redaction from agent tool inputs, outputs,\
    \ JSONL logs, or the specific security defect described in OOMPAH-651 (ClientCredentials\
    \ rendering with HTTP Basic passwords in agent debugging and persistence in JSONL\
    \ streams).\n\n---\n\n**Focus handoff: duplicate_detector**\n\n**Duplicate preflight\
    \ verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:** Comprehensive\
    \ search of 200+ tasks in merged and archived states, plus the single open task\
    \ (OOMPAH-281 on GitHub Actions runners), returned no results for patterns: secret,\
    \ redact, password, credential, token, authorization, expose, leak, sanitize,\
    \ telemetry, or agent/tool logging. OOMPAH-651 addresses a novel security defect\
    \ requiring centralized redaction boundary for all agent tool inputs/outputs,\
    \ exceptions, JSONL events, and telemetry payloads. No prior duplicate exists."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: f7f4595d-abc9-40eb-97a8-2f1981f2b7f4
oompah.task_costs:
  total_input_tokens: 82
  total_output_tokens: 2879
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 82
      output_tokens: 2879
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 82
    output_tokens: 2879
    cost_usd: 0.0
    recorded_at: '2026-07-31T09:02:29.889282+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-651__20260731T090132Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-651
    source_sha: 8fd133e26aa2823ab68cde2a42b446933142b614
    completed_at: '2026-07-31T09:02:29.895786+00:00'
---
## Summary

Security defect reproduced on 2026-07-31: agent debugging rendered a ClientCredentials value containing the configured HTTP Basic password, and the raw command/tool result was persisted in the per-agent JSONL/log stream. Truncation limits size but does not redact secrets. Implementation scope: add one recursive, centrally enforced redaction boundary before any ACP/API/CLI agent tool input, tool output, exception, last-message, telemetry payload, or JSONL event is recorded or exposed in state. Cover structured values and stringified repr/text forms for passwords, bearer/task-handoff tokens, authorization headers, URLs with userinfo, environment assignments, credential dataclasses, and known configured secret values without logging those values during initialization. Apply consistently to Claude, Codex, OpenCode, API-agent, and legacy agent paths; preserve enough safe context for diagnosis. Inspect existing logs for local exposure and provide an operator-safe rotation/cleanup procedure without copying secrets into task comments. Required tests inject sentinel secrets into nested dict/list objects, repr strings, command output, exceptions, streaming chunks, and state snapshots for every backend, asserting zero plaintext persistence while nonsecret content remains. Acceptance: no injected sentinel reaches agent JSONL, service logs, state API, alerts, comments, or telemetry; existing redaction contracts remain compatible; focused logging/security tests, make check-secrets, terminal mutation scan, and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 09:01
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 09:01
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 09:02
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 33, Tool calls: 15
- Tokens: 82 in / 2.9K out [3.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 1s
- Log: OOMPAH-651__20260731T090132Z.jsonl
---
author: oompah
created: 2026-07-31 09:03
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 09:03
---
Focus: Security Auditor
---
author: oompah
created: 2026-07-31 09:05
---
UNDERSTANDING & PLAN

Issue: Secrets (passwords, tokens, bearer credentials, URLs with userinfo) are being logged to JSONL event streams without redaction. The current _truncate_for_log function only limits size, not content.

**Root Cause Analysis:**
- Tool inputs/outputs flow through acp_backends/claude.py _truncate_for_log()
- _truncate_for_log() only truncates size, doesn't redact secrets
- Events are persisted via console.py _persist_and_emit() -> ConsoleStore.append()
- Secrets leak into: .oompah/console/*.jsonl, telemetry, state API

**Implementation Plan:**
1. Create centralized redaction module (oompah/secrets.py) with recursive secret detection
2. Patterns to redact: passwords, bearer/task-handoff tokens, auth headers, URLs with userinfo, env assignments, credential objects
3. Replace _truncate_for_log with redacted version in claude.py
4. Integrate redaction in console_format.py ConsoleEvent.to_dict()
5. Add redaction to exception/error messages in agent paths
6. Create comprehensive tests with sentinel secrets injected into nested structures
7. Scan existing logs locally and provide rotation procedure (without copying secrets)
8. Verify with: make check-secrets, make test, terminal mutation scan

**Next Steps:** Explore secret detection patterns and implement centralized redaction module.
---
<!-- COMMENTS:END -->
