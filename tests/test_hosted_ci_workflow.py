from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HOSTED_CI_WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"


def _hosted_ci_workflow() -> str:
    return HOSTED_CI_WORKFLOW.read_text(encoding="utf-8")


def test_hosted_ci_provisions_the_required_os_sandbox() -> None:
    workflow = _hosted_ci_workflow()

    assert "apt_get install --yes bubblewrap iproute2" in workflow
    assert "kernel.apparmor_restrict_unprivileged_userns=0" in workflow
    assert "kernel.unprivileged_userns_clone=1" in workflow
    assert workflow.count("--unshare-user") >= 2
    assert workflow.count("--unshare-pid") >= 2
    assert workflow.count("--unshare-net") >= 2
    assert "--cap-add CAP_NET_ADMIN" in workflow
    assert "ip link show lo" in workflow


def test_hosted_ci_uses_the_supported_makefile_gate() -> None:
    workflow = _hosted_ci_workflow()

    assert 'python-version: ["3.12"]' in workflow
    assert "UV_PYTHON: ${{ matrix.python-version }}" in workflow
    assert 'OOMPAH_PYTEST_WORKERS: "2"' in workflow
    assert "python -m pip install --upgrade pip uv" in workflow
    assert "make test-setup" in workflow
    assert "run: make test" in workflow
    assert "run: pytest" not in workflow
    assert 'pip install -e ".[dev]"' not in workflow


def test_hosted_pull_request_ci_checks_out_the_immutable_review_head() -> None:
    workflow = _hosted_ci_workflow()

    assert "uses: actions/checkout@v4" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow


def test_hosted_ci_configures_the_canonical_git_identity() -> None:
    workflow = _hosted_ci_workflow()

    assert "git config --global user.name oompah" in workflow
    assert (
        "git config --global user.email lesserevil@users.noreply.github.com"
        in workflow
    )
