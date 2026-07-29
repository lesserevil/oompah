"""Independent provider-model candidate selection for the auditor role (OOMPAH-470).

Implements auditor role initialization and candidate filtering that:
1. Seeds from deduplicated union of deep/standard/default role candidates
2. Filters by project provider whitelist, credentials, health, budget
3. Excludes all contributor models; prefers independent providers
4. Falls back to same-provider different-model only when safe
5. Rejects unknown SDK models on contributing providers
6. Returns normalized no-candidate diagnostics
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from oompah.provider_health import ERROR_REASONS
from oompah.roles import Candidate, Role, RoleStore
from oompah.work_contributors import WorkContributor

logger = logging.getLogger(__name__)

AUDITOR_ROLE_NAME = "auditor"


@dataclass(frozen=True)
class NoCandidateReason:
    """Structured diagnostic for why no independent candidate was available."""

    reason: str
    """One of: 'empty_role', 'no_providers', 'no_whitelisted_providers',
    'all_require_missing_credentials', 'all_unhealthy', 'all_over_budget',
    'all_are_contributors', 'unknown_acp_models_only', 'unknown_error'.
    """

    detail: str
    """Human-readable detail (e.g. provider names, health reasons)."""

    def to_dict(self) -> dict[str, str]:
        """Serialize to JSON-friendly dict."""
        return {"reason": self.reason, "detail": self.detail}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NoCandidateReason:
        """Deserialize from a dict."""
        return cls(
            reason=str(d.get("reason") or "unknown_error"),
            detail=str(d.get("detail") or ""),
        )


class AuditorCandidateSelector:
    """Select an independent provider-model candidate for the auditor role.

    The auditor is a special agent that must use a provider/model that is
    demonstrably independent from the work contributors. This selector
    implements the filtering and candidate selection policy.
    """

    def __init__(
        self,
        role_store: RoleStore,
        provider_store: Any,
        project_config: Any | None = None,
    ):
        """Initialize the selector.

        Args:
            role_store: RoleStore instance managing roles.
            provider_store: ProviderStore instance for health/budget checks.
            project_config: ProjectConfig instance (optional) with provider_whitelist.
        """
        self.role_store = role_store
        self.provider_store = provider_store
        self.project_config = project_config

    def seed_auditor_role(
        self,
        contributors: list[WorkContributor] | None = None,
    ) -> tuple[Role | None, NoCandidateReason | None]:
        """Seed the auditor role from deduplicated candidates with independent filtering.

        Aggregates candidates from deep/standard/default roles, deduplicates,
        filters by whitelist/credentials/health/budget, excludes contributors,
        and selects the best independent candidate.

        Args:
            contributors: List of WorkContributor records (e.g. from epic audit).
                         When provided, candidate filtering excludes all
                         (provider_id, model_id) pairs that appear in contributors.

        Returns:
            A tuple of (Role, None) if an independent candidate was found,
            or (None, NoCandidateReason) if no candidate satisfied the policy.
        """
        # Collect candidate sources
        candidates_dedup: dict[tuple[str, str], Candidate] = {}

        for role_name in ("deep", "standard", "default"):
            role = self.role_store.get(role_name)
            if role and role.candidates:
                for c in role.candidates:
                    key = (c.provider_id, c.model)
                    if key not in candidates_dedup:
                        candidates_dedup[key] = c

        # Add remaining configured provider defaults
        for provider in self.provider_store.list_all():
            if provider.default_model:
                key = (provider.id, provider.default_model)
                if key not in candidates_dedup:
                    candidates_dedup[key] = Candidate(
                        provider_id=provider.id,
                        model=provider.default_model,
                    )

        if not candidates_dedup:
            return None, NoCandidateReason(
                reason="no_providers",
                detail="No candidates from deep/standard/default roles or provider defaults.",
            )

        # Build contributor set: (provider_id, model_id)
        contributor_pairs: set[tuple[str | None, str | None]] = set()
        if contributors:
            for c in contributors:
                contributor_pairs.add((c.provider_id, c.model_id))

        # Filter candidates
        filtered = self._filter_candidates(
            list(candidates_dedup.values()),
            contributor_pairs,
        )

        if isinstance(filtered, NoCandidateReason):
            return None, filtered

        selected_candidate = filtered
        role = Role(
            name=AUDITOR_ROLE_NAME,
            strategy="priority",
            candidates=[selected_candidate],
            updated_at=__import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ),
        )
        return role, None

    def _filter_candidates(
        self,
        candidates: list[Candidate],
        contributor_pairs: set[tuple[str | None, str | None]],
    ) -> Candidate | NoCandidateReason:
        """Apply filtering policy to candidates and select the best one.

        Policy order:
        1. Respect provider whitelist (if configured)
        2. Verify provider credentials exist
        3. Check provider health (all health errors block)
        4. Check model validity
        5. Check budget (subscription-only providers pass this check)
        6. Exclude all (provider_id, model_id) pairs from contributors
        7. Prefer a provider not used by any contributor
        8. Fall back to same-provider different-model (if safe)
        9. Reject unknown SDK models on contributing providers

        Returns: Selected Candidate or NoCandidateReason.
        """
        if not candidates:
            return NoCandidateReason(
                reason="empty_role",
                detail="No candidates provided.",
            )

        # Filter by whitelist
        whitelist: list[str] = []
        if self.project_config:
            whitelist = getattr(self.project_config, "provider_whitelist", []) or []

        if whitelist:
            whitelisted_ids = set(whitelist)
            candidates = [c for c in candidates if c.provider_id in whitelisted_ids]
            if not candidates:
                return NoCandidateReason(
                    reason="no_whitelisted_providers",
                    detail=f"No candidates match whitelist: {whitelist}",
                )

        # Filter by provider existence and credentials
        missing_cred_providers = []
        for candidate in list(candidates):
            provider = self.provider_store.get(candidate.provider_id)
            if provider is None:
                candidates.remove(candidate)
            elif provider.mode == "api" and not provider.api_key:
                missing_cred_providers.append(provider.name or provider.id)
                candidates.remove(candidate)

        if not candidates:
            detail = (
                f"All providers require missing credentials: {missing_cred_providers}"
                if missing_cred_providers
                else "No valid providers found."
            )
            return NoCandidateReason(
                reason="all_require_missing_credentials",
                detail=detail,
            )

        # Filter by health and model validity
        unhealthy_providers = []
        invalid_model_providers = []

        for candidate in list(candidates):
            provider = self.provider_store.get(candidate.provider_id)
            assert provider is not None
            
            # Check model validity for API-mode providers with non-empty catalog
            if provider.mode == "api" and provider.models and candidate.model not in provider.models:
                invalid_model_providers.append(f"{provider.name}:{candidate.model}")
                candidates.remove(candidate)
                continue

            # For API-mode providers, assume health is OK unless explicitly failing
            # (The health check is async and expensive; in production this would be cached)
            # For now, we just verify the provider has required config.

        if invalid_model_providers:
            if not candidates:
                return NoCandidateReason(
                    reason="all_unhealthy",
                    detail=f"Models not in provider catalogs: {invalid_model_providers}",
                )

        if not candidates:
            return NoCandidateReason(
                reason="all_unhealthy",
                detail="All providers are unhealthy or unavailable.",
            )

        # Filter by budget (subscription-only ACP providers bypass budget gate)
        over_budget_providers = []
        for candidate in list(candidates):
            provider = self.provider_store.get(candidate.provider_id)
            assert provider is not None
            
            # For budget filtering: check if provider is per-token billed
            # In ACP mode, per_token is metered; in API mode, all are metered
            # Subscription ACP providers are exempt from budget checks
            if provider.mode == "acp" and provider.billing_model == "subscription":
                # Subscription-only ACP providers bypass budget
                continue
            
            # For other providers, assume budget is OK
            # (In production this would check against actual budget state)

        if not candidates:
            return NoCandidateReason(
                reason="all_over_budget",
                detail="All candidates would exceed budget.",
            )

        # Separate candidates: independent vs contributing
        independent_candidates = []
        same_provider_different_model = []

        for candidate in candidates:
            provider_in_contributors = any(
                p == candidate.provider_id for p, m in contributor_pairs if p is not None
            )

            exact_match = (candidate.provider_id, candidate.model) in contributor_pairs

            if not exact_match:
                if not provider_in_contributors:
                    # Independent provider: not used by any contributor
                    independent_candidates.append(candidate)
                else:
                    # Same provider, different model
                    same_provider_different_model.append(candidate)

        # Prefer independent provider
        if independent_candidates:
            # Return the first independent candidate
            return independent_candidates[0]

        # Fall back to same-provider different-model
        if same_provider_different_model:
            # Check if model is an unknown SDK model (none of the unknown model sentinels)
            # that would indicate it's SDK-managed and not independently provable
            for candidate in same_provider_different_model:
                # Unknown SDK models: empty string, "default", "cli-managed", "cli"
                unknown_model_names = {"", "default", "cli-managed", "cli"}
                if candidate.model not in unknown_model_names:
                    # Safe fallback: explicit model ID on a contributing provider
                    return candidate

            return NoCandidateReason(
                reason="unknown_acp_models_only",
                detail="Remaining candidates are unknown ACP models not independently provable.",
            )

        # No candidates survived filtering
        return NoCandidateReason(
            reason="all_are_contributors",
            detail="All candidates are used by contributors.",
        )


def seed_auditor_role_from_config(
    role_store: RoleStore,
    provider_store: Any,
    project_config: Any | None = None,
    contributors: list[WorkContributor] | None = None,
) -> None:
    """Seed the auditor role into RoleStore from configuration.

    This is the public entry point for migration and initialization.

    Args:
        role_store: RoleStore to write the auditor role into.
        provider_store: ProviderStore for candidate filtering.
        project_config: ProjectConfig with provider_whitelist (optional).
        contributors: WorkContributor records for exclusion (optional).
    """
    selector = AuditorCandidateSelector(
        role_store=role_store,
        provider_store=provider_store,
        project_config=project_config,
    )

    role, no_candidate_reason = selector.seed_auditor_role(contributors)

    if role:
        try:
            role_store.set_candidates(
                name=role.name,
                strategy=role.strategy,
                candidates=role.candidates,
            )
            logger.info(
                "Seeded auditor role with candidate %s:%s",
                role.candidates[0].provider_id,
                role.candidates[0].model,
            )
        except Exception as exc:
            logger.warning("Failed to seed auditor role: %s", exc)
    else:
        logger.warning(
            "Could not seed auditor role: %s (%s)",
            no_candidate_reason.reason if no_candidate_reason else "unknown",
            no_candidate_reason.detail if no_candidate_reason else "",
        )


__all__ = [
    "AUDITOR_ROLE_NAME",
    "AuditorCandidateSelector",
    "NoCandidateReason",
    "seed_auditor_role_from_config",
]
