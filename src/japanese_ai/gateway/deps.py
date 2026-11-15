"""Request dependencies: container access, authentication, rate limits."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request

from japanese_ai.core.logging import principal_var
from japanese_ai.gateway.container import Container
from japanese_ai.infrastructure.auth import Principal


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


async def current_principal(
    request: Request,
    container: ContainerDep,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> Principal:
    principal = await container.authenticator.authenticate(authorization, x_api_key)
    principal_var.set(principal.label)
    request.state.principal = principal
    container.limiter.check(f"all:{principal.label}", container.settings.rate_limit_per_minute)
    return principal


PrincipalDep = Annotated[Principal, Depends(current_principal)]


def inference_quota(principal: PrincipalDep, container: ContainerDep) -> Principal:
    """Stricter limit for endpoints that run a speech model."""
    container.limiter.check(
        f"inference:{principal.label}", container.settings.inference_rate_limit_per_minute
    )
    return principal


InferencePrincipalDep = Annotated[Principal, Depends(inference_quota)]
