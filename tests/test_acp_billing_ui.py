"""Tests for the billing_model UI affordances on /providers.

Covers the oompah-zlz_2-ag7h additions to the Add/Edit Provider dialog:

* Two-option radio group: subscription (flat-rate) vs per_token.
* "model_costs are ignored" hint shown only when subscription selected.
* openProviderDialog seeds radios from provider.billing_model.
* submitProvider sends billing_model in the request body.

See bead oompah-zlz_2-ag7h.
"""

from __future__ import annotations

import os
import re

import pytest


def _load_providers_html() -> str:
    path = os.path.join(
        os.path.dirname(__file__),
        os.pardir,
        "oompah",
        "templates",
        "providers.html",
    )
    with open(path, "r") as f:
        return f.read()


@pytest.fixture(scope="module")
def html() -> str:
    return _load_providers_html()


@pytest.fixture(scope="module")
def script(html: str) -> str:
    matches = re.findall(r"<script[^>]*>(.*?)</script>", html, re.DOTALL)
    assert matches
    return "\n".join(matches)


# ----------------------------------------------------------------------
# Radio group markup
# ----------------------------------------------------------------------


class TestBillingModelRadioGroup:
    def test_radio_group_present(self, html):
        """Two-option radio group lives in the provider dialog."""
        assert 'name="prov-billing-model"' in html
        assert 'value="subscription"' in html
        assert 'value="per_token"' in html

    def test_default_is_subscription_checked(self, html):
        """Subscription is checked by default — matches the
        ModelProvider field default and preserves back-compat for
        operators clicking 'Add Provider' without thinking about it."""
        m = re.search(
            r'<input[^>]*name="prov-billing-model"[^>]*value="subscription"[^>]*checked',
            html,
        )
        assert m, "subscription radio should be checked by default"

    def test_per_token_not_checked_by_default(self, html):
        m = re.search(
            r'<input[^>]*name="prov-billing-model"[^>]*value="per_token"[^>]*checked',
            html,
        )
        assert m is None, "per_token must not be the default"

    def test_labels_mention_budget(self, html):
        """The labels must explain the difference so the operator
        doesn't have to read the bead to understand the choice."""
        # Subscription label calls out flat-rate.
        assert "flat-rate" in html
        # Per-token label calls out budget tracking.
        assert "tracked against budget" in html


# ----------------------------------------------------------------------
# Hint / "model_costs ignored" inline note
# ----------------------------------------------------------------------


class TestBillingModelHint:
    def test_subscription_note_present(self, html):
        """The 'model_costs are ignored when subscription' hint must
        exist so the operator understands an obvious UI pitfall."""
        assert 'id="prov-billing-subscription-note"' in html
        assert "ignored at billing time" in html

    def test_hint_explains_both_modes(self, html):
        """The persistent hint paragraph mentions both subscription
        (bypasses budget) and per-token (meters against rolling
        window)."""
        assert "bypasses the budget gate" in html.lower() \
            or "subscription bypasses" in html.lower()
        # Either rolling-window language or model_costs reference is
        # acceptable — both convey the per-token meaning.
        assert (
            "rolling-window" in html
            or "model_costs" in html
        )


# ----------------------------------------------------------------------
# JS lifecycle: seed, read, submit
# ----------------------------------------------------------------------


class TestBillingModelLifecycle:
    def test_open_dialog_seeds_radios(self, script):
        """openProviderDialog reads provider.billing_model so editing
        an existing provider lands on the right radio."""
        assert "provider.billing_model" in script

    def test_get_helper_present(self, script):
        """A helper reads the selected radio value so submitProvider
        can include it in the body without duplicating the
        querySelector logic."""
        assert "getSelectedBillingModel" in script

    def test_submit_sends_billing_model(self, script):
        """Submit body includes billing_model so the server endpoint
        receives the operator's choice."""
        # We look for the body assignment in submitProvider — the key
        # billing_model appears alongside backend in the same dict.
        assert "billing_model: getSelectedBillingModel()" in script

    def test_update_note_handler_present(self, script):
        """A change handler flips the subscription note visibility so
        the hint stays accurate when the operator toggles."""
        assert "updateBillingModelNote" in script

    def test_change_listener_bound(self, script):
        """The change listener is wired up at DOMContentLoaded so the
        note responds without a page reload."""
        # Listener attached to all radio inputs in the group.
        assert 'name="prov-billing-model"' in script
        assert "addEventListener('change', updateBillingModelNote)" in script
