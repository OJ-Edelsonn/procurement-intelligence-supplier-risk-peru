"""Local settings loaded without exposing secrets in version control."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

SYSTEM_DATABASES = {"master", "model", "msdb", "tempdb"}


@dataclass(frozen=True)
class Settings:
    """Filesystem settings for the project data layers."""

    data_root: Path

    @property
    def raw_root(self) -> Path:
        return self.data_root / "raw"

    @property
    def interim_root(self) -> Path:
        return self.data_root / "interim"

    @property
    def processed_root(self) -> Path:
        return self.data_root / "processed"

    @property
    def metadata_root(self) -> Path:
        return self.data_root / "metadata"


@dataclass(frozen=True)
class SqlServerSettings:
    """SQL Server connection settings using Windows integrated authentication."""

    server: str
    database: str
    driver: str
    trusted_connection: str
    encrypt: str
    trust_server_certificate: str

    def connection_string(self, database: str | None = None) -> str:
        selected_database = database or self.database
        return ";".join(
            [
                f"DRIVER={{{self.driver}}}",
                f"SERVER={self.server}",
                f"DATABASE={selected_database}",
                f"Trusted_Connection={self.trusted_connection}",
                f"Encrypt={self.encrypt}",
                f"TrustServerCertificate={self.trust_server_certificate}",
            ]
        )


def load_settings(env_file: str | Path = ".env") -> Settings:
    """Load DATA_ROOT from the process environment or a local .env file."""

    file_values = dotenv_values(env_file)
    configured_root = os.getenv("DATA_ROOT") or file_values.get("DATA_ROOT")
    if not configured_root:
        raise ValueError("DATA_ROOT must be defined in the environment or .env file.")

    data_root = Path(configured_root).expanduser()
    if not data_root.is_absolute():
        raise ValueError("DATA_ROOT must be an absolute path.")

    return Settings(data_root=data_root)


def load_sql_server_settings(
    env_file: str | Path = ".env",
) -> SqlServerSettings:
    """Load a credential-free SQL Server configuration from environment values."""

    file_values = dotenv_values(env_file)

    def required(name: str) -> str:
        value = os.getenv(name) or file_values.get(name)
        if not value:
            raise ValueError(f"{name} must be defined in the environment or .env file.")
        return str(value).strip()

    database = required("SQL_DATABASE")
    if database.casefold() in SYSTEM_DATABASES:
        raise ValueError(f"SQL_DATABASE cannot target a system database: {database}")
    if not database.replace("_", "").isalnum() or not database[0].isalpha():
        raise ValueError(
            "SQL_DATABASE must start with a letter and contain only letters, digits or underscores."
        )

    trusted_connection = required("SQL_TRUSTED_CONNECTION")
    if trusted_connection.casefold() not in {"yes", "true"}:
        raise ValueError(
            "Phase 7 supports Windows integrated authentication only; "
            "SQL_TRUSTED_CONNECTION must be yes."
        )

    return SqlServerSettings(
        server=required("SQL_SERVER"),
        database=database,
        driver=required("SQL_DRIVER"),
        trusted_connection=trusted_connection,
        encrypt=required("SQL_ENCRYPT"),
        trust_server_certificate=required("SQL_TRUST_SERVER_CERTIFICATE"),
    )
