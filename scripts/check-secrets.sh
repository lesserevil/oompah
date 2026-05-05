#!/usr/bin/env bash
# Paranoid secret scanner. Two responsibilities:
#
#   1. Refuse staged paths that should NEVER be committed (.env, the
#      contents of .oompah/, any *.netrc, any private-key blob).
#   2. Grep staged content for known token shapes (Anthropic sk-,
#      GitHub PATs, GitLab PATs, AWS keys, Slack tokens, generic JWTs,
#      private-key headers).
#
# Designed to run from .pre-commit-config.yaml as a "local" hook AND
# directly from a Makefile target / shell. Exits non-zero on any hit.
#
# Usage:
#   scripts/check-secrets.sh                # scan staged diff
#   scripts/check-secrets.sh --files <a> <b>  # scan specific files
#   scripts/check-secrets.sh --all          # scan whole working tree

set -euo pipefail

RED=$'\033[0;31m'
YELLOW=$'\033[0;33m'
NC=$'\033[0m'

err() { printf '%s%s%s\n' "$RED" "$*" "$NC" >&2; }
warn() { printf '%s%s%s\n' "$YELLOW" "$*" "$NC" >&2; }

# ---------------------------------------------------------------------------
# Path-based forbidden list. These should NEVER be in a commit, ever.
# Listing each pattern explicitly because anchored regexes catch things a
# single match wouldn't (e.g. a renamed copy of providers.json).
# ---------------------------------------------------------------------------
FORBIDDEN_PATHS=(
    '^\.env$'
    '^\.env\.local$'
    '^\.env\.production$'
    '^\.env\.development$'
    '^\.env\.dev$'
    '^\.env\.prod$'
    '^.*\.netrc$'
    '^\.oompah/.*\.json$'
    '^.*/\.oompah/.*\.json$'
    '^.*\.pem$'
    '^.*_id_rsa$'
    '^.*_id_ed25519$'
    '^id_rsa$'
    '^id_ed25519$'
)
# .env.example, .env.template, etc. are committable templates with
# placeholder values — they don't match any of the patterns above.

# ---------------------------------------------------------------------------
# Content patterns. Anything matching is a fail. Comments aren't safe —
# people leave keys in comments while debugging.
# ---------------------------------------------------------------------------
SECRET_PATTERNS=(
    'sk-[A-Za-z0-9_-]{20,}'                         # Anthropic / OpenAI / LiteLLM virtual keys
    'sk-ant-[A-Za-z0-9_-]{40,}'                     # Anthropic specifically
    'ghp_[A-Za-z0-9]{36,}'                          # GitHub Personal Access Token
    'github_pat_[A-Za-z0-9_]{82,}'                  # GitHub fine-grained PAT
    'gho_[A-Za-z0-9]{36,}'                          # GitHub OAuth
    'ghu_[A-Za-z0-9]{36,}'                          # GitHub user-to-server
    'ghs_[A-Za-z0-9]{36,}'                          # GitHub server-to-server
    'glpat-[A-Za-z0-9_-]{20,}'                      # GitLab PAT
    'AKIA[0-9A-Z]{16}'                              # AWS Access Key ID
    'ASIA[0-9A-Z]{16}'                              # AWS temporary access key
    'xox[baprs]-[A-Za-z0-9-]{10,}'                  # Slack tokens
    '-----BEGIN [A-Z ]*PRIVATE KEY-----'            # Private keys in any format
    'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}'  # JWT (header.payload.sig)
)

# ---------------------------------------------------------------------------
# Mode parsing
# ---------------------------------------------------------------------------
mode="staged"
explicit_files=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)    mode="all"; shift ;;
        --files)  mode="files"; shift; explicit_files=("$@"); break ;;
        *)        explicit_files+=("$1"); mode="files"; shift ;;
    esac
done

# Determine the file list to scan.
case "$mode" in
    staged)
        # Only newly-staged or modified content. Includes file additions.
        files=()
        while IFS= read -r line; do files+=("$line"); done < <(git diff --cached --name-only --diff-filter=ACM)
        ;;
    files)
        files=("${explicit_files[@]}")
        ;;
    all)
        # Whole tree, respecting .gitignore. Useful for ad-hoc audits.
        files=()
        while IFS= read -r line; do files+=("$line"); done < <(git ls-files)
        ;;
esac

if [[ ${#files[@]} -eq 0 ]]; then
    exit 0
fi

# ---------------------------------------------------------------------------
# Pass 1: forbidden paths
# ---------------------------------------------------------------------------
declare -i path_violations=0
for f in "${files[@]}"; do
    [[ -z "$f" ]] && continue
    for pat in "${FORBIDDEN_PATHS[@]}"; do
        if [[ "$f" =~ $pat ]]; then
            err "FORBIDDEN PATH: $f matches $pat"
            err "  This file is on the do-not-commit list. If it's a new"
            err "  config file that should be committed, edit"
            err "  scripts/check-secrets.sh::FORBIDDEN_PATHS first."
            path_violations+=1
        fi
    done
done

# ---------------------------------------------------------------------------
# Pass 2: content patterns. Scan each file's CURRENT content (or the
# staged blob, if running on staged diff and the file is staged).
# ---------------------------------------------------------------------------
declare -i content_violations=0
for f in "${files[@]}"; do
    [[ -z "$f" ]] && continue
    [[ ! -f "$f" ]] && continue

    # Skip binaries — bash regex on raw bytes is unsafe and grep -I handles it.
    if file -b --mime "$f" 2>/dev/null | grep -q 'charset=binary'; then
        continue
    fi

    # Read the staged blob if we're in staged mode and the file is in the
    # index — otherwise the working tree might already have been corrected
    # since `git add` and we'd miss the staged secret.
    if [[ "$mode" == "staged" ]]; then
        content=$(git show ":$f" 2>/dev/null || cat "$f")
    else
        content=$(cat "$f")
    fi

    for pat in "${SECRET_PATTERNS[@]}"; do
        # Filter out lines that explicitly mark themselves as test
        # fixtures or known-safe values via the pragma. The pragma must
        # be on the SAME line as the apparent secret.
        # detect-secrets-style marker: "# pragma: allowlist secret"
        matches=$(printf '%s' "$content" | grep -nE -- "$pat" 2>/dev/null \
            | grep -vE 'pragma:\s*allowlist\s*secret' || true)
        if [[ -n "$matches" ]]; then
            err "SECRET MATCH in $f: pattern /$pat/"
            err "  First matching line:"
            printf '%s' "$matches" | head -1 | sed 's/^/    /' >&2
            err "  (To allowlist a known-safe value, add"
            err "  '# pragma: allowlist secret' on the same line.)"
            content_violations+=1
        fi
    done
done

# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------
if [[ $path_violations -gt 0 || $content_violations -gt 0 ]]; then
    err ""
    err "BLOCKED: $path_violations forbidden path(s), $content_violations secret content match(es)."
    err "If you're certain this is a false positive, override with --no-verify"
    err "ONLY when you've manually confirmed nothing sensitive is being committed."
    exit 1
fi

exit 0
