---
id: OOMPAH-651
type: bug
status: Open
priority: 1
title: Redact secrets from agent tool inputs, outputs, and JSONL event logs
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T08:57:13.236209Z'
updated_at: '2026-07-31T09:01:31.098496Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0e9a5db29b45c78c6e68a8ad86b68bf52f79076c1703d73ce9af52a1e07f6993
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 94e4a117-070f-4d21-ad00-c621d3e70815
  claim_owner: 432b475d-ac6b-4689-b481-380c0818b1e9
  claimed_at: '2026-07-31T09:01:26.742196+00:00'
  claim_expires_at: '2026-07-31T09:31:26.742196+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: bbb8dc38-259d-4b59-bb50-ec4646233e27
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
<!-- COMMENTS:END -->
