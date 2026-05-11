#!/usr/bin/env bash
# branch-cleanup.sh — Prune squash-merged/merged branch artifacts from lesserevil/oompah
# and NVIDIA-Omniverse/trickle.
#
# USAGE:
#   scripts/branch-cleanup.sh [--dry-run] [--no-dry-run] [--phase1] [--phase2] [--all]
#
# OPTIONS:
#   --dry-run     Print what would be done without making any changes (DEFAULT for safety)
#   --no-dry-run  Actually apply changes
#   --phase1      Run Phase 1 only: delete safe/squash-merged branches
#   --phase2      Run Phase 2 only: reopen stranded beads
#   --all         Run both phases (default when neither --phase1 nor --phase2 given)
#
# IDEMPOTENT: Re-running produces no changes on branches already deleted or
# beads already reopened.
#
# OPERATOR EXPLORATION WHITELIST (branches that are intentionally kept):
#
#   oompah:
#     bench/*                    — benchmark exploration
#     feature/*                  — operator feature branches
#     add-endpoint-caching       — operator exploration
#
#   trickle:
#     bench/*                    — benchmark exploration
#     epic/*                     — epic branches (managed by orchestrator)
#     fix/*                      — operator hotfix branches
#     feature/*                  — operator feature branches
#     gh-readonly-queue/*        — GitHub merge queue staging refs
#     compositor-capture-memo    — operator research memo
#     trickle-no-external-pub    — operator exploration
#     trickle-no-external-pub-v2 — operator exploration
#     trickle-readme-relpath-fix — operator docs fix
#     trickle-release-features   — release feature tracking
#     trickle-url-room-optional  — operator exploration
#     trickle-docs-plans-split   — docs restructure
#     trickle-demo-x-stack       — demo branch
#     trickle-pkgmgr-templates   — package manager templates
#     trickle-web-cursor-token-fix — web client fix
#     trickle-callback-auth-phase2-spec — spec branch
#
# This script is safe to re-run after PRs land (it re-audits on every run).

set -euo pipefail

OOMPAH_REPO="lesserevil/oompah"
TRICKLE_REPO="NVIDIA-Omniverse/trickle"
THIS_BEAD="oompah-zlz_2-8tj2"
GZ8W_BEAD="oompah-zlz_2-gz8w"
TRICKLE_BEADS_DIR="/Users/shedwards/.oompah/repos/trickle/.beads"
TODAY="$(date '+%Y-%m-%d')"

# Defaults
DRY_RUN=true
RUN_PHASE1=false
RUN_PHASE2=false

# Parse args
for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY_RUN=true ;;
    --no-dry-run) DRY_RUN=false ;;
    --phase1)     RUN_PHASE1=true ;;
    --phase2)     RUN_PHASE2=true ;;
    --all)        RUN_PHASE1=true; RUN_PHASE2=true ;;
    *)            echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

if ! $RUN_PHASE1 && ! $RUN_PHASE2; then
  RUN_PHASE1=true
  RUN_PHASE2=true
fi

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
info() { log "INFO  $*"; }
warn() { log "WARN  $*"; }

dry_delete() {
  local repo="$1" branch="$2" reason="$3"
  if $DRY_RUN; then
    echo "[DRY-RUN] Would delete ${repo}/${branch} (${reason})"
  else
    # Use the appropriate token per repo
    local token
    if [[ "$repo" == "lesserevil/"* ]]; then
      token=$(git remote get-url origin 2>/dev/null | sed 's|.*://[^:]*:\([^@]*\)@.*|\1|')
    else
      token=$(gh auth token --hostname github.com 2>/dev/null || true)
    fi
    if [[ -z "$token" ]]; then
      warn "No auth token for ${repo} — skipping delete of ${branch}"
      return 0
    fi
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
      -H "Authorization: token ${token}" \
      "https://api.github.com/repos/${repo}/git/refs/heads/${branch}" 2>/dev/null || echo "000")
    if [[ "$http_code" == "204" || "$http_code" == "200" ]]; then
      info "Deleted ${repo}/${branch} (${reason})"
    elif [[ "$http_code" == "422" || "$http_code" == "404" ]]; then
      info "Skipped ${repo}/${branch} — already gone (HTTP ${http_code})"
    else
      warn "Failed to delete ${repo}/${branch} — HTTP ${http_code}"
    fi
  fi
}

