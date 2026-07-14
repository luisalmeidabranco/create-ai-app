from __future__ import annotations

from pathlib import Path

from create_ai_app.models import ProjectConfig


def install(cfg: ProjectConfig, target: Path) -> None:
    pkg = target / "src" / cfg.pkg_name
    if cfg.auth == "API key header":
        # Already handled inline in router.py by api.py
        pass
    elif cfg.auth == "Azure Entra ID":
        _write_entra_auth(cfg, pkg)


def _write_entra_auth(cfg: ProjectConfig, pkg: Path) -> None:
    content = f"""from __future__ import annotations

import os
import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer

logger = logging.getLogger(__name__)

_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"https://login.microsoftonline.com/{{_TENANT_ID}}/oauth2/v2.0/authorize",
    tokenUrl=f"https://login.microsoftonline.com/{{_TENANT_ID}}/oauth2/v2.0/token",
    auto_error=True,
)


async def verify_token(token: Annotated[str, Depends(oauth2_scheme)]) -> dict:
    \"\"\"Validate Azure Entra ID JWT. Replace with azure-identity / msal for production.\"\"\"
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    # TODO: validate the JWT signature against Azure JWKS endpoint
    # See: https://learn.microsoft.com/en-us/entra/identity-platform/access-tokens
    return {{"sub": "user", "token": token}}
"""
    (pkg / "auth.py").write_text(content)
