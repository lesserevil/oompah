# Merge Queue Operator Runbook

This runbook covers day-to-day operation of the submit-queue branch
policy on our managed repositories. The policy replaces the strict
`open_review` dispatch gate (see `docs/submit-queue.md` for the design)
and — for repos where merge queue is available — is required for
`Project.max_in_flight_prs > 1` to be safe.

## Repos covered

The cutover is **asymmetric** because GitHub Merge Queue requires
organization-owned repositories. User-owned repos fall back to legacy
branch protection (required status checks only).

| Repo | Account / token | Backend | Merge queue | `Project.merge_queue_enabled` |
| --- | --- | --- | --- | --- |
| `lesserevil/oompah` | `gh auth switch --user lesserevil` | `branch_protection` (legacy) | ❌ unsupported (user-owned) | **must stay `False`** |
| `NVIDIA-Omniverse/trickle` | `gh auth switch --user NVShawn` | `ruleset` | ✅ active | flip to `True` |

The script `scripts/merge-queue-cutover.sh` dispatches between
backends per repo via its `repo_api_kind` function — operators do
not need to think about which API is involved; just call
`apply` / `rollback` / `status` with `--repo`.

## Quick reference

| What | Command |
| --- | --- |
| Inspect current rules on `main` | `scripts/merge-queue-cutover.sh status --repo OWNER/NAME` |
| Apply / re-apply submit-queue ruleset | `scripts/merge-queue-cutover.sh apply --repo OWNER/NAME` |
| Roll back (delete ruleset) | `scripts/merge-queue-cutover.sh rollback --repo OWNER/NAME` |
| Enqueue a PR via gh CLI | `gh pr merge --auto --squash <number>` |
| Dequeue a PR | `gh pr edit <number> --remove-auto-merge` (closes auto-merge), or close+reopen the PR |
| Force a re-queue after a flaky failure | Re-run the failed checks via the GH UI on the PR's `gh-readonly-queue/...` ref, then re-enqueue |

## Cutover (Step 5) — coordinated procedure

The cutover changes how merges happen on `main`. Two flips need to land
within a short window of each other to avoid YOLO PRs sitting in limbo:

1. **Orchestrator side** — flip `Project.merge_queue_enabled = True` on
   the matching project in the running oompah service.
   - Web UI: `/projects-manage` → edit project → toggle "Merge queue
     enabled".
   - API: `PATCH /api/v1/projects/{project_id}` with body
     `{"merge_queue_enabled": true}`.
2. **GitHub side** — apply the merge-queue ruleset on `main` for the
   target repo:
   ```bash
   gh auth switch --user lesserevil       # for oompah
   scripts/merge-queue-cutover.sh apply --repo lesserevil/oompah
   gh auth switch --user NVShawn          # for trickle
   scripts/merge-queue-cutover.sh apply --repo NVIDIA-Omniverse/trickle
   ```

If you flip the GitHub side first, every YOLO `merge_review` call to
that repo will return HTTP 405 Method Not Allowed. The watchdog
(`Orchestrator._watchdog_yolo_limbo`) catches that and notifies, so
nothing is lost — but the cleanest sequence is **flag first, ruleset
second**.

If you flip the orchestrator side first, `enqueue_review` falls back to
`gh pr merge --auto --squash`, which simply enables auto-merge until
the ruleset is applied — also harmless.

## Per-repo settings (current)

Defined in `scripts/merge-queue-cutover.sh`. Tune values there and
re-run `apply` to update the live ruleset (the script does an UPDATE
when a ruleset with the canonical name `submit-queue-main` already
exists).

### `lesserevil/oompah` (branch protection only)

CI wall time ≈ 3 minutes. **Merge queue is not available on
user-owned repos** — see `docs/submit-queue.md` §Step 5. The script
applies legacy branch protection here.

| Parameter | Value | Rationale |
| --- | --- | --- |
| Backend | `PUT /branches/main/protection` | Rulesets API rejects `merge_queue` rule for user-owned repos. |
| Required status checks | `test (3.11)`, `test (3.12)`, `test (3.13)` | Matrix from `.github/workflows/ci.yml`. |
| `enforce_admins` | `false` | Orchestrator account (admin) bypasses for `bd` sync commits and emergency hotfixes. |
| `allow_force_pushes` | `false` | Standard. |
| `allow_deletions` | `false` | Standard. |
| `required_pull_request_reviews` | `null` | Orchestrator opens and merges its own PRs; review approval would deadlock. |
| `Project.merge_queue_enabled` | **must stay `False`** | YOLO must keep using direct `merge_review`; `enqueue_review` would call the unsupported merge-queue endpoint. |

