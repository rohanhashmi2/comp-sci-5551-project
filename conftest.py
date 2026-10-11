"""Root pytest configuration.

Swaps DATABASE_URL to TEST_DATABASE_URL *before* Django imports its
settings, so the app talks to Supabase at runtime but tests hit a local
Postgres. Keep this file free of Django imports — it must run before
Django is bootstrapped.
"""

import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent

environ.Env.read_env(BASE_DIR / ".env")

if "TEST_DATABASE_URL" not in os.environ:
    raise RuntimeError(
        "TEST_DATABASE_URL is not set. Tests require a local Postgres URL "
        "distinct from DATABASE_URL. See README section 'Local Postgres for "
        "tests' and .env.example."
    )

os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
