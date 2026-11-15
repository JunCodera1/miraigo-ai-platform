from __future__ import annotations

from fastapi import APIRouter, Request

from japanese_ai import __version__
from japanese_ai.core import errors
from japanese_ai.core.envelope import ApiResponse, success
from japanese_ai.core.errors import AppError
from japanese_ai.gateway.deps import ContainerDep, PrincipalDep
from japanese_ai.gateway.schemas import HealthOut, ModelOut

router = APIRouter()


@router.get("/health/live", tags=["system"], summary="Process is up")
async def live(request: Request) -> ApiResponse[dict[str, str]]:
    return success(request, {"status": "ok"})


@router.get("/health/ready", tags=["system"], summary="Ready to serve, per capability")
async def ready(request: Request, container: ContainerDep) -> ApiResponse[HealthOut]:
    capabilities = {"language": True}
    for route in ("asr", "pronunciation"):
        capabilities[route] = any(
            container.pool.get(spec).availability()[0] for spec in container.router.chain(route)
        )
    status = "ok" if all(capabilities.values()) else "degraded"
    data = HealthOut(
        status=status, version=__version__, env=container.settings.env, capabilities=capabilities
    )
    return success(request, data)


@router.get("/api/v1/models", tags=["system"], summary="Registered models and their availability")
async def list_models(
    request: Request, container: ContainerDep, _: PrincipalDep
) -> ApiResponse[list[ModelOut]]:
    routes = {
        "asr": (container.settings.asr_model, container.registry.routing("asr")),
        "pronunciation": (
            container.settings.pronunciation_model,
            container.registry.routing("pronunciation"),
        ),
    }
    out = []
    for spec in container.registry.all():
        available, reason = container.pool.get(spec).availability() if spec.enabled else (False, "disabled")
        roles = {
            route: "primary"
            if spec.id == (override or routing.primary)
            else "fallback"
            if spec.id in routing.fallbacks
            else "none"
            for route, (override, routing) in routes.items()
        }
        out.append(
            ModelOut(
                id=spec.id,
                capability=spec.capability,
                provider=spec.provider,
                deployment=spec.deployment,
                languages=spec.languages,
                license=spec.license,
                source=spec.source,
                description=spec.description,
                enabled=spec.enabled,
                available=available,
                unavailable_reason=reason,
                features=spec.features,
                routing_role=roles["asr"],
                routing_roles=roles,
            )
        )
    return success(request, out)


@router.get("/api/v1/admin/usage", tags=["system"], summary="Per-model usage since start (admin)")
async def usage(
    request: Request, container: ContainerDep, principal: PrincipalDep
) -> ApiResponse[list[dict]]:
    if principal.kind != "service" and principal.role != "ADMIN":
        raise AppError(errors.FORBIDDEN, "Admin access required.", 403)
    return success(request, container.ledger.snapshot())
