from __future__ import annotations

import importlib.util
from pathlib import Path
import tomllib

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "cli-release.yml"
SCRIPT_PATH = REPO_ROOT / "scripts" / "render_cli_release_notes.py"


def _load_release_notes_module():
    spec = importlib.util.spec_from_file_location(
        "render_cli_release_notes", SCRIPT_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_notes_include_exact_tag_and_artifact_install_commands():
    module = _load_release_notes_module()

    notes = module.render_release_notes(
        tag="v1.0.0",
        wheel_name="oompah-1.0.0-py3-none-any.whl",
        sdist_name="oompah-1.0.0.tar.gz",
    )

    assert (
        'uv tool install "git+https://github.com/lesserevil/oompah@v1.0.0"'
        in notes
    )
    assert (
        'pipx install "git+https://github.com/lesserevil/oompah@v1.0.0"'
        in notes
    )
    assert (
        'uv tool install "https://github.com/lesserevil/oompah/releases/download/'
        'v1.0.0/oompah-1.0.0-py3-none-any.whl"'
        in notes
    )
    assert (
        'pipx install "https://github.com/lesserevil/oompah/releases/download/'
        'v1.0.0/oompah-1.0.0-py3-none-any.whl"'
        in notes
    )
    assert "task CLI release" in notes
    assert "does not install or configure the oompah service runtime" in notes


def test_default_package_install_is_task_cli_only():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["project"]["dependencies"] == ["httpx>=0.27"]

    extras = data["project"]["optional-dependencies"]
    assert "server" in extras
    assert "fastapi>=0.115" in extras["server"]
    assert "uvicorn[standard]>=0.34" in extras["server"]
    assert "watchfiles>=1.0" in extras["server"]

    assert "fastapi>=0.115" in extras["dev"]
    assert "watchfiles>=1.0" in extras["dev"]
    assert "oompah[server]" in extras["all"]


def test_release_notes_renderer_validates_tag_and_artifacts(tmp_path):
    module = _load_release_notes_module()
    pyproject = tmp_path / "pyproject.toml"
    dist = tmp_path / "dist"
    dist.mkdir()
    pyproject.write_text(
        "[project]\nname = \"oompah\"\nversion = \"1.2.3\"\n",
        encoding="utf-8",
    )
    (dist / "oompah-1.2.3-py3-none-any.whl").write_text("", encoding="utf-8")
    (dist / "oompah-1.2.3.tar.gz").write_text("", encoding="utf-8")

    notes = module.render_release_notes_for_dist(
        tag="v1.2.3",
        pyproject_path=pyproject,
        dist_dir=dist,
    )

    assert "oompah-1.2.3-py3-none-any.whl" in notes
    assert "oompah-1.2.3.tar.gz" in notes


def test_release_notes_renderer_rejects_version_mismatched_tag(tmp_path):
    module = _load_release_notes_module()
    pyproject = tmp_path / "pyproject.toml"
    dist = tmp_path / "dist"
    dist.mkdir()
    pyproject.write_text(
        "[project]\nname = \"oompah\"\nversion = \"1.2.3\"\n",
        encoding="utf-8",
    )

    try:
        module.render_release_notes_for_dist(
            tag="v1.2.4",
            pyproject_path=pyproject,
            dist_dir=dist,
        )
    except ValueError as exc:
        assert "expected 'v1.2.3'" in str(exc)
    else:
        raise AssertionError("version-mismatched release tag was accepted")


def test_release_workflow_is_tag_or_manual_github_release_only():
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    triggers = workflow.get("on") or workflow.get(True)

    assert triggers["push"]["tags"] == ["v*"]
    assert "branches" not in triggers["push"]
    assert "workflow_dispatch" in triggers
    assert workflow["permissions"] == {"contents": "write"}

    assert "python -m build --sdist --wheel" in text
    assert "python -m pip install dist/*.whl" in text
    assert "oompah --help" in text
    assert "oompah task --help" in text
    assert "gh release create" in text
    assert "gh release upload" in text
    assert "scripts/render_cli_release_notes.py" in text

    lower = text.lower()
    assert "twine" not in lower
    assert "pypi" not in lower
    assert "id-token" not in lower


def test_release_docs_cover_tag_creation_and_verification_commands():
    text = (REPO_ROOT / "docs" / "cli-release.md").read_text(encoding="utf-8")

    assert 'git tag -a v1.0.0 -m "oompah v1.0.0"' in text
    assert "Actions > CLI Release" in text
    assert (
        'uv tool install "git+https://github.com/lesserevil/oompah@v1.0.0"'
        in text
    )
    assert (
        'pipx install "git+https://github.com/lesserevil/oompah@v1.0.0"'
        in text
    )
    assert (
        'uv tool install "https://github.com/lesserevil/oompah/releases/download/'
        'v1.0.0/oompah-1.0.0-py3-none-any.whl"'
        in text
    )
    assert (
        'pipx install "https://github.com/lesserevil/oompah/releases/download/'
        'v1.0.0/oompah-1.0.0-py3-none-any.whl"'
        in text
    )
    assert "standalone `oompah task` client" in text
    assert "does not install or configure" in text


def test_release_docs_describe_draft_and_final_tag_convention():
    text = (REPO_ROOT / "docs" / "cli-release.md").read_text(encoding="utf-8")

    # Docs must describe the 1.0 release train conventions
    assert "release/1.0" in text
    assert "v1.0.0-draft" in text
    assert "v1.0.0" in text
    # Draft tag is force-movable; final tag is immutable
    assert "force-move" in text or "force-movable" in text
    assert "immutable" in text or "must not be force-moved" in text or "must never be force-moved" in text


def test_release_workflow_accepts_any_version_tag():
    """Workflow tag trigger covers all version tags including draft and final forms."""
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    triggers = workflow.get("on") or workflow.get(True)

    # The v* wildcard must cover both v1.0.0-draft and v1.0.0
    assert "v*" in triggers["push"]["tags"]


# ---------------------------------------------------------------------------
# Draft release tag validation (OOMPAH-19)
# ---------------------------------------------------------------------------


def test_validate_tag_final_form_accepted():
    """v1.0.0 is accepted as the immutable final release tag for version 1.0.0."""
    module = _load_release_notes_module()
    # Must not raise
    module.validate_tag_matches_version("v1.0.0", "1.0.0")


def test_validate_tag_draft_form_accepted():
    """v1.0.0-draft is accepted as the force-movable draft tag for version 1.0.0."""
    module = _load_release_notes_module()
    # Must not raise
    module.validate_tag_matches_version("v1.0.0-draft", "1.0.0")


def test_validate_tag_rejects_mismatched_final_tag():
    """Final release validation still rejects a tag that does not match project.version."""
    module = _load_release_notes_module()
    try:
        module.validate_tag_matches_version("v1.0.1", "1.0.0")
    except ValueError as exc:
        assert "expected 'v1.0.0'" in str(exc)
    else:
        raise AssertionError("mismatched final tag was accepted")


def test_validate_tag_rejects_wrong_version_draft_tag():
    """Draft validation is explicit — only v{version}-draft, not any other version's draft."""
    module = _load_release_notes_module()
    try:
        module.validate_tag_matches_version("v2.0.0-draft", "1.0.0")
    except ValueError as exc:
        assert "expected 'v1.0.0'" in str(exc)
    else:
        raise AssertionError("wrong-version draft tag was accepted")


def test_is_draft_release_tag_true_for_draft_form():
    """is_draft_release_tag returns True for the explicit v{version}-draft form."""
    module = _load_release_notes_module()
    assert module.is_draft_release_tag("v1.0.0-draft", "1.0.0") is True


def test_is_draft_release_tag_false_for_final_form():
    """is_draft_release_tag returns False for the exact final release tag."""
    module = _load_release_notes_module()
    assert module.is_draft_release_tag("v1.0.0", "1.0.0") is False


def test_is_draft_release_tag_false_for_other_prerelease():
    """is_draft_release_tag rejects arbitrary pre-release suffixes (e.g. -rc1)."""
    module = _load_release_notes_module()
    assert module.is_draft_release_tag("v1.0.0-rc1", "1.0.0") is False


def test_render_notes_for_dist_accepts_draft_tag(tmp_path):
    """render_release_notes_for_dist succeeds when the tag is the draft form."""
    module = _load_release_notes_module()
    pyproject = tmp_path / "pyproject.toml"
    dist = tmp_path / "dist"
    dist.mkdir()
    pyproject.write_text(
        '[project]\nname = "oompah"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (dist / "oompah-1.0.0-py3-none-any.whl").write_text("", encoding="utf-8")
    (dist / "oompah-1.0.0.tar.gz").write_text("", encoding="utf-8")

    notes = module.render_release_notes_for_dist(
        tag="v1.0.0-draft",
        pyproject_path=pyproject,
        dist_dir=dist,
    )

    # Draft tag appears in install commands
    assert "v1.0.0-draft" in notes
    # Artifacts are still the 1.0.0 wheel and sdist (built from project.version)
    assert "oompah-1.0.0-py3-none-any.whl" in notes
    assert "oompah-1.0.0.tar.gz" in notes
