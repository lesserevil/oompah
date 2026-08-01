#!/usr/bin/env bash
set -euo pipefail

mode="${1:-parallel}"
shift || true
workers="${OOMPAH_PYTEST_WORKERS-4}"
configured_root="${OOMPAH_PYTEST_TEMP_ROOT:-${HOME}/.oompah/tmp}"

case "${configured_root}" in
    "~")
        configured_root="${HOME}"
        ;;
    "~/"*)
        configured_root="${HOME}/${configured_root:2}"
        ;;
esac

case "${mode}" in
    parallel)
        if ! [[ "${workers}" =~ ^[0-9]+$ ]] || (( workers < 1 || workers > 16 )); then
            echo "ERROR: OOMPAH_PYTEST_WORKERS must be an integer from 1 through 16 (got '${workers}')." >&2
            exit 2
        fi
        ;;
    serial)
        ;;
    *)
        echo "ERROR: test mode must be 'parallel' or 'serial' (got '${mode}')." >&2
        exit 2
        ;;
esac

test_parent="${configured_root}/pytest"
mkdir -p "${test_parent}"
chmod 700 "${test_parent}"
test_run_root="$(mktemp -d "${test_parent}/run.XXXXXX")"
test_lifecycle_root="${test_run_root}/lifecycle"
mkdir -p "${test_lifecycle_root}"

# A gate may run in a task worktree while the operator's service is alive in
# another checkout.  Do not inherit the service URL, credentials, or scoped
# task capability into tests.  Give any lifecycle test a private port and PID
# state rooted below this one disposable run directory.
test_server_port="$(python -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
export OOMPAH_PYTEST_GATE=1
export OOMPAH_PYTEST_RUN_ROOT="${test_run_root}"
export OOMPAH_TEST_SERVER_PORT="${test_server_port}"
export OOMPAH_SERVER_PORT="${test_server_port}"
export OOMPAH_TEST_PID_FILE="${test_lifecycle_root}/.oompah.pid"
export OOMPAH_TEST_PID_META_FILE="${test_lifecycle_root}/.oompah.pid.meta"
unset OOMPAH_SERVER_URL OOMPAH_SERVER_USERNAME OOMPAH_SERVER_PASSWORD \
    OOMPAH_SERVER_PASSWORD_FILE OOMPAH_TASK_HANDOFF_TOKEN \
    OOMPAH_TASK_HANDOFF_PROJECT_ID OOMPAH_TASK_HANDOFF_TASK_ID

cleanup_test_run() {
    case "${test_run_root}" in
        "${test_parent}"/run.*)
            rm -rf -- "${test_run_root}"
            ;;
        *)
            echo "WARNING: refusing to clean unexpected pytest run root '${test_run_root}'." >&2
            ;;
    esac
}
trap cleanup_test_run EXIT

export PYTHONPYCACHEPREFIX="${test_run_root}/pycache"

if (( $# > 0 )); then
    test_targets=("$@")
else
    test_targets=(tests/)
fi
pytest_args=(
    "${test_targets[@]}"
    -v
    --basetemp "${test_run_root}/basetemp"
    -o "cache_dir=${test_run_root}/pytest-cache"
)
if [[ "${mode}" == "parallel" ]]; then
    # Bound worker restarts to zero.  Signal-based test timeouts (pyproject
    # ``timeout_method = "signal"``) already keep an intentionally timing-out
    # test from tearing down its worker, so a lost worker under the parallel
    # gate now indicates a genuine crash rather than an expected timeout.
    # Restarting a crashed worker triggers the LoadScopeScheduling /
    # LoadGroupScheduling KeyError family tracked by OOMPAH-675: xdist re-
    # attaches events for a replaced ``WorkerController`` whose scheduler
    # bookkeeping has already been popped, and the run aborts partway through
    # without the original crash identity.  Failing fast on the first genuine
    # crash preserves the responsible test's identity in the terminal report
    # and lets the operator re-run the gate.
    pytest_args+=(-n "${workers}" --dist loadgroup --max-worker-restart=0)
    echo "Running pytest with ${workers} isolated workers under ${test_run_root}"
else
    echo "Running pytest serially under ${test_run_root}"
fi

set +e
# Make exports .venv/bin ahead of the system PATH, and test-setup installs this
# project's editable test dependencies there.  Invoke that interpreter directly
# so an already-prepared gate does not require a second uv subprocess.
python -m pytest "${pytest_args[@]}"
test_status=$?
set -e
exit "${test_status}"
