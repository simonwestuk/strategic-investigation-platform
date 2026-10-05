"""Authentication and RBAC.

* ``dev`` mode: identity from ``X-User-Id`` / ``X-User-Name`` / ``X-User-Roles`` headers, defaulting to
  a demo user. Refused at startup when ``SIP_ENV=production``.
* ``entra_id`` mode: validates an Entra ID bearer token (signature via the tenant JWKS, issuer, audience,
  expiry) and maps the ``roles`` claim (app roles) onto platform roles.

The authenticated principal is the only source of a review/decision actor. Request bodies cannot set it.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status

from sip.config import AuthMode, Settings
from sip.domain import Actor, ActorKind, Role

OPERATOR_ROLES = [Role.INVESTIGATOR, Role.PRIVACY_REVIEWER, Role.GOVERNANCE_REVIEWER, Role.DECISION_MAKER]


def _parse_roles(raw: str | None) -> list[Role]:
    if raw is None:
        return list(OPERATOR_ROLES)
    roles = []
    for r in raw.split(","):
        r = r.strip()
        try:
            roles.append(Role(r))
        except ValueError:
            continue
    return roles


@lru_cache(maxsize=4)
def _jwks(tenant: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys")


def _entra_actor(token: str, settings: Settings) -> Actor:
    if not settings.entra_tenant_id or not settings.entra_api_audience:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Entra ID is not configured.")
    try:
        key = _jwks(settings.entra_tenant_id).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=settings.entra_api_audience,
            issuer=f"https://login.microsoftonline.com/{settings.entra_tenant_id}/v2.0",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token.") from exc
    roles = []
    for r in claims.get("roles", []):
        try:
            roles.append(Role(r))
        except ValueError:
            continue
    return Actor(
        kind=ActorKind.HUMAN,
        id=f"entra:{claims.get('oid', claims['sub'])}",
        display_name=claims.get("name") or claims.get("preferred_username") or "user",
        roles=roles,
    )


def current_actor(
    request: Request,
    x_user_id: Annotated[str | None, Header()] = None,
    x_user_name: Annotated[str | None, Header()] = None,
    x_user_roles: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> Actor:
    settings: Settings = request.app.state.settings
    if settings.sip_auth_mode == AuthMode.ENTRA_ID:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer token required.")
        return _entra_actor(authorization.split(" ", 1)[1], settings)
    return Actor(
        kind=ActorKind.HUMAN,
        id=f"dev:{(x_user_id or 'operator')[:64]}",
        display_name=(x_user_name or "Operator")[:100],  # single-operator default: holds every approval role
        roles=_parse_roles(x_user_roles),
    )


CurrentActor = Annotated[Actor, Depends(current_actor)]


def require(role: Role):  # type: ignore[no-untyped-def]
    def check(actor: CurrentActor) -> Actor:
        if not actor.has_role(role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role '{role.value}'.")
        return actor

    return check
