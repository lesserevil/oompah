"""Independent provider/model selection for the reserved auditor role.

The auditor role is operator-editable, but its initial candidates must be
safe to use before an operator has made an explicit choice.  This module
owns that migration-time seed and the smaller, reusable policy used when an
audit has contributor provenance available.

The selector deliberately does not perform live network health probes.  A
bootstrap health probe would make startup dependent on every configured
provider.  Callers that have health results can pass them (or a checker) and
the selector also understands the normalized status fields used by the
provider health endpoint.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from oompah.provider_health import ERROR_REASONS, openai_base_url_error
from oompah.roles import Candidate, Role, RoleStore
from oompah.work_contributors import WorkContributor

logger = logging.getLogger(__name__)

AUDITOR_ROLE_NAME = "auditor"

# WorkContributor uses these values when a backend manages the model itself.
# Keep the set local as well as in work_contributors so this module remains
# usable with small test doubles and older records.
UNKNOWN_MODEL_NAMES = frozenset({"", "default", "cli-managed", "cli", "sdk-managed", "unknown", "auto"})

_REASONS = frozenset(
    {
        "empty_role",
        "no_providers",
        "no_whitelisted_providers",
        "all_require_missing_credentials",
        "all_unhealthy",
        "all_over_budget",
        "all_are_contributors",
        "all_attempted",
        "unknown_acp_models_only",
        "invalid_model",
        "invalid_base_url",
        "unknown_error",
    }
)


@dataclass(frozen=True)
class NoCandidateReason:
    """Structured, normalized diagnostic for an empty candidate set."""

    reason: str
    detail: str

    def __post_init__(self) -> None:
        # Do not let an arbitrary provider exception become a new public
        # reason code.  ``unknown_error`` is the stable catch-all.
        if self.reason not in _REASONS:
            object.__setattr__(self, "reason", "unknown_error")

    def to_dict(self) -> dict[str, str]:
        """Serialize to a JSON-friendly diagnostic."""
        return {"reason": self.reason, "detail": self.detail}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "NoCandidateReason":
        """Deserialize a diagnostic, normalizing unknown reason codes."""
        return cls(
            reason=str(value.get("reason") or "unknown_error"),
            detail=str(value.get("detail") or ""),
        )


class AuditorCandidateSelector:
    """Select safe, demonstrably independent candidates for an auditor."""

    def __init__(
        self,
        role_store: RoleStore,
        provider_store: Any,
        project_config: Any | None = None,
        *,
        health_results: Mapping[str, Any] | None = None,
        health_checker: Callable[..., Any] | None = None,
        budget_state: Any | None = None,
        budget_checker: Callable[..., Any] | None = None,
        budget_limit: float | None = None,
        current_spend: float = 0.0,
        # Short aliases are useful for callers constructing the selector from
        # a provider/status response and retain a forgiving integration API.
        health: Mapping[str, Any] | None = None,
        budget: Any | None = None,
    ):
        self.role_store = role_store
        self.provider_store = provider_store
        self.project_config = project_config
        self.health_results = health_results if health_results is not None else health
        self.health_checker = health_checker
        self.budget_state = budget_state if budget_state is not None else budget
        self.budget_checker = budget_checker
        self.budget_limit = budget_limit
        self.current_spend = current_spend

    # ------------------------------------------------------------------
    # Public selection and migration API
    # ------------------------------------------------------------------

    def seed_auditor_role(
        self,
        contributors: list[WorkContributor] | None = None,
    ) -> tuple[Role | None, NoCandidateReason | None]:
        """Build the editable auditor role from configured candidates.

        Candidate order is stable: deep, standard, and default role entries
        first, followed by provider defaults not already present.  The role
        retains every safe candidate, with independent providers before safe
        same-provider fallbacks, so the existing role editor and round-robin
        selector can continue to operate after migration.
        """
        candidates = self._seed_candidates()
        if not candidates:
            return None, NoCandidateReason(
                "no_providers",
                "No candidates from deep/standard/default roles or provider defaults.",
            )

        contributor_pairs = self._contributor_pairs(contributors)
        eligible, reason = self._eligible_candidates(candidates, contributor_pairs)
        if reason is not None:
            return None, reason

        # A role with multiple safe candidates should exercise the existing
        # LRU round-robin path.  A single candidate is equivalent under either
        # strategy, but priority makes its intent explicit in the persisted
        # file and preserves the old one-candidate representation.
        strategy = "round_robin" if len(eligible) > 1 else "priority"
        return (
            Role(
                name=AUDITOR_ROLE_NAME,
                strategy=strategy,
                candidates=eligible,
                updated_at=datetime.now(timezone.utc),
            ),
            None,
        )

    def select_candidate(
        self,
        contributors: list[WorkContributor] | None = None,
    ) -> tuple[Candidate | None, NoCandidateReason | None]:
        """Select the first safe candidate from the current auditor role.

        This is the audit-time companion to :meth:`seed_auditor_role`.  It
        lets a project apply its contributor and policy context without
        rewriting the operator's editable role configuration.
        """
        role = self.role_store.get(AUDITOR_ROLE_NAME)
        if role is None or not role.candidates:
            return None, NoCandidateReason("empty_role", "Auditor role has no candidates.")
        eligible, reason = self._eligible_candidates(
            list(role.candidates), self._contributor_pairs(contributors)
        )
        if reason is not None:
            return None, reason
        return eligible[0], None

    def select_candidates(
        self,
        contributors: list[WorkContributor] | None = None,
        *,
        exclude: set[tuple[str, str]] | None = None,
    ) -> tuple[list[Candidate], NoCandidateReason | None]:
        """Return all currently eligible candidates in selection order.

        The ordinary role dispatcher only needs one candidate, while audit
        retries must exclude candidates already tried by this durable audit.
        Keeping the policy filtering in one place prevents retries from
        accidentally bypassing independence, health, whitelist, or budget
        checks.
        """
        role = self.role_store.get(AUDITOR_ROLE_NAME)
        if role is None or not role.candidates:
            return [], NoCandidateReason("empty_role", "Auditor role has no candidates.")
        eligible, reason = self._eligible_candidates(
            list(role.candidates), self._contributor_pairs(contributors)
        )
        if reason is not None:
            return [], reason
        excluded = exclude or set()
        remaining = [
            candidate
            for candidate in eligible
            if (candidate.provider_id, candidate.model) not in excluded
        ]
        if remaining:
            return remaining, None
        return [], NoCandidateReason(
            "all_attempted" if eligible else "empty_role",
            "All eligible auditor candidates were already attempted for this audit.",
        )

    def _seed_candidates(self) -> list[Candidate]:
        """Return the deduplicated migration union in operator order."""
        deduplicated: dict[tuple[str, str], Candidate] = {}
        for role_name in ("deep", "standard", "default"):
            role = self.role_store.get(role_name)
            for candidate in list(getattr(role, "candidates", None) or []):
                key = (candidate.provider_id, candidate.model)
                deduplicated.setdefault(key, candidate)

        for provider in self.provider_store.list_all():
            default_model = getattr(provider, "default_model", None)
            if default_model:
                key = (provider.id, default_model)
                deduplicated.setdefault(
                    key, Candidate(provider_id=provider.id, model=default_model)
                )
        return list(deduplicated.values())

    # ------------------------------------------------------------------
    # Policy filtering
    # ------------------------------------------------------------------

    def _filter_candidates(
        self,
        candidates: list[Candidate],
        contributor_pairs: set[tuple[str | None, str | None]],
    ) -> Candidate | NoCandidateReason:
        """Return the first candidate that satisfies the complete policy.

        Kept as a small compatibility API for callers that used the initial
        implementation directly.  New code that needs all safe candidates
        uses :meth:`_eligible_candidates`.
        """
        eligible, reason = self._eligible_candidates(candidates, contributor_pairs)
        if reason is not None:
            return reason
        return eligible[0]

    def _eligible_candidates(
        self,
        candidates: list[Candidate],
        contributor_pairs: set[tuple[str | None, str | None]],
    ) -> tuple[list[Candidate], NoCandidateReason | None]:
        """Apply policy filters and return safe candidates in preference order."""
        if not candidates:
            return [], NoCandidateReason("empty_role", "No candidates provided.")

        candidates, reason = self._apply_whitelist(candidates)
        if reason is not None:
            return [], reason

        policy_candidates: list[Candidate] = []
        failures: dict[str, list[str]] = {
            "no_providers": [],
            "invalid_base_url": [],
            "missing_credentials": [],
            "unhealthy": [],
            "invalid_model": [],
            "over_budget": [],
        }
        for candidate in candidates:
            provider = self.provider_store.get(candidate.provider_id)
            label = self._provider_label(provider, candidate.provider_id)
            if provider is None:
                failures["no_providers"].append(label)
                continue

            # ACP sessions do not use the OpenAI-compatible transport.  Every
            # other candidate must have a validated absolute endpoint before
            # it is eligible for an auditor launch.  Keep the diagnostic
            # generic: provider URLs may contain credentials or query secrets.
            if str(getattr(provider, "mode", "api") or "api").casefold() != "acp":
                endpoint_error = openai_base_url_error(
                    getattr(provider, "base_url", "")
                )
                if endpoint_error is not None:
                    failures["invalid_base_url"].append(f"{label}:{endpoint_error}")
                    continue

            if self._requires_credentials(provider) and not getattr(provider, "api_key", ""):
                failures["missing_credentials"].append(label)
                continue

            healthy, health_detail = self._provider_is_healthy(provider, candidate)
            if not healthy:
                failures["unhealthy"].append(f"{label}:{health_detail}")
                continue

            if not self._budget_allows(provider, candidate):
                failures["over_budget"].append(label)
                continue

            if not self._model_is_valid(provider, candidate.model):
                failures["invalid_model"].append(f"{label}:{candidate.model}")
                continue
            policy_candidates.append(candidate)

        if not policy_candidates:
            return [], self._diagnose_policy_failure(failures)

        ordered, contributor_reason = self._exclude_contributors(
            policy_candidates, contributor_pairs
        )
        if contributor_reason is not None:
            return [], contributor_reason
        return ordered, None

    def _apply_whitelist(
        self, candidates: list[Candidate]
    ) -> tuple[list[Candidate], NoCandidateReason | None]:
        whitelist = list(
            getattr(self.project_config, "provider_whitelist", []) or []
        ) if self.project_config is not None else []
        if not whitelist:
            return list(candidates), None

        allowed = {str(value).strip().casefold() for value in whitelist if str(value).strip()}
        filtered: list[Candidate] = []
        for candidate in candidates:
            provider = self.provider_store.get(candidate.provider_id)
            provider_name = getattr(provider, "name", "") if provider else ""
            if (
                candidate.provider_id.casefold() in allowed
                or str(provider_name).strip().casefold() in allowed
            ):
                filtered.append(candidate)
        if not filtered:
            return [], NoCandidateReason(
                "no_whitelisted_providers",
                f"No candidates match whitelist: {whitelist}",
            )
        return filtered, None

    @staticmethod
    def _contributor_pairs(
        contributors: list[WorkContributor] | None,
    ) -> set[tuple[str | None, str | None]]:
        return {
            (
                str(contributor.provider_id).strip()
                if contributor.provider_id is not None
                else None,
                str(contributor.model_id).strip()
                if contributor.model_id is not None
                else None,
            )
            for contributor in (contributors or [])
        }

    def _exclude_contributors(
        self,
        candidates: list[Candidate],
        contributor_pairs: set[tuple[str | None, str | None]],
    ) -> tuple[list[Candidate], NoCandidateReason | None]:
        if not contributor_pairs:
            return list(candidates), None

        # A contributor without a provider identity cannot be compared with
        # any configured candidate.  Treating it as independent would make a
        # false claim of auditor independence, so fail closed instead.
        if any(not provider_id for provider_id, _model_id in contributor_pairs):
            return [], NoCandidateReason(
                "unknown_error",
                "Contributor provenance lacks a provider identity; auditor independence cannot be established.",
            )

        contributed_providers = {
            provider_id for provider_id, _model_id in contributor_pairs if provider_id
        }
        unknown_contributor_providers = {
            provider_id
            for provider_id, model_id in contributor_pairs
            if provider_id and self._is_unknown_model(model_id)
        }
        contributed_models: dict[str, set[str]] = {}
        for provider_id, model_id in contributor_pairs:
            if provider_id and not self._is_unknown_model(model_id):
                contributed_models.setdefault(provider_id, set()).add(str(model_id))

        independent: list[Candidate] = []
        fallback: list[Candidate] = []
        unknown_models: list[Candidate] = []
        for candidate in candidates:
            provider_id = candidate.provider_id
            if provider_id not in contributed_providers:
                independent.append(candidate)
                continue
            if (provider_id, candidate.model) in contributor_pairs:
                continue
            # An SDK-managed contributor has no model identity to compare
            # against.  Treating any later explicit model as "different" would
            # claim independence that the evidence cannot establish.
            if provider_id in unknown_contributor_providers:
                unknown_models.append(candidate)
                continue
            # Same-provider fallback is deliberately explicit and must differ
            # from every known model contributed by that provider.
            if self._is_unknown_model(candidate.model) or candidate.model in contributed_models.get(provider_id, set()):
                unknown_models.append(candidate)
                continue
            fallback.append(candidate)

        # Same-provider candidates are a fallback policy, not additional
        # round-robin choices.  Keeping them alongside independent candidates
        # would eventually dispatch a contributing provider even though an
        # independently provable provider is available.
        if independent:
            return independent, None
        if fallback:
            return fallback, None
        if unknown_models:
            return [], NoCandidateReason(
                "unknown_acp_models_only",
                "Remaining candidates are unknown or unverifiable models on contributing providers.",
            )
        return [], NoCandidateReason(
            "all_are_contributors",
            "All candidates are used by contributors.",
        )

    # ------------------------------------------------------------------
    # Provider status helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _provider_label(provider: Any, provider_id: str) -> str:
        return str(getattr(provider, "name", None) or provider_id)

    @staticmethod
    def _requires_credentials(provider: Any) -> bool:
        return str(getattr(provider, "mode", "api") or "api").casefold() != "acp"

    @staticmethod
    def _is_unknown_model(model: Any) -> bool:
        if model is None:
            return True
        return str(model).strip().casefold() in UNKNOWN_MODEL_NAMES

    @staticmethod
    def _is_subscription_acp(provider: Any) -> bool:
        mode = str(getattr(provider, "mode", "api") or "api").casefold()
        billing = str(getattr(provider, "billing_model", "") or "").casefold()
        return mode == "acp" and (
            billing == "subscription" or bool(getattr(provider, "acp_subscription_only", False))
        )

    def _model_is_valid(self, provider: Any, model: str) -> bool:
        mode = str(getattr(provider, "mode", "api") or "api").casefold()
        catalog = list(getattr(provider, "models", []) or [])
        if mode == "api" and not model:
            return False
        # An empty ACP catalog is an SDK-managed catalog.  Its model sentinel
        # is handled only when it is on a contributing provider; a provider
        # with no contribution is independently identifiable.
        return not catalog or model in catalog

    def _provider_is_healthy(self, provider: Any, candidate: Candidate) -> tuple[bool, str]:
        value: Any = None
        provider_id = getattr(provider, "id", candidate.provider_id)
        if self.health_results is not None:
            if isinstance(self.health_results, Mapping):
                value = self.health_results.get(provider_id)
                if value is None:
                    value = self.health_results.get(candidate.provider_id)
                if value is None:
                    value = self.health_results.get(getattr(provider, "name", ""))
        if value is None and self.health_checker is not None:
            try:
                value = self._call_checker(self.health_checker, provider, candidate)
            except Exception as exc:  # pragma: no cover - defensive integration boundary
                return False, "unknown_error"
        if value is None:
            # A provider health response may be attached by an API caller or
            # test double.  Use vars() to avoid treating MagicMock's arbitrary
            # attributes as real health signals.
            values = vars(provider) if hasattr(provider, "__dict__") else {}
            for key in ("health_result", "health_status", "health", "healthy"):
                if key in values:
                    value = values[key]
                    break
        return self._health_value(value)

    @staticmethod
    def _health_value(value: Any) -> tuple[bool, str]:
        if value is None:
            return True, ""
        if isinstance(value, bool):
            return value, "provider_unavailable" if not value else ""
        if isinstance(value, Mapping):
            if "success" in value:
                success = bool(value.get("success"))
                return success, str(value.get("error_reason") or "provider_unavailable")
            if "healthy" in value:
                healthy = bool(value.get("healthy"))
                return healthy, str(value.get("reason") or "provider_unavailable")
            value = value.get("error_reason", value.get("status"))
        else:
            success = getattr(value, "success", None)
            if isinstance(success, bool):
                return success, str(getattr(value, "error_reason", "provider_unavailable") or "provider_unavailable")
            healthy = getattr(value, "healthy", None)
            if isinstance(healthy, bool):
                return healthy, str(getattr(value, "error_reason", "provider_unavailable") or "provider_unavailable")
            value = getattr(value, "error_reason", value)
        status = str(value or "").strip().casefold()
        if not status or status in {"ok", "healthy", "success", "ready", "available"}:
            return True, ""
        normalized = status if status in ERROR_REASONS else "provider_unavailable"
        return False, normalized

    # ------------------------------------------------------------------
    # Budget helpers
    # ------------------------------------------------------------------

    def _budget_allows(self, provider: Any, candidate: Candidate) -> bool:
        if self._is_subscription_acp(provider):
            return True
        if self._is_explicitly_free(provider, candidate.model):
            return True

        if self.budget_checker is not None:
            try:
                result = self._call_checker(self.budget_checker, provider, candidate)
                allowed, _ = self._budget_value(result)
                return allowed
            except Exception:
                return False

        values = vars(provider) if hasattr(provider, "__dict__") else {}
        for key in ("budget_blocked", "over_budget", "budget_exceeded"):
            if values.get(key) is True:
                return False
        remaining = values.get("budget_remaining")
        if isinstance(remaining, (int, float)) and remaining <= 0:
            return False

        state = self.budget_state
        if state is None:
            state = self.project_config
        allowed, known = self._budget_value(state, provider.id, candidate.model)
        if known:
            return allowed

        limit = self.budget_limit
        spend = self.current_spend
        if limit is None and state is not None:
            limit = self._number_attr(state, "budget_limit")
            spend_value = self._number_attr(state, "estimated_cost", "current_spend", "spent")
            if spend_value is not None:
                spend = spend_value
        if limit is not None and limit > 0 and spend >= limit:
            return False
        return True

    @staticmethod
    def _is_explicitly_free(provider: Any, model: str) -> bool:
        method = getattr(provider, "is_model_explicitly_free", None)
        if callable(method):
            try:
                return bool(method(model))
            except Exception:
                pass
        costs = getattr(provider, "model_costs", None)
        if isinstance(costs, Mapping) and model in costs:
            entry = costs.get(model) or {}
            return (
                entry.get("cost_per_1k_input", -1) == 0
                and entry.get("cost_per_1k_output", -1) == 0
            )
        return False

    @staticmethod
    def _number_attr(value: Any, *names: str) -> float | None:
        if isinstance(value, Mapping):
            for name in names:
                raw = value.get(name)
                if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                    return float(raw)
            return None
        values = vars(value) if hasattr(value, "__dict__") else {}
        for name in names:
            raw = values.get(name)
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                return float(raw)
        return None

    @classmethod
    def _budget_value(
        cls, value: Any, provider_id: str | None = None, model: str | None = None
    ) -> tuple[bool, bool]:
        """Return ``(allowed, known)`` for a budget status value."""
        if value is None:
            return True, False
        if isinstance(value, bool):
            return value, True
        if isinstance(value, Mapping):
            if provider_id is not None and provider_id in value:
                return cls._budget_value(value[provider_id], None, model)
            for key in ("allowed", "can_dispatch"):
                if key in value and isinstance(value[key], bool):
                    return value[key], True
            for key in ("budget_blocked", "over_budget", "budget_exceeded"):
                if value.get(key) is True:
                    return False, True
            limit = cls._number_attr(value, "budget_limit")
            spend = cls._number_attr(value, "estimated_cost", "current_spend", "spent")
            if limit is not None and limit > 0 and spend is not None:
                return spend < limit, True
            remaining = cls._number_attr(value, "budget_remaining", "remaining")
            if remaining is not None:
                return remaining > 0, True
            return True, False
        # Service/orchestrator budget snapshots are commonly dataclasses or
        # SimpleNamespace instances rather than mappings. Inspect only
        # declared attributes so a MagicMock's fabricated attributes cannot
        # accidentally block a candidate.
        values = vars(value) if hasattr(value, "__dict__") else {}
        for key in ("allowed", "can_dispatch"):
            if isinstance(values.get(key), bool):
                return values[key], True
        for key in ("budget_blocked", "over_budget", "budget_exceeded"):
            if values.get(key) is True:
                return False, True
        limit = cls._number_attr(value, "budget_limit")
        spend = cls._number_attr(value, "estimated_cost", "current_spend", "spent")
        if limit is not None and limit > 0 and spend is not None:
            return spend < limit, True
        remaining = cls._number_attr(value, "budget_remaining", "remaining")
        if remaining is not None:
            return remaining > 0, True
        status = str(value).strip().casefold()
        if status in {"ok", "healthy", "allowed", "available", "ready"}:
            return True, True
        if status in {"over_budget", "budget_exceeded", "budget_blocked", "blocked"}:
            return False, True
        return True, False

    @staticmethod
    def _call_checker(checker: Callable[..., Any], provider: Any, candidate: Candidate) -> Any:
        """Call a checker with either ``(provider, model)`` or ``(provider)``."""
        try:
            signature = inspect.signature(checker)
        except (TypeError, ValueError):
            return checker(provider, candidate.model)
        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind
            in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
        ]
        if any(parameter.kind == parameter.VAR_POSITIONAL for parameter in signature.parameters.values()) or len(positional) >= 2:
            return checker(provider, candidate.model)
        if len(positional) == 1:
            return checker(provider)
        return checker()

    @staticmethod
    def _diagnose_policy_failure(failures: Mapping[str, list[str]]) -> NoCandidateReason:
        total = sum(len(values) for values in failures.values())
        if total == 0:
            return NoCandidateReason("unknown_error", "No candidate failure details available.")
        nonempty = [(key, values) for key, values in failures.items() if values]
        if len(nonempty) == 1:
            key, values = nonempty[0]
            reason_map = {
                "no_providers": "no_providers",
                "invalid_base_url": "invalid_base_url",
                "missing_credentials": "all_require_missing_credentials",
                "unhealthy": "all_unhealthy",
                "invalid_model": "invalid_model",
                "over_budget": "all_over_budget",
            }
            return NoCandidateReason(reason_map[key], ", ".join(values))
        return NoCandidateReason(
            "unknown_error",
            "; ".join(f"{key}={values}" for key, values in nonempty),
        )


def seed_auditor_role_from_config(
    role_store: RoleStore,
    provider_store: Any,
    project_config: Any | None = None,
    contributors: list[WorkContributor] | None = None,
    **selector_options: Any,
) -> None:
    """Seed the reserved auditor role through the existing RoleStore path."""
    # Migration must never replace an operator's editable configuration.  The
    # bootstrap caller also guards this condition, but keeping the invariant
    # here protects other callers and makes repeated migrations idempotent.
    existing = role_store.get(AUDITOR_ROLE_NAME)
    if existing is not None:
        logger.debug("Auditor role already configured; leaving it unchanged")
        return

    selector = AuditorCandidateSelector(
        role_store=role_store,
        provider_store=provider_store,
        project_config=project_config,
        **selector_options,
    )
    role, reason = selector.seed_auditor_role(contributors)
    if role is not None:
        try:
            role_store.set_candidates(
                name=role.name,
                strategy=role.strategy,
                candidates=role.candidates,
            )
            logger.info(
                "Seeded auditor role with %d candidate(s)", len(role.candidates)
            )
        except Exception as exc:  # pragma: no cover - persistence boundary
            logger.warning("Failed to seed auditor role: %s", exc)
    else:
        logger.warning(
            "Could not seed auditor role: %s (%s)",
            reason.reason if reason else "unknown_error",
            reason.detail if reason else "",
        )


__all__ = [
    "AUDITOR_ROLE_NAME",
    "AuditorCandidateSelector",
    "NoCandidateReason",
    "UNKNOWN_MODEL_NAMES",
    "seed_auditor_role_from_config",
]
