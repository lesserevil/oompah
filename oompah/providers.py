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

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump([p.to_dict() for p in self._providers.values()], f, indent=2)

    def list_all(self) -> list[ModelProvider]:
        return list(self._providers.values())

    def get(self, provider_id: str) -> ModelProvider | None:
        return self._providers.get(provider_id)

    def create(
        self,
        name: str,
        base_url: str,
        api_key: str = "",
        models: list[str] | None = None,
        default_model: str | None = None,
        provider_type: str = "openai",
    ) -> ModelProvider:
        provider_id = f"prov-{uuid.uuid4().hex[:8]}"
        provider = ModelProvider(
            id=provider_id,
            name=name,
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            models=models or [],
            default_model=default_model,
            provider_type=provider_type,
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
        self._save()
        return provider

    def delete(self, provider_id: str) -> bool:
        if provider_id in self._providers:
            del self._providers[provider_id]
            self._save()
            return True
        return False