# ============================================================
# Whitelist helpers
# ============================================================
is_whitelisted_oompah() {
  local b="$1"
  case "$b" in
    main|bench/*|feature/*|add-endpoint-caching) return 0 ;;
  esac
  return 1
}

is_whitelisted_trickle() {
  local b="$1"
  case "$b" in
    main|bench/*|epic/*|fix/*|feature/*|"gh-readonly-queue/"*) return 0 ;;
    compositor-capture-memo) return 0 ;;
    trickle-no-external-pub|trickle-no-external-pub-v2) return 0 ;;
    trickle-readme-relpath-fix|trickle-release-features) return 0 ;;
    trickle-url-room-optional|trickle-docs-plans-split) return 0 ;;
    trickle-demo-x-stack|trickle-pkgmgr-templates) return 0 ;;
    trickle-web-cursor-token-fix|trickle-callback-auth-phase2-spec) return 0 ;;
  esac
  return 1
}

# ============================================================
# Phase 1: delete no-op branches from a repo
# ============================================================
phase1_cleanup_repo() {
  local repo="$1"
  local remote="$2"   # git remote name (origin / trickle)
  local wlfn="$3"     # whitelist function name

  local n_deleted=0 n_kept=0 n_whitelisted=0

  info "=== Phase 1: ${repo} ==="

  local branches
  branches=$(gh api "repos/${repo}/branches" --paginate --jq '.[].name' 2>/dev/null)

  # Cache main history subjects (for squash-merge detection)
  local main_subjects
  main_subjects=$(git log "${remote}/main" --format="%s" 2>/dev/null || true)

  while IFS= read -r branch; do
    [[ -z "$branch" || "$branch" == "main" ]] && continue

    if "$wlfn" "$branch"; then
      n_whitelisted=$((n_whitelisted + 1))
      continue
    fi

    # Ensure we have a local ref
    local tip
    tip=$(git rev-parse "${remote}/${branch}" 2>/dev/null || true)
    if [[ -z "$tip" ]]; then
      git fetch "$remote" "${branch}:refs/remotes/${remote}/${branch}" --quiet 2>/dev/null || true
      tip=$(git rev-parse "${remote}/${branch}" 2>/dev/null || true)
    fi
    if [[ -z "$tip" ]]; then
      warn "No ref for ${remote}/${branch} — skipping"
      n_kept=$((n_kept + 1))
      continue
    fi

    # Safe: branch tip is already an ancestor of main
    if git merge-base --is-ancestor "${remote}/${branch}" "${remote}/main" 2>/dev/null; then
      dry_delete "$repo" "$branch" "tip is ancestor of main"
      n_deleted=$((n_deleted + 1))
      continue
    fi

    # Squash-merged: subject line "<branch>:" found in main's commit history
    if echo "$main_subjects" | grep -qF "${branch}:"; then
      dry_delete "$repo" "$branch" "squash-merged (subject in main history)"
      n_deleted=$((n_deleted + 1))
      continue
    fi

    info "KEEPING ${branch} (genuinely stranded — work not on main)"
    n_kept=$((n_kept + 1))

  done <<< "$branches"

  info "Phase 1 ${repo}: deleted=${n_deleted} kept=${n_kept} whitelisted=${n_whitelisted}"
}

# ============================================================
# Helper: fetch all open PR branch refs for a repo (one API call)
# Writes names to a temp file, one per line
# ============================================================
fetch_open_pr_branches() {
  local repo="$1" tmpfile="$2"
  gh api "repos/${repo}/pulls?state=open&per_page=100" \
    --jq '.[].head.ref' 2>/dev/null > "$tmpfile" || true
}

branch_has_open_pr() {
  local branch="$1" tmpfile="$2"
  grep -qxF "$branch" "$tmpfile" 2>/dev/null
}

# ============================================================
# Phase 2: reopen stranded oompah beads
# ============================================================
phase2_reopen_oompah() {
  info "=== Phase 2: Reopen stranded oompah beads ==="

  # Stranded oompah branches with closed beads (confirmed from current audit)
  local beads
  beads=(
    oompah-zlz_2-0c3
    oompah-zlz_2-2y7
    oompah-zlz_2-3xm
    oompah-zlz_2-6xc
    oompah-zlz_2-8yt
    oompah-zlz_2-ag7
    oompah-zlz_2-bsg
    oompah-zlz_2-grw
    oompah-zlz_2-hye
    oompah-zlz_2-mif
    oompah-zlz_2-p4y
    oompah-zlz_2-saj
    oompah-zlz_2-yqss
    oompah-zlz_2-z22
    oompah-0gd
    oompah-8h6
    oompah-h15
    oompah-spl
  )

  local n_reopened=0 n_skip_pr=0 n_skip_open=0 n_err=0

  # Batch fetch open PRs (one API call)
  local oompah_prs_tmp
  oompah_prs_tmp=$(mktemp)
  info "Fetching open oompah PRs..."
  fetch_open_pr_branches "$OOMPAH_REPO" "$oompah_prs_tmp"

  for bead in "${beads[@]}"; do
    # Check for open PR
    if branch_has_open_pr "$bead" "$oompah_prs_tmp"; then
      info "${bead} has open PR — skipping reopen"
      n_skip_pr=$((n_skip_pr + 1))
      continue
    fi

    # Get current bead state
    local bead_json
    bead_json=$(bd show "$bead" --json 2>/dev/null || true)
    if [[ -z "$bead_json" ]]; then
      warn "${bead} not found in bd — skipping"
      n_err=$((n_err + 1))
      continue
    fi

    local status closed_at
    status=$(echo "$bead_json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if isinstance(data, list): data = data[0]
print(data.get('status', 'unknown'))
" 2>/dev/null || echo "unknown")
    closed_at=$(echo "$bead_json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if isinstance(data, list): data = data[0]
print(data.get('closed_at', 'unknown'))
" 2>/dev/null || echo "unknown")

    if [[ "$status" != "closed" ]]; then
      info "${bead} is already ${status} — skipping"
      n_skip_open=$((n_skip_open + 1))
      continue
    fi

    # Gather diagnostic info
    local tip ahead
    tip=$(git rev-parse "origin/${bead}" 2>/dev/null || echo "no-branch")
    ahead=0
    if [[ "$tip" != "no-branch" ]]; then
      ahead=$(git rev-list "origin/main..origin/${bead}" 2>/dev/null | wc -l | tr -d ' ')
    fi

    local diag="Reopened by branch-cleanup bead ${THIS_BEAD} on ${TODAY}. Agent committed and pushed but did not open a PR; close was therefore premature.

Branch: ${bead}
Branch tip SHA: ${tip}
Commits ahead of main: ${ahead}
Originally closed at: ${closed_at}"

    if $DRY_RUN; then
      echo "[DRY-RUN] Would reopen ${bead} as P1/bug, add gz8w dep, add diagnostic comment"
    else
      if bd update "$bead" --status=open --priority=1 --type=bug 2>/dev/null; then
        info "Reopened ${bead} as P1/bug"
        bd dep add "$bead" "$GZ8W_BEAD" --type blocks 2>/dev/null || \
          warn "  Could not add gz8w dep to ${bead} (may already exist)"
        bd comments add "$bead" "$diag" --author=oompah 2>/dev/null || \
          warn "  Could not add diagnostic comment to ${bead}"
        n_reopened=$((n_reopened + 1))
      else
        warn "Failed to reopen ${bead}"
        n_err=$((n_err + 1))
      fi
    fi
  done

  rm -f "$oompah_prs_tmp"

  # Orphan oompah branches (no matching bead)
  info "=== Phase 2: Oompah orphan branches ==="
  local orphans
  orphans=(udpah-b6d umpah-bz4)
  for branch in "${orphans[@]}"; do
    local tip
    tip=$(git rev-parse "origin/${branch}" 2>/dev/null || echo "no-branch")
    # Check if an orphan bead already exists (search by title substring)
    local existing_count
    existing_count=$(bd list --json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
beads = data if isinstance(data, list) else data.get('issues', [])
count = sum(1 for b in beads if '${branch}' in b.get('title', '') and b.get('status') != 'closed')
print(count)
" 2>/dev/null || echo "0")
    if [[ "$existing_count" -gt 0 ]]; then
      info "Orphan bead for ${branch} already exists — skipping"
      continue
    fi
    if $DRY_RUN; then
      echo "[DRY-RUN] Would file orphan bead for ${branch} (tip=${tip})"
    else
      bd create \
        --title="Orphan branch: ${branch} has unmerged commits with no matching bead" \
        --description="The branch \`${branch}\` exists on origin/oompah with unmerged commits (tip: ${tip}) but does not match any bead identifier. It is not on the operator exploration whitelist. This branch predates the oompah-zlz_2 naming convention. Operator review needed: port the work to a new bead, or delete if no longer relevant.

Filed by branch-cleanup bead ${THIS_BEAD}." \
        --type=bug --priority=2 --labels=orphan-branch \
        2>/dev/null || warn "Could not create orphan bead for ${branch}"
    fi
  done

  info "Phase 2 oompah: reopened=${n_reopened} skip_pr=${n_skip_pr} skip_open=${n_skip_open} errors=${n_err}"
}

# ============================================================
# Phase 2: reopen stranded trickle beads
# ============================================================
phase2_reopen_trickle() {
  info "=== Phase 2: Reopen stranded trickle beads ==="

  if [[ ! -d "$TRICKLE_BEADS_DIR" ]]; then
    warn "Trickle beads dir not found (${TRICKLE_BEADS_DIR}) — skipping trickle Phase 2"
    return 0
  fi

  if ! git remote | grep -q '^trickle$'; then
    warn "trickle remote not configured — skipping trickle Phase 2"
    return 0
  fi

  # Batch fetch open PRs for trickle
  local trickle_prs_tmp
  trickle_prs_tmp=$(mktemp)
  info "Fetching open trickle PRs..."
  fetch_open_pr_branches "$TRICKLE_REPO" "$trickle_prs_tmp"

  # Collect all genuinely stranded trickle branches
  local main_subjects
  main_subjects=$(git log "trickle/main" --format="%s" 2>/dev/null || true)

  local n_reopened=0 n_skip_pr=0 n_skip_open=0 n_no_bead=0 n_err=0

  local branches
  branches=$(gh api "repos/${TRICKLE_REPO}/branches" --paginate --jq '.[].name' 2>/dev/null)

  while IFS= read -r branch; do
    [[ -z "$branch" || "$branch" == "main" ]] && continue
    if is_whitelisted_trickle "$branch"; then continue; fi

    local tip
    tip=$(git rev-parse "trickle/${branch}" 2>/dev/null || true)
    [[ -z "$tip" ]] && continue

    # Check if genuinely stranded
    if git merge-base --is-ancestor "trickle/${branch}" "trickle/main" 2>/dev/null; then continue; fi
    if echo "$main_subjects" | grep -qF "${branch}:"; then continue; fi

    # This branch is genuinely stranded — check for open PR
    if branch_has_open_pr "$branch" "$trickle_prs_tmp"; then
      info "${branch} has open PR — skipping reopen"
      n_skip_pr=$((n_skip_pr + 1))
      continue
    fi

    # Look up bead in trickle issues.jsonl
    local bead_line
    bead_line=$(grep "\"id\":\"${branch}\"" "${TRICKLE_BEADS_DIR}/issues.jsonl" 2>/dev/null | head -1 || true)
    if [[ -z "$bead_line" ]]; then
      warn "${branch} has no matching trickle bead — filing orphan"
      n_no_bead=$((n_no_bead + 1))
      if $DRY_RUN; then
        echo "[DRY-RUN] Would file orphan trickle bead for ${branch} (tip=${tip})"
      else
        BEADS_DIR="$TRICKLE_BEADS_DIR" bd create \
          --title="Orphan branch: ${branch} has unmerged commits with no matching bead" \
          --description="The branch \`${branch}\` exists on NVIDIA-Omniverse/trickle with unmerged commits (tip: ${tip}) but does not match any bead identifier. Operator review needed.

Filed by oompah branch-cleanup bead ${THIS_BEAD}." \
          --type=bug --priority=2 --labels=orphan-branch \
          2>/dev/null || warn "Could not create orphan bead for trickle/${branch}"
      fi
      continue
    fi

    local status closed_at
    status=$(echo "$bead_line" | python3 -c "
import sys, json
data = json.loads(sys.stdin.readline())
print(data.get('status', 'unknown'))
" 2>/dev/null || echo "unknown")
    closed_at=$(echo "$bead_line" | python3 -c "
import sys, json
data = json.loads(sys.stdin.readline())
print(data.get('closed_at', 'unknown'))
" 2>/dev/null || echo "unknown")

    if [[ "$status" != "closed" ]]; then
      info "${branch} bead is already ${status} — skipping"
      n_skip_open=$((n_skip_open + 1))
      continue
    fi

    # Gather diagnostic info
    local ahead
    ahead=$(git rev-list "trickle/main..trickle/${branch}" 2>/dev/null | wc -l | tr -d ' ')

    local diag="Reopened by branch-cleanup bead ${THIS_BEAD} on ${TODAY}. Agent committed and pushed but did not open a PR; close was therefore premature.

Branch: ${branch} (NVIDIA-Omniverse/trickle)
Branch tip SHA: ${tip}
Commits ahead of main: ${ahead}
Originally closed at: ${closed_at}

Note: When re-dispatching, ensure a close-gate is in place on trickle (equivalent to oompah gz8w) to prevent repeat of the pattern."

    if $DRY_RUN; then
      echo "[DRY-RUN] Would reopen trickle ${branch} as P1/bug, add diagnostic comment"
    else
      if BEADS_DIR="$TRICKLE_BEADS_DIR" bd update "$branch" --status=open --priority=1 --type=bug 2>/dev/null; then
        info "Reopened trickle ${branch} as P1/bug"
        BEADS_DIR="$TRICKLE_BEADS_DIR" bd comments add "$branch" "$diag" --author=oompah 2>/dev/null || \
          warn "  Could not add diagnostic comment to ${branch}"
        n_reopened=$((n_reopened + 1))
      else
        warn "Failed to reopen trickle ${branch}"
        n_err=$((n_err + 1))
      fi
    fi

  done <<< "$branches"

  rm -f "$trickle_prs_tmp"

  info "Phase 2 trickle: reopened=${n_reopened} skip_pr=${n_skip_pr} skip_open=${n_skip_open} no_bead=${n_no_bead} errors=${n_err}"
}

# ============================================================
# Main
# ============================================================
info "Branch cleanup script starting (dry_run=${DRY_RUN} phase1=${RUN_PHASE1} phase2=${RUN_PHASE2})"

if $DRY_RUN; then
  warn "DRY-RUN mode: no changes will be made. Pass --no-dry-run to apply."
fi

# Fetch up-to-date refs
info "Fetching origin (oompah)..."
git fetch origin --prune --quiet 2>/dev/null || warn "fetch origin failed"

if $RUN_PHASE1 || $RUN_PHASE2; then
  if ! git remote | grep -q '^trickle$'; then
    NVSHAWN_TOKEN=$(gh auth token --hostname github.com 2>/dev/null || true)
    if [[ -n "$NVSHAWN_TOKEN" ]]; then
      git remote add trickle \
        "https://NVShawn:${NVSHAWN_TOKEN}@github.com/NVIDIA-Omniverse/trickle.git" 2>/dev/null || true
    fi
  fi
  info "Fetching trickle..."
  git fetch trickle --prune --quiet 2>/dev/null || warn "fetch trickle failed"
fi

if $RUN_PHASE1; then
  phase1_cleanup_repo "$OOMPAH_REPO" "origin"  "is_whitelisted_oompah"
  if git remote | grep -q '^trickle$'; then
    phase1_cleanup_repo "$TRICKLE_REPO" "trickle" "is_whitelisted_trickle"
  else
    warn "trickle remote not available — skipping trickle Phase 1"
  fi
fi

if $RUN_PHASE2; then
  phase2_reopen_oompah
  if git remote | grep -q '^trickle$'; then
    phase2_reopen_trickle
  else
    warn "trickle remote not available — skipping trickle Phase 2"
  fi
fi

info "Branch cleanup complete."
