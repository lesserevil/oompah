#!/usr/bin/env bash
# scripts/runner.sh — Manage the Oompah self-hosted GitHub Actions runner container.
#
# Usage:
#   ./scripts/runner.sh setup    Register a new runner (fetches registration token)
#   ./scripts/runner.sh start    Start the runner container
#   ./scripts/runner.sh stop     Stop the runner container
#   ./scripts/runner.sh status   Print runner container status
#
# Required environment variables (set in .env or shell):
#   GITHUB_TOKEN          — PAT with "Self-hosted runners: Read and write" permission
#
# Optional environment variables (all have defaults):
#   OOMPAH_RUNNER_REPO         — target repo (default: lesserevil/oompah)
#   OOMPAH_RUNNER_NAME         — runner name (default: oompah-runner)
#   OOMPAH_RUNNER_LABELS       — comma-separated labels (default: self-hosted,linux,x64,oompah)
#   OOMPAH_RUNNER_IMAGE        — container image (default: ghcr.io/actions/actions-runner:2.323.0)
#   OOMPAH_RUNNER_WORKDIR      — host dir for runner data (default: .runner-data)
#   OOMPAH_RUNNER_CONTAINER    — container name (default: oompah-actions-runner)
#   CONTAINER_CMD              — container runtime (default: auto-detect podman or docker)
#
# Note: GitHub Actions does NOT support an OR expression between GitHub-hosted and
# self-hosted runner labels (e.g. `ubuntu-latest OR oompah`). Setting `runs-on:
# [self-hosted, oompah]` means the job ONLY runs on the self-hosted runner — making
# the local runner the sole required capacity. See docs/self-hosted-runner.md.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
OOMPAH_RUNNER_REPO="${OOMPAH_RUNNER_REPO:-lesserevil/oompah}"
OOMPAH_RUNNER_NAME="${OOMPAH_RUNNER_NAME:-oompah-runner}"
OOMPAH_RUNNER_LABELS="${OOMPAH_RUNNER_LABELS:-self-hosted,linux,x64,oompah}"
OOMPAH_RUNNER_IMAGE="${OOMPAH_RUNNER_IMAGE:-ghcr.io/actions/actions-runner:2.323.0}"
OOMPAH_RUNNER_WORKDIR="${OOMPAH_RUNNER_WORKDIR:-.runner-data}"
OOMPAH_RUNNER_CONTAINER="${OOMPAH_RUNNER_CONTAINER:-oompah-actions-runner}"

# Load .env if present (only variables not already set in environment)
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# Re-read after .env (env vars set before sourcing take priority)
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
OOMPAH_RUNNER_REPO="${OOMPAH_RUNNER_REPO:-lesserevil/oompah}"
OOMPAH_RUNNER_NAME="${OOMPAH_RUNNER_NAME:-oompah-runner}"
OOMPAH_RUNNER_LABELS="${OOMPAH_RUNNER_LABELS:-self-hosted,linux,x64,oompah}"
OOMPAH_RUNNER_IMAGE="${OOMPAH_RUNNER_IMAGE:-ghcr.io/actions/actions-runner:2.323.0}"
OOMPAH_RUNNER_WORKDIR="${OOMPAH_RUNNER_WORKDIR:-.runner-data}"
OOMPAH_RUNNER_CONTAINER="${OOMPAH_RUNNER_CONTAINER:-oompah-actions-runner}"

# Auto-detect container runtime
if [ -n "${CONTAINER_CMD:-}" ]; then
    _CONTAINER_CMD="$CONTAINER_CMD"
elif command -v podman >/dev/null 2>&1; then
    _CONTAINER_CMD="podman"
elif command -v docker >/dev/null 2>&1; then
    _CONTAINER_CMD="docker"
else
    echo "ERROR: Neither podman nor docker found. Install one first." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_require_token() {
    if [ -z "$GITHUB_TOKEN" ]; then
        echo "ERROR: GITHUB_TOKEN is not set." >&2
        echo "Set it in .env or export it in your shell." >&2
        echo "The token needs 'Self-hosted runners: Read and write' permission." >&2
        exit 1
    fi
}

