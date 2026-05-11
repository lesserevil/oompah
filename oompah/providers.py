"""Model provider storage and management."""

from __future__ import annotations

import json
import logging
import os
import uuid

from oompah.models import ModelProvider

logger = logging.getLogger(__name__)

DEFAULT_PROVIDERS_PATH = ".oompah/providers.json"


class ProviderStore:
    """File-backed store for model provider configurations."""

    def __init__(self, path: str | None = None):
        self.path = path or DEFAULT_PROVIDERS_PATH
        self._providers: dict[str, ModelProvider] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            self._providers = {}
            return
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            self._providers = {}
            for entry in data:
                p = ModelProvider.from_dict(entry)
                if p.id:
                    self._providers[p.id] = p
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load providers from %s: %s", self.path, exc)
            self._providers = {}
        # Defensively reconcile model_roles on every provider at startup so
        # hand-edited providers.json drift gets self-healed before any dispatch.
        self._reconcile_all()

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump([p.to_dict() for p in self._providers.values()], f, indent=2)

    def _reconcile_all(self) -> None:
        """Defensively reconcile model_roles on every provider at startup.

        Hand-edited providers.json files with stale model_roles entries
        get self-healed immediately rather than waiting for an operator
        to notice the drift via "Model X not available" dispatch failures.
        """
        for provider in self._providers.values():
            provider._reconcile_model_roles()

    def list_all(self) -> list[ModelProvider]:
        return list(self._providers.values())

    def get(self, provider_id: str) -> ModelProvider | None:
        return self._providers.get(provider_id)

    def get_default(self) -> ModelProvider | None:
        """Return the sole provider if exactly one exists, else None."""
        if len(self._providers) == 1:
            return next(iter(self._providers.values()))
        return None

    def create(
        self,
        name: str,
        base_url: str = "",
        api_key: str = "",
        models: list[str] | None = None,
        default_model: str | None = None,
        provider_type: str = "openai_compatible",
        backend: str | None = None,
        mode: str = "api",
        acp_permission_mode: str | None = None,
        acp_subscription_only: bool = False,
        billing_model: str = "subscription",
    ) -> ModelProvider:
        # Normalize mode here as a safety net; the API endpoint validates
        # earlier so callers that hit this path with a bad value stay
        # consistent (mirrors ModelProvider.from_dict's behavior).
        m = (mode or "api").lower()
        if m not in ("api", "acp"):
            m = "api"
        # Normalize provider_type: collapse legacy values
        # (openai/anthropic/custom) -> openai_compatible and keep
        # provider_type isomorphic with mode (oompah-zlz_2-zvm0).
        pt = str(provider_type or "openai_compatible").lower().strip()
        if pt in ("openai", "anthropic", "custom", ""):
            pt = "openai_compatible"
        if m == "acp":
            pt = "acp"
        elif pt == "acp":
            # provider_type=acp wins — coerce mode to acp too.
            m = "acp"
        else:
            pt = "openai_compatible"
        provider_type = pt
        # Defensive normalization mirroring ModelProvider.from_dict's
        # safety net: unknown billing_model values fall back to
        # subscription so a typo on the API request can't silently
        # start metering against the budget.
        if not isinstance(billing_model, str) or billing_model.lower() not in (
            "subscription", "per_token",
        ):
            billing_model = "subscription"
        else:
            billing_model = billing_model.lower()
        provider_id = f"prov-{uuid.uuid4().hex[:8]}"
        provider = ModelProvider(
            id=provider_id,
            name=name,
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            models=models or [],
            default_model=default_model,
            provider_type=provider_type,
            backend=backend or None,
            mode=m,
            acp_permission_mode=acp_permission_mode,
            acp_subscription_only=bool(acp_subscription_only),
            billing_model=billing_model,
        )
        self._providers[provider_id] = provider
        self._save()
        return provider

    def update(self, provider_id: str, **fields) -> ModelProvider | None:
        provider = self._providers.get(provider_id)
        if not provider:
            return None
        for key, value in fields.items():
            if hasattr(provider, key) and key != "id":
                setattr(provider, key, value)
        if "base_url" in fields:
            provider.base_url = provider.base_url.rstrip("/")
        # Normalize ``mode`` after assignment so a bad value can't
        # silently slip into the JSON store. Mirrors create() and
        # ModelProvider.from_dict.
        if "mode" in fields:
            m = (provider.mode or "api").lower()
            provider.mode = m if m in ("api", "acp") else "api"
        self._save()
        # Reconcile model_roles whenever the models list changes.
        if "models" in fields:
            provider._reconcile_model_roles()
        return provider

    def delete(self, provider_id: str) -> bool:
        if provider_id in self._providers:
            del self._providers[provider_id]
            self._save()
            return True
        return False
