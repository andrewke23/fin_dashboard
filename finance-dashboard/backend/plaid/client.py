"""
backend/plaid/client.py

Builds and caches the Plaid API client.

Design decisions:
- lru_cache(maxsize=1) gives us a process-level singleton without a global variable.
- Environment mapping keeps the production guard explicit — you cannot accidentally
  point at production by typing the wrong string.
- All Plaid imports stay inside this module; the rest of the backend imports from
  backend.plaid.client, so switching SDKs only requires changing this file.
"""

from functools import lru_cache

import plaid
from plaid.api import plaid_api

from backend.config import get_settings

_ENV_MAP = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}


@lru_cache(maxsize=1)
def get_plaid_client() -> plaid_api.PlaidApi:
    """
    Returns a configured, cached Plaid API client.

    Raises ValueError for unknown environment strings so misconfiguration
    fails fast at startup rather than on the first API call.
    """
    settings = get_settings()

    env_key = settings.plaid_env.lower()
    if env_key not in _ENV_MAP:
        raise ValueError(
            f"Unknown PLAID_ENV={settings.plaid_env!r}. "
            f"Must be one of: {list(_ENV_MAP.keys())}"
        )

    configuration = plaid.Configuration(
        host=_ENV_MAP[env_key],
        api_key={
            "clientId": settings.plaid_client_id,
            "secret": settings.plaid_secret,
        },
    )

    api_client = plaid.ApiClient(configuration)
    return plaid_api.PlaidApi(api_client)
