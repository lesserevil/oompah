---
id: OOMPAH-651
type: bug
status: Backlog
priority: 1
title: Redact secrets from agent tool inputs, outputs, and JSONL event logs
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T08:57:13.236209Z'
updated_at: '2026-07-31T08:57:13.236209Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Security defect reproduced on 2026-07-31: agent debugging rendered a ClientCredentials value containing the configured HTTP Basic password, and the raw command/tool result was persisted in the per-agent JSONL/log stream. Truncation limits size but does not redact secrets. Implementation scope: add one recursive, centrally enforced redaction boundary before any ACP/API/CLI agent tool input, tool output, exception, last-message, telemetry payload, or JSONL event is recorded or exposed in state. Cover structured values and stringified repr/text forms for passwords, bearer/task-handoff tokens, authorization headers, URLs with userinfo, environment assignments, credential dataclasses, and known configured secret values without logging those values during initialization. Apply consistently to Claude, Codex, OpenCode, API-agent, and legacy agent paths; preserve enough safe context for diagnosis. Inspect existing logs for local exposure and provide an operator-safe rotation/cleanup procedure without copying secrets into task comments. Required tests inject sentinel secrets into nested dict/list objects, repr strings, command output, exceptions, streaming chunks, and state snapshots for every backend, asserting zero plaintext persistence while nonsecret content remains. Acceptance: no injected sentinel reaches agent JSONL, service logs, state API, alerts, comments, or telemetry; existing redaction contracts remain compatible; focused logging/security tests, make check-secrets, terminal mutation scan, and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

