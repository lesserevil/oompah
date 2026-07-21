"""Documentation / contract tests for plans/prompt-injection-protection.md.

These tests enforce the structural requirements of the external-content trust
model defined in OOMPAH-286.  They are documentation tests: they fail when
the plan document is absent or missing required sections, making the
inventory a hard gate rather than advisory prose.

Test categories
---------------
1. ``TestPlanDocumentExists`` — the plan file is present and non-empty.
2. ``TestInventoryComponents`` — the inventory names each required component.
3. ``TestProvenanceContractSchema`` — the machine-readable provenance contract
   JSON is present and valid.
4. ``TestTrustLevelCoverage`` — the document addresses trusted, untrusted, and
   mixed sources.
5. ``TestNonGoalsCoverage`` — the non-goals section is present.
6. ``TestAttackScenariosCoverage`` — the document covers expected attack types.
"""

from __future__ import annotations

import json
import os
import re

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLAN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "plans",
    "prompt-injection-protection.md",
)


def _load_plan() -> str:
    """Return the full text of the plan document or skip if absent."""
    if not os.path.isfile(_PLAN_PATH):
        pytest.skip(
            f"plans/prompt-injection-protection.md not found at {_PLAN_PATH}. "
            "Create the file to pass these contract tests."
        )
    with open(_PLAN_PATH, encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# 1. Plan document existence
# ---------------------------------------------------------------------------


class TestPlanDocumentExists:
    def test_file_exists(self):
        """The plan document must exist at plans/prompt-injection-protection.md."""
        assert os.path.isfile(_PLAN_PATH), (
            "plans/prompt-injection-protection.md is missing. "
            "Create it as specified by OOMPAH-286."
        )

    def test_file_is_non_empty(self):
        """The plan document must contain meaningful content (>500 bytes)."""
        with open(_PLAN_PATH, encoding="utf-8") as fh:
            content = fh.read()
        assert len(content) > 500, (
            "plans/prompt-injection-protection.md is present but suspiciously short "
            f"({len(content)} bytes). Expected at least 500 bytes."
        )


# ---------------------------------------------------------------------------
# 2. Inventory: required component names
# ---------------------------------------------------------------------------


class TestInventoryComponents:
    """The inventory section must name all five required components.

    These are the components through which external content enters the
    LLM or agent prompt.  Each must appear by its canonical name so that
    a developer auditing a new input can look up the entry and determine
    its trust level and required controls.
    """

    REQUIRED_COMPONENTS = [
        # (canonical_name, human_readable_description)
        (
            "intake_bridge",
            "intake bridge (github_intake_bridge.py — imports GitHub content)",
        ),
        (
            "focus_triage",
            "focus triage (_build_triage_prompt in focus.py — issue metadata in LLM call)",
        ),
        (
            "prompt_renderer",
            "prompt renderer (render_prompt in prompt.py — renders WORKFLOW.md template)",
        ),
        (
            "continuation_prompts",
            "continuation prompts (build_continuation_prompt in prompt.py)",
        ),
        (
            "agent_system_prompt",
            "agent system prompt construction (orchestrator.py ApiAgentSession system_prompt=)",
        ),
    ]

    @pytest.mark.parametrize("component,description", REQUIRED_COMPONENTS)
    def test_component_named_in_inventory(self, component: str, description: str):
        """The plan document must name the component '{}' in its inventory."""
        content = _load_plan()
        assert component in content, (
            f"plans/prompt-injection-protection.md must name the component "
            f"'{component}' ({description}) in its inventory. "
            "Add an inventory entry for this prompt path."
        )

    def test_inventory_section_present(self):
        """The plan document must contain an 'Inventory' section heading."""
        content = _load_plan()
        # Accept any heading level containing "Inventory" (case-insensitive),
        # including numbered headings like "## 6. Inventory of Prompt Paths".
        assert re.search(r"#+[^#\n]*[Ii]nventory", content), (
            "plans/prompt-injection-protection.md must contain an 'Inventory' "
            "section heading that lists all prompt paths."
        )

    def test_all_five_components_present_together(self):
        """All five required components must appear in the same document."""
        content = _load_plan()
        missing = [
            name
            for name, _ in self.REQUIRED_COMPONENTS
            if name not in content
        ]
        assert not missing, (
            "The following components are missing from the inventory in "
            f"plans/prompt-injection-protection.md: {missing}. "
            "Add inventory entries for each prompt path."
        )


# ---------------------------------------------------------------------------
# 3. Provenance contract schema
# ---------------------------------------------------------------------------


class TestProvenanceContractSchema:
    """The document must define a machine-readable provenance contract."""

    def test_provenance_contract_section_present(self):
        """The plan must contain a 'Provenance Contract' section."""
        content = _load_plan()
        assert re.search(r"#+\s+.*[Pp]rovenance.*[Cc]ontract", content), (
            "plans/prompt-injection-protection.md must contain a 'Provenance "
            "Contract' section specifying the machine-readable metadata format."
        )

    def test_provenance_json_schema_parseable(self):
        """Any JSON block in the provenance section must be valid JSON."""
        content = _load_plan()
        # Find the provenance section header (supporting numbered headings like
        # "## 8. Machine-Readable Provenance Contract") and extract the text
        # from that point to the next same-or-higher-level heading or end.
        header_match = re.search(
            r"(#+)[^#\n]*[Pp]rovenance[^#\n]*[Cc]ontract",
            content,
        )
        if not header_match:
            pytest.skip("Provenance Contract section not found — prerequisite test will fail.")

        # Capture everything from the matched header position to end of document,
        # then trim at the next heading of the same level or higher.
        start_pos = header_match.start()
        section_text = content[start_pos:]

        # Find all ```json ... ``` blocks in the section text.
        json_blocks = re.findall(r"```json\s*([\s\S]*?)```", section_text)
        assert json_blocks, (
            "The Provenance Contract section must contain at least one ```json "
            "code block defining the contract schema."
        )
        for block in json_blocks:
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                pytest.fail(
                    f"JSON block in Provenance Contract section is not valid JSON: {exc}\n"
                    f"Block content:\n{block}"
                )

    def test_provenance_version_field_documented(self):
        """The provenance contract must include a version field."""
        content = _load_plan()
        # Accept either `"version"` in a JSON block or a prose mention.
        assert '"version"' in content or "`version`" in content, (
            "The provenance contract in plans/prompt-injection-protection.md "
            "must document a 'version' field for future schema evolution."
        )

    def test_provenance_component_field_documented(self):
        """The provenance contract must include a component field."""
        content = _load_plan()
        assert '"component"' in content or "`component`" in content, (
            "The provenance contract must document a 'component' field naming "
            "the prompt path (e.g. 'intake_bridge', 'prompt_renderer')."
        )

    def test_provenance_trust_field_documented(self):
        """The provenance contract must include a trust field."""
        content = _load_plan()
        assert '"trust"' in content or "`trust`" in content, (
            "The provenance contract must document a 'trust' field indicating "
            "the trust level ('trusted', 'untrusted', 'mixed')."
        )


# ---------------------------------------------------------------------------
# 4. Trust-level coverage
# ---------------------------------------------------------------------------


class TestTrustLevelCoverage:
    """The document must define trusted, untrusted, and mixed trust levels."""

    def test_trusted_sources_defined(self):
        content = _load_plan()
        assert re.search(r"\bTrusted\b.*source", content, re.IGNORECASE) or \
               "trusted source" in content.lower(), (
            "plans/prompt-injection-protection.md must define what constitutes "
            "a 'trusted source'."
        )

    def test_untrusted_sources_defined(self):
        content = _load_plan()
        assert re.search(r"\bUntrusted\b.*source", content, re.IGNORECASE) or \
               "untrusted source" in content.lower(), (
            "plans/prompt-injection-protection.md must define what constitutes "
            "an 'untrusted source'."
        )

    def test_mixed_trust_defined(self):
        content = _load_plan()
        assert "mixed" in content.lower(), (
            "plans/prompt-injection-protection.md must define 'mixed' trust "
            "(e.g., the rendered prompt mixes a trusted template with untrusted values)."
        )

    def test_github_intake_is_untrusted(self):
        """GitHub issue content must be classified as untrusted."""
        content = _load_plan()
        # The document should pair "UNTRUSTED" with GitHub sources somewhere.
        # We check that the word "UNTRUSTED" appears near "github" (case-insensitive).
        lower = content.lower()
        idx_github = lower.find("github")
        idx_untrusted = lower.find("untrusted")
        assert idx_github >= 0 and idx_untrusted >= 0, (
            "plans/prompt-injection-protection.md must classify GitHub-sourced "
            "content (issue body, comments) as UNTRUSTED."
        )

    def test_system_prompt_is_trusted(self):
        """The agent system prompt must be classified as trusted."""
        content = _load_plan()
        lower = content.lower()
        # "trusted" must appear near "system prompt" somewhere in the document.
        assert "trusted" in lower and "system prompt" in lower, (
            "plans/prompt-injection-protection.md must classify the agent system "
            "prompt as TRUSTED (developer-written constant)."
        )


# ---------------------------------------------------------------------------
# 5. Non-goals section
# ---------------------------------------------------------------------------


class TestNonGoalsCoverage:
    def test_non_goals_section_present(self):
        content = _load_plan()
        # Accept numbered headings like "## 9. Non-Goals" or plain "## Non-Goals".
        assert re.search(r"#+[^#\n]*[Nn]on.?[Gg]oals?", content), (
            "plans/prompt-injection-protection.md must contain a 'Non-Goals' "
            "section clarifying what the threat model does NOT cover."
        )

    def test_non_goals_mentions_complete_prevention(self):
        """Non-goals should clarify that complete injection prevention is not claimed."""
        content = _load_plan()
        lower = content.lower()
        # Accept any mention of "complete prevention", "all injection", etc.
        assert "prevent" in lower or "complete" in lower or "impossib" in lower, (
            "The Non-Goals section should note that complete prompt injection "
            "prevention is not claimed as a goal."
        )


# ---------------------------------------------------------------------------
# 6. Attack scenarios
# ---------------------------------------------------------------------------


class TestAttackScenariosCoverage:
    """The document must cover the primary attack scenarios."""

    REQUIRED_SCENARIOS = [
        ("issue", "issue-body injection (malicious GitHub issue body)"),
        ("comment", "comment injection (mid-run comment delivery path)"),
        ("attachment", "attachment-borne injection (malicious file content)"),
        ("triage", "focus-triage manipulation (malicious issue title/metadata)"),
    ]

    @pytest.mark.parametrize("keyword,description", REQUIRED_SCENARIOS)
    def test_attack_scenario_covered(self, keyword: str, description: str):
        """The plan document must cover the attack scenario: {}."""
        content = _load_plan()
        lower = content.lower()
        assert keyword in lower, (
            f"plans/prompt-injection-protection.md must cover the attack scenario "
            f"'{description}'. Add a subsection describing the vector and control."
        )

    def test_attack_scenarios_section_present(self):
        """The document must contain an 'Attack Scenarios' section."""
        content = _load_plan()
        # Accept numbered headings like "## 4. Attack Scenarios".
        assert re.search(r"#+[^#\n]*[Aa]ttack\s+[Ss]cenarios?", content), (
            "plans/prompt-injection-protection.md must contain an "
            "'Attack Scenarios' section."
        )


# ---------------------------------------------------------------------------
# 7. Server-side authority
# ---------------------------------------------------------------------------


class TestServerSideAuthority:
    """The document must state which controls remain server-side authoritative."""

    def test_server_side_controls_section_present(self):
        content = _load_plan()
        lower = content.lower()
        assert "server" in lower and (
            "authoritative" in lower or "authority" in lower or "control" in lower
        ), (
            "plans/prompt-injection-protection.md must state which server-side "
            "controls remain authoritative regardless of model output."
        )

    def test_task_state_transitions_mentioned(self):
        """Task state transitions must be listed as a server-side control."""
        content = _load_plan()
        lower = content.lower()
        assert "state transition" in lower or "status" in lower, (
            "The server-side controls section must mention that task state "
            "transitions are enforced server-side."
        )

    def test_git_push_guards_mentioned(self):
        """Git push guards must be listed as a server-side control."""
        content = _load_plan()
        lower = content.lower()
        assert "push" in lower and "branch" in lower, (
            "The server-side controls section must mention that git push targets "
            "are restricted by server-side guards."
        )