### `NVIDIA-Omniverse/trickle`

CI wall time ≈ 60 minutes (4-OS matrix + e2e tier A/B). Long, occasionally
flaky.

| Parameter | Value | Rationale |
| --- | --- | --- |
| `merge_method` | `SQUASH` | Matches today's direct-merge behaviour. |
| `max_entries_to_build` | `3` | Three speculative builds in parallel — gives parallel throughput. |
| `max_entries_to_merge` | `1` | **No batching.** A single flake in a shared batch ejects every PR in that batch; with 60-min CI the cost of re-running is large. Each PR in its own merge_group ref. |
| `min_entries_to_merge` | `1` | Same. |
| `min_entries_to_merge_wait_minutes` | `5` | Default; mostly irrelevant when `max_entries_to_merge=1`. |
| `check_response_timeout_minutes` | `60` | Matches CI wall time. |
| `grouping_strategy` | `ALLGREEN` | Wait for all required checks. |
| Required status checks | `lint`, `test-linux`, `smoke-deb`, `test-macos`, `test-windows`, `tier-a-unit`, `build-matrix`, `tier-b-linux`, `tier-b-windows`, `tier-b-macos` | All jobs that run on `merge_group:` from `ci.yml` and `e2e.yml`. Tier-C is `schedule`/`workflow_dispatch` only and is correctly excluded. |

After the cutover has been observed stable for a day or two, raise
`Project.max_in_flight_prs` on trickle from `1` to `3` (per
`docs/submit-queue.md` §3 recommendations). On oompah, `3` is also a
reasonable target; raise once Step 2 (`.beads/issues.jsonl` merge
driver) is in production so concurrent agent commits don't conflict on
the bead store.

## Debugging

### A PR is "stuck" in the queue

Symptoms: `gh pr view <n>` shows `mergeStateStatus: BLOCKED`,
`autoMergeRequest` set, but no `gh-readonly-queue/main/pr-N-…` branch
visible.

Likely causes:
- A required status check is missing or has not reported. Look at the
  ruleset's `required_status_checks` and make sure each is named
  exactly as the corresponding job in the workflow file. Names
  including parens (e.g. `test (3.11)`) must match the matrix output
  exactly.
- The `merge_group:` trigger is missing from a workflow whose check is
  required. Step 1 of the rollout adds these triggers; verify the file
  contains:
  ```yaml
  on:
    merge_group:
      branches: [main]
  ```
- A bypass actor closed the queue. Inspect with
  `scripts/merge-queue-cutover.sh status --repo OWNER/NAME`.

### A PR was ejected from the queue

GitHub UI shows "This pull request was removed from the merge queue
because of a failure." The merge_group CI failed on the speculative
branch. Look at the failed Action run on the `gh-readonly-queue/...`
ref, fix the failing test (or the merge conflict), push, and re-enqueue
with `gh pr merge --auto --squash <n>`.

The orchestrator's `_yolo_retry_ci` watchdog re-enqueues retryable
failures automatically; manual intervention is only needed for genuine
test failures.

### CI runs but the queue stalls forever

GitHub shows the speculative branch was tested ✅ but the PR never
merges. Check that `check_response_timeout_minutes` in the ruleset is
≥ the slowest required check's wall time. Trickle's value (60 min)
needs to grow if e2e tier-b ever starts taking longer than that.

### Need to merge urgently while queue is broken

Last-resort emergency brake:

```bash
scripts/merge-queue-cutover.sh rollback --repo OWNER/NAME
# Now direct merge works again. Land the urgent PR.
# Then re-apply when ready:
scripts/merge-queue-cutover.sh apply --repo OWNER/NAME
```

Keep this short — while the ruleset is removed there is no trunk-safety
property other than what individual reviewers enforce.

## See also

- Design doc: `docs/submit-queue.md`
- Cutover script: `scripts/merge-queue-cutover.sh`
- GitHub merge queue docs:
  <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue>
