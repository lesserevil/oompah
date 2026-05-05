#!/usr/bin/env bash
# scripts/merge-queue-cutover.sh
#
# Apply or roll back the submit-queue branch policy on a repo's `main`
# branch. Step 5 of docs/submit-queue.md.
#
# This script is idempotent: re-applying does an UPDATE on rulesets and
# a re-PUT on branch protection (which is also idempotent on GitHub's
# side). It also accepts a `rollback` verb that removes the policy.
#
# Dispatches between two backends per repo, controlled by `repo_api_kind`:
#
# - `ruleset` (org-owned repos): full GitHub Merge Queue via the
#   Rulesets API. POST/PUT /repos/{owner}/{repo}/rulesets with a
#   `merge_queue` rule + `required_status_checks` rule.
#
# - `branch_protection` (user-owned free-tier repos): legacy branch
#   protection PUT /repos/{owner}/{repo}/branches/{branch}/protection.
#   Required status checks gate direct merges; merge queue is **not**
#   enabled because GitHub does not support the merge_queue rule type
#   on user-owned repos. The orchestrator's existing direct-merge YOLO
#   path is the merge mechanism; this is fine for fast-CI repos like
#   oompah where queue parallelism isn't the bottleneck.
#
# Usage:
#   scripts/merge-queue-cutover.sh apply   --repo lesserevil/oompah
#   scripts/merge-queue-cutover.sh apply   --repo NVIDIA-Omniverse/trickle
#   scripts/merge-queue-cutover.sh rollback --repo lesserevil/oompah
#   scripts/merge-queue-cutover.sh status  --repo NVIDIA-Omniverse/trickle
#
# Authentication: assumes `gh auth status` shows an account with admin
# access to the repo. Switch accounts beforehand if needed:
#   gh auth switch --user <login>
#
# Coordination: BEFORE running `apply`, make sure
# `Project.merge_queue_enabled = True` is set on the matching project in
# the running orchestrator (via /projects-manage UI or
# `PATCH /api/v1/projects/{project_id}`). Otherwise existing YOLO
# direct-merge attempts will fail with HTTP 405 once the ruleset is
# active. The watchdog will catch the limbo state, but it is cleaner to
# coordinate the two flips.

set -euo pipefail

RULESET_NAME="submit-queue-main"

usage() {
    cat <<EOF >&2
Usage:
  $0 apply    --repo OWNER/NAME
  $0 rollback --repo OWNER/NAME
  $0 status   --repo OWNER/NAME

Options:
  --repo OWNER/NAME   Target repository (e.g. lesserevil/oompah).
EOF
    exit 2
}

# Return "ruleset" or "branch_protection" — which API path applies to
# this repo. GitHub Merge Queue (the merge_queue rule type) is only
# available on **organization-owned** repos. User-owned free-tier repos
# fall back to the legacy branch-protection PUT, which gives required
# status checks but not merge queue. The choice is per-repo, set here.
repo_api_kind() {
    local repo="$1"
    case "$repo" in
        lesserevil/oompah)         echo "branch_protection" ;;
        NVIDIA-Omniverse/trickle)  echo "ruleset" ;;
        *)
            echo "error: no submit-queue mapping defined for repo '$repo'" >&2
            return 1
            ;;
    esac
}

# Build the JSON ruleset payload tuned for the given repo.
# - trickle: batch_size=1 (no batching), build_concurrency=3, timeout=60min.
# (oompah uses build_branch_protection_payload instead; merge_queue rule
# is unsupported on user-owned repos.)
build_payload() {
    local repo="$1"
    case "$repo" in
        NVIDIA-Omniverse/trickle)
            cat <<'EOF'
{
  "name": "submit-queue-main",
  "target": "branch",
  "enforcement": "active",
  "bypass_actors": [],
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "merge_queue",
      "parameters": {
        "merge_method": "SQUASH",
        "max_entries_to_build": 3,
        "max_entries_to_merge": 1,
        "min_entries_to_merge": 1,
        "min_entries_to_merge_wait_minutes": 5,
        "check_response_timeout_minutes": 60,
        "grouping_strategy": "ALLGREEN"
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "do_not_enforce_on_create": false,
        "strict_required_status_checks_policy": false,
        "required_status_checks": [
          { "context": "lint" },
          { "context": "test-linux" },
          { "context": "smoke-deb" },
          { "context": "test-macos" },
          { "context": "test-windows" },
          { "context": "tier-a-unit" },
          { "context": "build-matrix" },
          { "context": "tier-b-linux" },
          { "context": "tier-b-windows" },
          { "context": "tier-b-macos" }
        ]
      }
    }
  ]
}
EOF
            ;;
        *)
            echo "error: no merge-queue payload defined for repo '$repo'" >&2
            exit 1
            ;;
    esac
}

# Build the legacy branch-protection PUT payload for repos that can't
# use the rulesets/merge_queue API (user-owned free-tier).
build_branch_protection_payload() {
    local repo="$1"
    case "$repo" in
        lesserevil/oompah)
            cat <<'EOF'
{
  "required_status_checks": {
    "strict": false,
    "checks": [
      { "context": "test (3.11)" },
      { "context": "test (3.12)" },
      { "context": "test (3.13)" }
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": false,
  "lock_branch": false,
  "allow_fork_syncing": false
}
EOF
            ;;
        *)
            echo "error: no branch-protection payload defined for repo '$repo'" >&2
            exit 1
            ;;
    esac
}

