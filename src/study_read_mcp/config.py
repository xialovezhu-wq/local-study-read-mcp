"""Portable repository configuration for the read-only MCP service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_PRODUCTION_ENV = (
    ("math_root", "STUDY_READ_MATH_ROOT"),
    ("cs408_root", "STUDY_READ_CS408_ROOT"),
    ("english_root", "STUDY_READ_ENGLISH_ROOT"),
    ("preprocessor_root", "STUDY_INTAKE_RUNTIME_ROOT"),
)


@dataclass(frozen=True, slots=True)
class RepositoryConfig:
    math_root: Path
    cs408_root: Path
    english_root: Path
    preprocessor_root: Path

    @classmethod
    def production(cls) -> "RepositoryConfig":
        """Load all production roots from explicit environment bindings.

        Production startup must not infer a repository from the current user,
        home directory, checkout location, or any other implicit default.
        """

        values: dict[str, Path] = {}
        missing: list[str] = []
        for field_name, environment_name in _PRODUCTION_ENV:
            raw = os.environ.get(environment_name)
            if raw is None or not raw.strip():
                missing.append(environment_name)
            else:
                values[field_name] = Path(raw)
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(
                f"study_read_mcp_production_environment_missing: {joined}"
            )
        return cls(**values)
