import os
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SCHEMA = os.getenv("SUPABASE_SCHEMA", "community_hub")


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
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_KEY in .env (copy from .env.example)."
        )
    return SchemaClient(create_client(SUPABASE_URL, SUPABASE_KEY), SCHEMA)