# Find the existing submit-queue ruleset id, or empty if missing.
existing_ruleset_id() {
    local repo="$1"
    gh api "repos/${repo}/rulesets" --paginate \
        --jq ".[] | select(.name == \"${RULESET_NAME}\") | .id" \
        2>/dev/null | head -n 1
}

cmd_apply() {
    local repo="$1"
    local kind
    kind="$(repo_api_kind "$repo")"

    if [[ "$kind" == "ruleset" ]]; then
        local payload existing
        payload="$(build_payload "$repo")"
        existing="$(existing_ruleset_id "$repo")"
        if [[ -n "$existing" ]]; then
            echo "Updating existing ruleset id=${existing} on ${repo}…"
            printf '%s' "$payload" | gh api -X PUT "repos/${repo}/rulesets/${existing}" --input -
        else
            echo "Creating new ruleset on ${repo}…"
            printf '%s' "$payload" | gh api -X POST "repos/${repo}/rulesets" --input -
        fi
        echo
        echo "Done. Ruleset is live. To roll back:"
        echo "  $0 rollback --repo ${repo}"
    else
        # branch_protection: legacy PUT.
        # User-owned repos cannot use the merge_queue rule type — see
        # docs/submit-queue.md §Step 5. Fall back to required status
        # checks via the legacy branch-protection API. Direct YOLO
        # merge_review continues to be the merge path; the queue is
        # not enabled.
        local payload
        payload="$(build_branch_protection_payload "$repo")"
        echo "Applying branch protection (no merge queue) on ${repo}…"
        echo "  Reason: ${repo} is user-owned/free-tier; merge_queue rule"
        echo "  is not supported by GitHub for this ownership."
        printf '%s' "$payload" | gh api -X PUT "repos/${repo}/branches/main/protection" --input -
        echo
        echo "Done. Branch protection is live. To roll back:"
        echo "  $0 rollback --repo ${repo}"
    fi
}

cmd_rollback() {
    local repo="$1"
    local kind
    kind="$(repo_api_kind "$repo")"

    if [[ "$kind" == "ruleset" ]]; then
        local existing
        existing="$(existing_ruleset_id "$repo")"
        if [[ -z "$existing" ]]; then
            echo "No '${RULESET_NAME}' ruleset found on ${repo}. Nothing to do." >&2
            return 0
        fi
        echo "Deleting ruleset id=${existing} on ${repo}…"
        gh api -X DELETE "repos/${repo}/rulesets/${existing}"
        echo "Rolled back. Direct merge restored on ${repo}."
    else
        # branch_protection: legacy DELETE.
        if ! gh api "repos/${repo}/branches/main/protection" >/dev/null 2>&1; then
            echo "No branch protection on ${repo}/main. Nothing to do." >&2
            return 0
        fi
        echo "Deleting branch protection on ${repo}/main…"
        gh api -X DELETE "repos/${repo}/branches/main/protection"
        echo "Rolled back. No branch protection on ${repo}/main."
    fi
}

cmd_status() {
    local repo="$1"
    local kind
    kind="$(repo_api_kind "$repo")"
    echo "Repo:    ${repo}"
    echo "API:     ${kind}"

    if [[ "$kind" == "ruleset" ]]; then
        echo "Active branch rules on main:"
        gh api "repos/${repo}/rules/branches/main" --jq '.[] | "  - " + .type'
        local existing
        existing="$(existing_ruleset_id "$repo")"
        if [[ -n "$existing" ]]; then
            echo
            echo "Submit-queue ruleset id=${existing} (this script's ruleset)"
        else
            echo
            echo "No '${RULESET_NAME}' ruleset present."
        fi
    else
        # branch_protection: query the legacy endpoint.
        if gh api "repos/${repo}/branches/main/protection" >/dev/null 2>&1; then
            echo "Branch protection on main: ENABLED"
            echo "Required status checks:"
            gh api "repos/${repo}/branches/main/protection/required_status_checks" \
                --jq '.contexts[]? | "  - " + .'
        else
            echo "Branch protection on main: NOT ENABLED"
        fi
    fi
}

main() {
    if [[ $# -lt 1 ]]; then usage; fi
    local action="$1"; shift
    local repo=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --repo) repo="$2"; shift 2 ;;
            -h|--help) usage ;;
            *) echo "error: unknown arg: $1" >&2; usage ;;
        esac
    done
    if [[ -z "$repo" ]]; then echo "error: --repo required" >&2; usage; fi

    case "$action" in
        apply)    cmd_apply    "$repo" ;;
        rollback) cmd_rollback "$repo" ;;
        status)   cmd_status   "$repo" ;;
        *) usage ;;
    esac
}

# Only call main when executed directly. When this script is `source`d
# (e.g. by tests that want to call build_payload in isolation), skip
# the entrypoint dispatch.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
