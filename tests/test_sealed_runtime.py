from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from study_read_mcp.morning import canonical_scope_hash

from .helpers import make_fixture


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)


def _editable_site_packages() -> Path:
    return Path(sysconfig.get_path("purelib"))


def _production_environment(config) -> dict[str, str]:
    return {
        "STUDY_READ_MATH_ROOT": str(config.math_root),
        "STUDY_READ_CS408_ROOT": str(config.cs408_root),
        "STUDY_READ_ENGLISH_ROOT": str(config.english_root),
        "STUDY_INTAKE_RUNTIME_ROOT": str(config.preprocessor_root),
    }


def _builder():
    spec = importlib.util.spec_from_file_location(
        "sealed_runtime_build_release", ROOT / "scripts/build_release.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _request(subject: str) -> bytes:
    value = {
        "tool": "authority_bundle",
        "arguments": {
            "subjects": [subject],
            "capabilities": ["authority", "preprocessor_release"],
            "checks": ["exists", "parseable", "release_bound"],
            "route": {
                "caller_skill_id": f"background-{subject}-processing",
                "caller_skill_version": "3.0.0",
                "plugin_version": "0.4.0-canary.9",
                "route_request_id": f"sealed-runtime-{subject}",
                "evidence_scope_hash": "a" * 64,
                "read_route": "mcp",
                "chunk_index": 1,
                "chunk_count": 1,
                "consumed_duplicate_read_count": 0,
            },
        },
    }
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def _morning_request(request: dict[str, object], evidence_scope_hash: str) -> bytes:
    value = {
        "tool": "cs408_morning_preparation_bundle",
        "arguments": {
            "request": request,
            "route": {
                "caller_skill_id": "kaoyan-408-morning-control",
                "caller_skill_version": "3.0.0",
                "plugin_version": "0.4.0-canary.9",
                "route_request_id": "sealed-runtime-morning-cs408",
                "evidence_scope_hash": evidence_scope_hash,
                "read_route": "mcp",
                "chunk_index": 1,
                "chunk_count": 1,
                "consumed_duplicate_read_count": 0,
            },
        },
    }
    return (json.dumps(value, separators=(",", ":")) + "\n").encode()


def _prepare_morning_fixture(config) -> tuple[dict[str, object], str]:
    root = config.cs408_root
    dashboard = root / "wiki/study_vaults/408-full/StudyVault/00-Dashboard"
    dashboard.mkdir(parents=True, exist_ok=True)
    (root / "wiki/study_vaults/408-full/input").mkdir(parents=True, exist_ok=True)
    (root / "复习单元卡").mkdir(parents=True, exist_ok=True)
    (root / "复习单元节点映射.md").write_text(
        "# 复习单元节点映射\n", encoding="utf-8"
    )
    (root / "DS_2023_002.md").write_text(
        "# DS_2023_002\n\nSynthetic protected evidence.\n",
        encoding="utf-8",
    )
    queue = (
        "review_date: 2026-08-07\n\n"
        "### MQ-MORNING-001\n"
        "- source_id: SRC-1\n"
        "- item_kind: formal\n"
    ).encode("utf-8")
    queue_path = dashboard / "2026-08-07-408晨间行动队列.md"
    queue_path.write_bytes(queue)
    queue_sha256 = hashlib.sha256(queue).hexdigest()
    item_ids = ["MQ-MORNING-001"]
    scope_hash = canonical_scope_hash("2026-08-07", queue_sha256, item_ids)
    request = {
        "review_date": "2026-08-07",
        "queue_sha256": queue_sha256,
        "item_ids": item_ids,
    }
    return request, scope_hash


class SealedRuntimeTests(unittest.TestCase):
    def test_isolated_no_site_starts_before_the_real_editable_pth(self) -> None:
        editable_source = str(ROOT / "src")
        pth_files = sorted(
            _editable_site_packages().glob("__editable__.study_read_mcp-*.pth")
        )
        self.assertTrue(pth_files, "fixture requires the real editable install")
        self.assertIn(editable_source, pth_files[0].read_text(encoding="utf-8"))
        completed = subprocess.run(
            [
                str(PYTHON),
                "-I",
                "-S",
                "-c",
                "import json,sys; print(json.dumps(sys.path))",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn(editable_source, json.loads(completed.stdout))

    def test_all_production_profiles_ignore_editable_install(self) -> None:
        builder = _builder()
        with tempfile.TemporaryDirectory() as temp:
            result = builder.build(Path(temp) / "releases")
            release = Path(result["release_dir"])
            fixture_config = make_fixture(Path(temp) / "authority")
            morning_request, morning_scope_hash = _prepare_morning_fixture(
                fixture_config
            )
            editable_site = Path(temp) / "editable-site"
            editable_package = editable_site / "study_read_mcp"
            editable_package.mkdir(parents=True)
            (editable_package / "__init__.py").write_text(
                "raise RuntimeError('editable import must never run')\n",
                encoding="utf-8",
            )
            (editable_site / "study-read-mcp-editable.pth").write_text(
                str(editable_site) + "\n", encoding="utf-8"
            )
            cases = (
                ("ordinary", "math"),
                ("background", "math"),
                ("background", "cs408"),
                ("background", "english"),
                ("morning_preparation", "cs408"),
            )
            for profile, subject in cases:
                with self.subTest(profile=profile, subject=subject):
                    completed = subprocess.run(
                        [
                            str(PYTHON),
                            "-I",
                            "-S",
                            str(release / "scripts/sealed_launcher.py"),
                            "--release-root",
                            str(release),
                            "--expected-release-id",
                            result["release_id"],
                            "--expected-release-manifest-sha256",
                            result["release_manifest_sha256"],
                            "--mode",
                            "client",
                            "--profile",
                            profile,
                            "--subject",
                            subject,
                        ],
                        input=(
                            _morning_request(morning_request, morning_scope_hash)
                            if profile == "morning_preparation"
                            else _request(subject)
                        ),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=editable_site,
                        env={
                            "PATH": "/usr/bin:/bin",
                            "PYTHONUTF8": "1",
                            "PYTHONDONTWRITEBYTECODE": "1",
                            "PYTHONNOUSERSITE": "1",
                            "PYTHONSAFEPATH": "1",
                            "PYTHONUSERBASE": str(editable_site),
                            "PYTHONPATH": str(release / "src"),
                            "STUDY_READ_MCP_EXPECTED_PROJECT_ROOT": str(release),
                            "STUDY_READ_MCP_EXPECTED_RELEASE_ID": result[
                                "release_id"
                            ],
                            "STUDY_READ_MCP_EXPECTED_RELEASE_MANIFEST_SHA256": result[
                                "release_manifest_sha256"
                            ],
                            **_production_environment(fixture_config),
                        },
                        check=False,
                        timeout=20,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    payload = json.loads(completed.stdout)
                    self.assertEqual(payload["server_release"], result["server_release"])
                    if profile != "morning_preparation":
                        self.assertTrue(payload["ok"])

    def test_runtime_binding_rejects_wrong_root_release_and_missing_binding(self) -> None:
        builder = _builder()
        with tempfile.TemporaryDirectory() as temp:
            result = builder.build(Path(temp) / "releases")
            release = Path(result["release_dir"])
            base_environment = {
                "PATH": "/usr/bin:/bin",
                "PYTHONUTF8": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(release / "src"),
            }
            code = (
                "from study_read_mcp.runtime_binding import "
                "verify_runtime_binding; verify_runtime_binding("
                "require_expected_environment=True)"
            )
            missing = subprocess.run(
                [str(PYTHON), "-c", code],
                cwd=release,
                env=base_environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(missing.returncode, 0)
            wrong = subprocess.run(
                [str(PYTHON), "-c", code],
                cwd=release,
                env={
                    **base_environment,
                    "STUDY_READ_MCP_EXPECTED_PROJECT_ROOT": str(release),
                    "STUDY_READ_MCP_EXPECTED_RELEASE_ID": "0" * 64,
                    "STUDY_READ_MCP_EXPECTED_RELEASE_MANIFEST_SHA256": result[
                        "release_manifest_sha256"
                    ],
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(wrong.returncode, 0)

            missing_pythonpath = subprocess.run(
                [
                    str(PYTHON),
                    "-m",
                    "study_read_mcp.client",
                    "--profile",
                    "background",
                    "--subject",
                    "math",
                    "--project-root",
                    str(release),
                ],
                input=_request("math"),
                cwd=release,
                env={
                    "PATH": "/usr/bin:/bin",
                    "PYTHONUTF8": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONNOUSERSITE": "1",
                    "STUDY_READ_MCP_EXPECTED_PROJECT_ROOT": str(release),
                    "STUDY_READ_MCP_EXPECTED_RELEASE_ID": result["release_id"],
                    "STUDY_READ_MCP_EXPECTED_RELEASE_MANIFEST_SHA256": result[
                        "release_manifest_sha256"
                    ],
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(missing_pythonpath.returncode, 0)

            tampered_parent = Path(temp) / "tampered"
            tampered_root = tampered_parent / release.name
            shutil.copytree(release, tampered_root)
            manifest_path = tampered_root / "release.json"
            manifest_path.chmod(0o600)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["formal_write_count"] = 1
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            tampered = subprocess.run(
                [str(PYTHON), "-c", code],
                cwd=tampered_root,
                env={
                    "PATH": "/usr/bin:/bin",
                    "PYTHONUTF8": "1",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONPATH": str(tampered_root / "src"),
                    "STUDY_READ_MCP_EXPECTED_PROJECT_ROOT": str(tampered_root),
                    "STUDY_READ_MCP_EXPECTED_RELEASE_ID": release.name,
                    "STUDY_READ_MCP_EXPECTED_RELEASE_MANIFEST_SHA256": result[
                        "release_manifest_sha256"
                    ],
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(tampered.returncode, 0)

    def test_sealed_launcher_rejects_wrong_manifest_sha_and_copied_launcher(self) -> None:
        builder = _builder()
        with tempfile.TemporaryDirectory() as temp:
            result = builder.build(Path(temp) / "releases")
            release = Path(result["release_dir"])
            common = [
                str(PYTHON),
                "-I",
                "-S",
                str(release / "scripts/sealed_launcher.py"),
                "--release-root",
                str(release),
                "--expected-release-id",
                result["release_id"],
                "--expected-release-manifest-sha256",
            ]
            wrong_manifest = subprocess.run(
                [
                    *common,
                    "0" * 64,
                    "--mode",
                    "server",
                    "--profile",
                    "ordinary",
                    "--subjects",
                    "math,cs408,english",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(wrong_manifest.returncode, 0)
            self.assertIn(b"mcp_sealed_release_manifest_invalid", wrong_manifest.stderr)

            copied = Path(temp) / "copied-launcher.py"
            shutil.copy2(release / "scripts/sealed_launcher.py", copied)
            copied.chmod(0o444)
            copied_launcher = subprocess.run(
                [
                    str(PYTHON),
                    "-I",
                    "-S",
                    str(copied),
                    "--release-root",
                    str(release),
                    "--expected-release-id",
                    result["release_id"],
                    "--expected-release-manifest-sha256",
                    result["release_manifest_sha256"],
                    "--mode",
                    "server",
                    "--profile",
                    "ordinary",
                    "--subjects",
                    "math,cs408,english",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(copied_launcher.returncode, 0)
            self.assertIn(b"mcp_sealed_launcher_origin_mismatch", copied_launcher.stderr)

    def test_three_subject_servers_use_sealed_release_and_distinct_stdio_sessions(self) -> None:
        from tests.test_focused_mcp import make_v2_session

        builder = _builder()
        with tempfile.TemporaryDirectory() as temp:
            result = builder.build(Path(temp) / "releases")
            release = Path(result["release_dir"])
            editable = Path(temp) / "wrong-cwd"
            (editable / "study_read_mcp").mkdir(parents=True)
            (editable / "study_read_mcp/__init__.py").write_text(
                "raise RuntimeError('wrong cwd import')\n", encoding="utf-8"
            )

            async def inspect(subject: str, session_root: Path) -> tuple[str, list[str]]:
                config, session = make_v2_session(session_root, subject)
                params = StdioServerParameters(
                    command=str(PYTHON),
                    args=[
                        "-I",
                        "-S",
                        str(release / "scripts/sealed_launcher.py"),
                        "--release-root",
                        str(release),
                        "--expected-release-id",
                        result["release_id"],
                        "--expected-release-manifest-sha256",
                        result["release_manifest_sha256"],
                        "--mode",
                        "subject-server",
                        "--subject",
                        subject,
                        "--read-session-manifest",
                        str(session),
                        "--preprocessor-root",
                        str(config.preprocessor_root),
                    ],
                    cwd=str(editable),
                    env={
                        "PATH": "/usr/bin:/bin",
                        "PYTHONPATH": str(editable),
                        "PYTHONUSERBASE": str(editable),
                        **_production_environment(config),
                    },
                )
                async with stdio_client(params) as streams:
                    async with ClientSession(*streams) as client:
                        initialized = await client.initialize()
                        tools = await client.list_tools()
                return initialized.serverInfo.name, [item.name for item in tools.tools]

            identities: list[str] = []
            for subject in ("math", "cs408", "english"):
                name, tools = asyncio.run(inspect(subject, Path(temp) / f"fixture-{subject}"))
                identities.append(name)
                self.assertEqual(
                    tools,
                    [
                        "get_task_context",
                        "read_task_artifact",
                        "list_records",
                        "get_records",
                        "search_records",
                        "query_relations",
                    ],
                )
            self.assertEqual(
                identities,
                ["kaoyan_math_read", "kaoyan_cs408_read", "kaoyan_english_read"],
            )

    def test_immutable_release_modules_cannot_bypass_expected_binding(self) -> None:
        builder = _builder()
        with tempfile.TemporaryDirectory() as temp:
            result = builder.build(Path(temp) / "releases")
            release = Path(result["release_dir"])
            completed = subprocess.run(
                [
                    str(PYTHON),
                    "-I",
                    "-c",
                    (
                        "import sys; sys.path.insert(0, %r); "
                        "from study_read_mcp.runtime_binding import verify_runtime_binding; "
                        "verify_runtime_binding()"
                    )
                    % str(release / "src"),
                ],
                cwd=release,
                env={"PATH": "/usr/bin:/bin"},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(b"mcp_runtime_expected_binding_missing", completed.stderr)

    def test_sealed_launcher_rejects_manifest_bound_source_tampering(self) -> None:
        builder = _builder()
        with tempfile.TemporaryDirectory() as temp:
            result = builder.build(Path(temp) / "source-releases")
            source_release = Path(result["release_dir"])
            tampered = Path(temp) / "tampered" / result["release_id"]
            shutil.copytree(source_release, tampered)
            changed = tampered / "src/study_read_mcp/client.py"
            changed.chmod(0o644)
            changed.write_bytes(changed.read_bytes() + b"\n# tampered\n")
            changed.chmod(0o444)
            completed = subprocess.run(
                [
                    str(PYTHON),
                    "-I",
                    "-S",
                    str(tampered / "scripts/sealed_launcher.py"),
                    "--release-root",
                    str(tampered),
                    "--expected-release-id",
                    result["release_id"],
                    "--expected-release-manifest-sha256",
                    result["release_manifest_sha256"],
                    "--mode",
                    "server",
                    "--profile",
                    "ordinary",
                    "--subjects",
                    "math,cs408,english",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn(b"mcp_sealed_release_source_invalid", completed.stderr)


if __name__ == "__main__":
    unittest.main()
