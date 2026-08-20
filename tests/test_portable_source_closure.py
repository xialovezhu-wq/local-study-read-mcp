from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from study_read_mcp.config import RepositoryConfig


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ENV = (
    "STUDY_READ_MATH_ROOT",
    "STUDY_READ_CS408_ROOT",
    "STUDY_READ_ENGLISH_ROOT",
    "STUDY_INTAKE_RUNTIME_ROOT",
)


def _load_build_release():
    path = ROOT / "scripts/build_release.py"
    spec = importlib.util.spec_from_file_location("portable_build_release", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PortableSourceClosureTests(unittest.TestCase):
    def test_production_reads_all_roots_from_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            roots = {
                name: base / name.removeprefix("STUDY_").lower()
                for name in PRODUCTION_ENV
            }
            environment = {name: str(path) for name, path in roots.items()}
            with patch.dict(os.environ, environment, clear=True):
                config = RepositoryConfig.production()

        self.assertEqual(config.math_root, roots["STUDY_READ_MATH_ROOT"])
        self.assertEqual(config.cs408_root, roots["STUDY_READ_CS408_ROOT"])
        self.assertEqual(config.english_root, roots["STUDY_READ_ENGLISH_ROOT"])
        self.assertEqual(
            config.preprocessor_root,
            roots["STUDY_INTAKE_RUNTIME_ROOT"],
        )

    def test_production_fails_closed_when_one_root_is_missing(self) -> None:
        environment = {
            name: f"/synthetic/{name.lower()}"
            for name in PRODUCTION_ENV
            if name != "STUDY_READ_ENGLISH_ROOT"
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(
                RuntimeError,
                "study_read_mcp_production_environment_missing: "
                "STUDY_READ_ENGLISH_ROOT",
            ):
                RepositoryConfig.production()

    def test_release_default_is_checkout_relative_without_environment(self) -> None:
        builder = _load_build_release()
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(builder.default_release_base(), ROOT / "build/releases")

    def test_build_release_uses_synthetic_environment_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release_base = Path(temporary) / "release-output"
            environment = {
                **os.environ,
                "STUDY_READ_MCP_RELEASE_BASE": str(release_base),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/build_release.py")],
                cwd=ROOT,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            result = json.loads(completed.stdout)
            self.assertEqual(Path(result["release_dir"]).parent, release_base)
            self.assertEqual(result["status"], "verified")


if __name__ == "__main__":
    unittest.main()
