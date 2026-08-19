"""Local settings loaded without exposing secrets in version control."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


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
