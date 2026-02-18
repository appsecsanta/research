from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import psycopg
from psycopg import Connection


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    user: str
    password: str
    dbname: str
    sslmode: Optional[str] = None
    connect_timeout: int = 10
    application_name: str = "backend-service"


def get_postgres_connection(config: PostgresConfig) -> Connection:
    conn = psycopg.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        dbname=config.dbname,
        sslmode=config.sslmode,
        connect_timeout=config.connect_timeout,
        application_name=config.application_name,
    )
    return conn
