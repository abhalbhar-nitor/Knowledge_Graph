"""Stage 2 - Connect to PostgreSQL safely.

What : open a READ-ONLY connection (ideally to a read replica) with a statement timeout.
Why  : the pipeline must never change business data or slow down live applications.
Out  : ctx.source (a DataSource) + ctx.source_info (server, user, read-only flag).

Two modes:
  * sample   - in-memory copy of sql/01_source_schema.sql (no database needed)
  * postgres - real database; credentials come from env/.env or the UI form and are
               never written to disk or logs.
"""
from __future__ import annotations

import os

from kg.config import settings
from kg.core.context import PipelineContext
from kg.sources.sample_source import SampleSource


def env_defaults() -> dict:
    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", "5432")),
        "dbname": os.environ.get("PGDATABASE", ""),
        "user": os.environ.get("PGUSER", ""),
        "password": os.environ.get("PGPASSWORD", ""),
        "sslmode": os.environ.get("PGSSLMODE", "prefer"),
        "schemas": settings.pg_schemas,
    }


def _replace_source(ctx: PipelineContext, source) -> None:
    if ctx.source is not None:
        try:
            ctx.source.close()
        except Exception:      # noqa: BLE001 - closing an old pool must not block reconnecting
            pass
    ctx.invalidate_from(2)
    ctx.source = source


def connect_sample(ctx: PipelineContext) -> dict:
    src = SampleSource()
    _replace_source(ctx, src)
    ctx.source_info = {"mode": "sample", "name": src.name, **src.ping()}
    ctx.log(2, "Connected to the in-memory sample database (6 retail tables)")
    ctx.mark_done(2)
    return ctx.source_info


def connect_postgres(ctx: PipelineContext, host: str, port: int, dbname: str, user: str, password: str,
                     sslmode: str = "prefer", schemas: list[str] | None = None) -> dict:
    from kg.sources.postgres_source import PostgresSource

    src = PostgresSource(host=host, port=port, dbname=dbname, user=user, password=password,
                         sslmode=sslmode, schemas=schemas or ["public"])
    try:
        info = src.ping()
    except Exception:
        src.close()
        raise
    _replace_source(ctx, src)
    ctx.source_info = {"mode": "postgres", "name": src.name, "schemas": src.schemas, **info}
    if not info["read_only"]:
        ctx.log(2, "Session is not read-only by default; read-only is enforced per session", "warning")
    ctx.log(2, f"Connected to {src.name} as {info['user']} (read-only session, statement timeout on)")
    ctx.mark_done(2)
    return ctx.source_info
