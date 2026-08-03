---
id: OOMPAH-716
type: bug
status: Open
priority: 1
title: Do not exhaust auditor policy budget on read-only awk and sed inspection
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T03:02:02.962763Z'
updated_at: '2026-08-03T03:03:44.310100Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ca6711b3db90a70ee9ccb0f22c07a68e76eaacdbcd18aa40230fb994cd5dc834
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4a8c8a80-2555-4e12-bb32-dc1bd9c65d81
  claim_owner: 382962b8-8b4b-4507-ae51-eef3a3f2cbc6
  claimed_at: '2026-08-03T03:03:36.588549+00:00'
  claim_expires_at: '2026-08-03T03:33:36.588549+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 2be72db4-3bd1-41a3-8ad8-1f03d49b3f4a
---
## Summary

Triggered by: OOMPAH-714

Triggered by OOMPAH-714 Done-audit attempt #1 at 2026-08-03 02:57-02:59 UTC (log OOMPAH-714__20260803T025707Z.jsonl). The deployed OOMPAH-713 behavior correctly returned a recoverable validation response for a grep expression, but equally read-only single commands `awk 'NR>=7790 && NR<=7900' oompah/orchestrator.py` and `sed -n '7790,7900p' oompah/orchestrator.py` were treated as fatal policy denials. The Opus auditor exhausted its denial budget and rotated after 2m23s despite making no mutation attempt. A second candidate continued, so completion was not stranded, but this wastes auditor capacity and can still exhaust all candidates under repeated tool-choice variance.

Implementation scope:
- Classify demonstrably read-only but unsupported inspection commands as recoverable validation responses that do not consume the fatal auditor policy-denial budget; they do not need to be executed.
- Cover at least non-mutating awk range/print and sed print-only forms, while keeping awk system()/write primitives, sed -i/-e write forms, output redirection, shell escape, process control, and state-changing git fail-closed and fatal.
- Keep prompt/tool guidance steering auditors to search_files and bounded read_file, and make the validation response name those alternatives.
- Ensure candidate rotation, terminal-audit health, and transport counters distinguish repeated local tool-policy incompatibility from provider failure.

Relevant code: oompah/auditor.py, oompah/authority_boundary.py, oompah/acp_tools.py, oompah/api_agent.py, oompah/orchestrator.py policy-denial accounting, auditor prompts/tool catalogs, and terminal-audit health classification.

Required tests:
- Replay the exact OOMPAH-714 awk and sed commands and prove neither invokes the fatal denial handler nor rotates the candidate.
- Prove the auditor can recover with search_files/read_file and submit an accepted verdict.
- Verify awk system()/redirection, sed -i, chained mutation, shell escape, and state-changing git remain fatal.
- Verify no launch/transport alert is recorded for recoverable validation, while genuine provider failures still are.

Acceptance criteria:
- Replaying OOMPAH-714 attempt #1 reaches submit_audit_result without candidate rotation solely because of the read-only awk/sed requests.
- No write-capable command is admitted.
- Focused authority-boundary, auditor-contract, backend tool, orchestrator denial-budget, and terminal-audit health tests pass; make test/check-secrets pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 03:03
---
Filed from live OOMPAH-714 terminal-audit evidence: read-only awk/sed inspection commands consumed the fatal policy budget and rotated an otherwise healthy auditor. Promoting for automatic dispatch while OOMPAH-714 finishes validation.
---
author: oompah
created: 2026-08-03 03:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 03:03
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
