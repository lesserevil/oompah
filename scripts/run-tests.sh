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
        configured_root="${HOME}/${configured_root#~/}"
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

export OOMPAH_PYTEST_RUN_ROOT="${test_run_root}"

if (( $# > 0 )); then
    test_targets=("$@")
else
    test_targets=(tests/)
fi
pytest_args=("${test_targets[@]}" -v --basetemp "${test_run_root}/basetemp")
if [[ "${mode}" == "parallel" ]]; then
    pytest_args+=(-n "${workers}" --dist loadgroup)
    echo "Running pytest with ${workers} isolated workers under ${test_run_root}"
else
    echo "Running pytest serially under ${test_run_root}"
fi

set +e
uv run pytest "${pytest_args[@]}"
test_status=$?
set -e
exit "${test_status}"
