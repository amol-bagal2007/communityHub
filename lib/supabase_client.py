from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


def _secret(name: str, default: str = "") -> str:
    """Read from environment first, then Streamlit secrets (Community Cloud)."""
    value = os.getenv(name, "")
    if value:
        return value
    try:
        import streamlit as st

        secrets = st.secrets
        if name in secrets:
            return str(secrets[name])
    except Exception:
        pass
    return default


SUPABASE_URL = _secret("SUPABASE_URL")
SUPABASE_KEY = _secret("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = _secret("SUPABASE_SERVICE_ROLE_KEY")
SCHEMA = _secret("SUPABASE_SCHEMA", "community_hub")
APP_URL = _secret("APP_URL", "http://localhost:8501")


class SchemaClient:
    """Wraps Supabase client to target the community_hub schema by default."""

    def __init__(self, client: Client, schema: str) -> None:
        self._client = client
        self._schema = schema

    def table(self, name: str) -> Any:
        return self._client.schema(self._schema).table(name)

    @property
    def auth(self) -> Any:
        return self._client.auth

    @property
    def raw(self) -> Client:
        return self._client


def get_client() -> SchemaClient:
    url = _secret("SUPABASE_URL")
    key = _secret("SUPABASE_KEY")
    schema = _secret("SUPABASE_SCHEMA", "community_hub")
    if not url or not key:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_KEY in .env (local) or Streamlit Secrets (cloud)."
        )
    return SchemaClient(create_client(url, key), schema)


def get_service_client() -> SchemaClient:
    """
    Service-role client for admin-only server actions (e.g., creating users).

    IMPORTANT: Keep SUPABASE_SERVICE_ROLE_KEY only in local/server env (.env)
    or Streamlit Secrets — never commit it. This bypasses RLS.
    """
    url = _secret("SUPABASE_URL")
    service_key = _secret("SUPABASE_SERVICE_ROLE_KEY")
    schema = _secret("SUPABASE_SCHEMA", "community_hub")
    if not url or not service_key:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env or Streamlit Secrets "
            "to use admin user creation."
        )
    return SchemaClient(create_client(url, service_key), schema)