_fetch_registration_token() {
    local repo="$1"
    local token
    token=$(curl -sf \
        -X POST \
        -H "Accept: application/vnd.github+json" \
        -H "Authorization: Bearer ${GITHUB_TOKEN}" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "https://api.github.com/repos/${repo}/actions/runners/registration-token" \
        | grep -o '"token":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$token" ]; then
        echo "ERROR: Failed to fetch registration token for ${repo}." >&2
        echo "Ensure GITHUB_TOKEN has 'Self-hosted runners: Read and write' permission." >&2
        exit 1
    fi
    echo "$token"
}

_runner_running() {
    "$_CONTAINER_CMD" ps --filter "name=^${OOMPAH_RUNNER_CONTAINER}$" --format "{{.Names}}" 2>/dev/null \
        | grep -q "^${OOMPAH_RUNNER_CONTAINER}$"
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_setup() {
    _require_token

    echo "==> Fetching GitHub Actions registration token for ${OOMPAH_RUNNER_REPO}..."
    local reg_token
    reg_token=$(_fetch_registration_token "$OOMPAH_RUNNER_REPO")

    echo "==> Creating work directory: ${OOMPAH_RUNNER_WORKDIR}"
    mkdir -p "${OOMPAH_RUNNER_WORKDIR}"

    # Save the registration token to workdir (not .env — it's short-lived)
    printf '%s' "$reg_token" > "${OOMPAH_RUNNER_WORKDIR}/registration-token"
    chmod 600 "${OOMPAH_RUNNER_WORKDIR}/registration-token"

    # Run a one-shot configure step inside the container
    echo "==> Configuring runner '${OOMPAH_RUNNER_NAME}' with labels: ${OOMPAH_RUNNER_LABELS}"
    "$_CONTAINER_CMD" run --rm \
        -v "$(pwd)/${OOMPAH_RUNNER_WORKDIR}:/runner-data:z" \
        --name "${OOMPAH_RUNNER_CONTAINER}-configure" \
        --entrypoint /bin/bash \
        "${OOMPAH_RUNNER_IMAGE}" \
        -c "
            cp -r /home/runner/. /runner-data/
            cd /runner-data
            ./config.sh \
                --url 'https://github.com/${OOMPAH_RUNNER_REPO}' \
                --token '${reg_token}' \
                --name '${OOMPAH_RUNNER_NAME}' \
                --labels '${OOMPAH_RUNNER_LABELS}' \
                --unattended \
                --replace
        "

    # Remove token after use
    rm -f "${OOMPAH_RUNNER_WORKDIR}/registration-token"

    echo "==> Runner configured successfully."
    echo "    Run 'make runner-start' (or './scripts/runner.sh start') to launch it."
}

cmd_start() {
    if [ ! -d "${OOMPAH_RUNNER_WORKDIR}" ]; then
        echo "ERROR: Runner not configured yet. Run './scripts/runner.sh setup' first." >&2
        exit 1
    fi

    if _runner_running; then
        echo "Runner container '${OOMPAH_RUNNER_CONTAINER}' is already running."
        return 0
    fi

    # Remove any stopped container with the same name
    "$_CONTAINER_CMD" rm -f "${OOMPAH_RUNNER_CONTAINER}" 2>/dev/null || true

    echo "==> Starting runner container '${OOMPAH_RUNNER_CONTAINER}'..."
    "$_CONTAINER_CMD" run -d \
        --name "${OOMPAH_RUNNER_CONTAINER}" \
        --restart unless-stopped \
        -v "$(pwd)/${OOMPAH_RUNNER_WORKDIR}:/runner-data:z" \
        --entrypoint /bin/bash \
        "${OOMPAH_RUNNER_IMAGE}" \
        -c "cd /runner-data && ./run.sh"

    echo "==> Runner started. Check status with 'make runner-status'."
}

cmd_stop() {
    if _runner_running; then
        echo "==> Stopping runner container '${OOMPAH_RUNNER_CONTAINER}'..."
        "$_CONTAINER_CMD" stop "${OOMPAH_RUNNER_CONTAINER}"
        "$_CONTAINER_CMD" rm -f "${OOMPAH_RUNNER_CONTAINER}" 2>/dev/null || true
        echo "==> Runner stopped."
    else
        echo "Runner container '${OOMPAH_RUNNER_CONTAINER}' is not running."
    fi
}

cmd_status() {
    echo "Container runtime: ${_CONTAINER_CMD}"
    echo "Container name:    ${OOMPAH_RUNNER_CONTAINER}"
    echo "Runner image:      ${OOMPAH_RUNNER_IMAGE}"
    echo "Target repo:       ${OOMPAH_RUNNER_REPO}"
    echo "Runner name:       ${OOMPAH_RUNNER_NAME}"
    echo "Runner labels:     ${OOMPAH_RUNNER_LABELS}"
    echo ""

    if _runner_running; then
        echo "Status: RUNNING"
        "$_CONTAINER_CMD" ps --filter "name=^${OOMPAH_RUNNER_CONTAINER}$" --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
    else
        echo "Status: STOPPED (container '${OOMPAH_RUNNER_CONTAINER}' not running)"
    fi

    # Show GitHub API status if token is available (no error if missing)
    if [ -n "$GITHUB_TOKEN" ]; then
        echo ""
        echo "GitHub API runner registration status:"
        curl -sf \
            -H "Accept: application/vnd.github+json" \
            -H "Authorization: Bearer ${GITHUB_TOKEN}" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            "https://api.github.com/repos/${OOMPAH_RUNNER_REPO}/actions/runners" \
            2>/dev/null \
        | python3 -c "
import json, sys
data = json.load(sys.stdin)
runners = data.get('runners', [])
if not runners:
    print('  No runners registered.')
else:
    for r in runners:
        labels = ', '.join(l['name'] for l in r.get('labels', []))
        print(f'  [{r[\"status\"].upper()}] {r[\"name\"]} (id={r[\"id\"]}) labels={labels}')
" 2>/dev/null || echo "  (could not fetch — check GITHUB_TOKEN permissions)"
    fi
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMAND="${1:-}"
case "$COMMAND" in
    setup)   cmd_setup ;;
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    status)  cmd_status ;;
    *)
        echo "Usage: $0 {setup|start|stop|status}" >&2
        echo ""
        echo "Commands:"
        echo "  setup   Register runner with GitHub (requires GITHUB_TOKEN)"
        echo "  start   Start the runner container"
        echo "  stop    Stop the runner container"
        echo "  status  Show runner container and GitHub registration status"
        exit 1
        ;;
esac
