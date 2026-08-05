---
id: OOMPAH-831
type: task
status: Open
priority: null
title: Make terminal-auditor search and safe inspection fallbacks match their advertised
  contract
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T15:44:15.632077Z'
updated_at: '2026-08-05T15:48:46.716894Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by OOMPAH-542 Archived-audit attempts logged at 2026-08-05T15:25:51Z and 2026-08-05T15:29:47Z.

The terminal-auditor prompt directs candidates away from shell pipelines toward search_files and bounded read_file, but the exposed tool contract is internally inconsistent. search_files advertises Python regular expressions while executing GNU basic grep syntax, so alternation, \\s, and similar documented patterns silently return no matches. Search results identify line numbers while bounded reads require character offsets, leaving no reliable supported path from a match to surrounding source. When candidates fall back to safe repository inspection, unsupported git ls-tree is classified as fatal rather than an unexecuted recoverable read-only request. OOMPAH-542 consequently rotated two healthy candidates without producing a code verdict.

Implementation scope:
- Make search_files semantics match the advertised Python-regex contract across every ACP backend, or change the contract and implementation together to one precisely documented syntax.
- Preserve workspace containment, include filtering, bounded output, binary handling, invalid-pattern errors, and timeout/resource bounds.
- Provide a supported bounded continuation from a search match to surrounding source, such as context-bearing search results or line-addressable bounded reads.
- Classify demonstrably read-only git ls-tree inspection as allowed or recoverable without consuming the fatal denial budget. Validate flags, revision operands, --, and workspace-relative paths fail-closed.
- Keep arbitrary python -c, output redirection, credential access, path escape, process control, and state-changing git fatal.
- Keep policy incompatibility distinct from provider transport failure.

Required tests:
- Python-regex alternation and ^\\s{4}def patterns find expected source through all auditor tool catalogs.
- Invalid regex, include filtering, large output, binary files, and workspace escape remain bounded and safe.
- A returned match can be inspected with bounded context without shell commands.
- Replay the three OOMPAH-542 git ls-tree forms; none invokes the fatal-denial callback or rotates the candidate.
- Replay the supported search/read path through accepted submit_audit_result.
- Repeated arbitrary python -c, mutation, redirects, and state-changing git still consume the fatal budget and rotate safely.
- Recoverable inspection mismatches do not raise transport or policy-incompatibility health alerts.

Acceptance criteria:
- An OOMPAH-542-style auditor can locate and inspect _watchdog_stale_completed and submit a verdict with one healthy candidate using only advertised tools.
- Tool descriptions and execution semantics agree across supported backends.
- No write-capable or arbitrary-code command is newly admitted.
- Focused auditor, ACP-tool, provider-retirement, terminal-audit-health, and output-bounds suites plus the configured full Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

