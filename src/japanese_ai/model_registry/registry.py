"""Model registry: what models exist, what they can do, and which one each capability uses.

The registry is data (YAML), not code. Adding or replacing a model means editing that file; the
gateway, pipelines and tests stay untouched. Measured quality numbers do not live here — they
belong to dated experiment reports — but each entry links to its source and licence.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Capability = Literal["asr"]
# A route is a task with its own model order. Several routes may use the same capability:
# transcription wants punctuation and accuracy, pronunciation wants a recogniser that corrects little.
Route = Literal["asr", "pronunciation"]
ROUTE_CAPABILITY: dict[str, Capability] = {"asr": "asr", "pronunciation": "asr"}
Deployment = Literal["local", "remote_api", "external_service"]


class CostSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Billing unit of the list price. Local models cost compute, not a per-call fee.
    unit: Literal["audio_minute", "none"] = "none"
    usd: float = 0.0


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    capability: Capability
    # Adapter key, resolved by ``providers.factory``.
    provider: str
    deployment: Deployment
    languages: list[str]
    license: str
    source: str
    description: str = ""
    enabled: bool = True
    features: dict[str, Any] = Field(default_factory=dict)
    cost: CostSpec = Field(default_factory=CostSpec)
    # Adapter-specific settings (file names, thread counts, endpoints).
    config: dict[str, Any] = Field(default_factory=dict)


class RoutingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: str
    fallbacks: list[str] = Field(default_factory=list)
    timeout_seconds: float = 120.0
    # Extra tries on the same provider, for transient failures only.
    max_retries: int = 0


class RegistryFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: list[ModelSpec]
    routing: dict[Route, RoutingSpec]

    @model_validator(mode="after")
    def _check_references(self) -> RegistryFile:
        ids = [model.id for model in self.models]
        duplicates = {model_id for model_id in ids if ids.count(model_id) > 1}
        if duplicates:
            raise ValueError(f"duplicate model ids: {sorted(duplicates)}")
        by_id = {model.id: model for model in self.models}
        for route, routing in self.routing.items():
            capability = ROUTE_CAPABILITY[route]
            for model_id in [routing.primary, *routing.fallbacks]:
                model = by_id.get(model_id)
                if model is None:
                    raise ValueError(f"routing.{route} references unknown model '{model_id}'")
                if model.capability != capability:
                    raise ValueError(f"model '{model_id}' is not a '{capability}' model")
        return self


class ModelRegistry:
    def __init__(self, data: RegistryFile) -> None:
        self._models = {model.id: model for model in data.models}
        self._routing = dict(data.routing)

    @classmethod
    def load(cls, path: Path | None = None) -> ModelRegistry:
        if path is None:
            text = resources.files("japanese_ai.model_registry").joinpath("models.yaml").read_text("utf-8")
        else:
            text = Path(path).read_text("utf-8")
        return cls(RegistryFile.model_validate(yaml.safe_load(text)))

    def get(self, model_id: str) -> ModelSpec | None:
        return self._models.get(model_id)

    def all(self) -> list[ModelSpec]:
        return list(self._models.values())

    def routing(self, route: Route) -> RoutingSpec:
        return self._routing[route]

    def chain(
        self, route: Route, *, preferred: str | None = None, primary_override: str | None = None
    ) -> list[ModelSpec]:
        """Models to try for ``route``, in order: the caller's choice (or the primary), then fallbacks.

        Disabled models are skipped. An explicit ``preferred`` model is never silently replaced:
        the caller asked for it, so it runs alone.
        """
        capability = ROUTE_CAPABILITY[route]
        if preferred is not None:
            model = self._models.get(preferred)
            if model is None or model.capability != capability or not model.enabled:
                return []
            return [model]

        routing = self._routing[route]
        ordered = [primary_override or routing.primary, *routing.fallbacks]
        chain: list[ModelSpec] = []
        for model_id in ordered:
            model = self._models.get(model_id)
            if model is not None and model.enabled and model.capability == capability and model not in chain:
                chain.append(model)
        return chain
