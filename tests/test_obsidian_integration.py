#!/usr/bin/env python3
"""Regression tests for optional Obsidian Markdown, Bases, and CLI integration."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "research_wiki.py"
SPEC = importlib.util.spec_from_file_location("research_wiki_obsidian", SCRIPT)
assert SPEC and SPEC.loader
research_wiki = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(research_wiki)


class ObsidianIntegrationTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def init_project(self, project: Path, *extra: str) -> dict[str, object]:
        result = self.run_cli("init-project", "--project-path", str(project), *extra, "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_bases_remain_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            self.init_project(project)
            self.assertFalse((project / "knowledge.base").exists())
            config = json.loads((project / ".research-wiki" / "config.json").read_text(encoding="utf-8"))
            self.assertFalse(config["obsidian_bases_enabled"])
            self.assertEqual(config["schema_version"], 2)

    def test_init_bases_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            self.init_project(project)
            result = self.run_cli("init-obsidian-bases", "--project-path", str(project))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["dry_run"])
            self.assertFalse((project / "knowledge.base").exists())

    def test_init_project_creates_project_scoped_knowledge_base_and_embed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            payload = self.init_project(
                project,
                "--knowledge-base-path",
                "Knowledge Base",
                "--project-name",
                "O'Brien \"Alpha\"",
                "--with-obsidian-bases",
            )
            knowledge = project / "Knowledge Base"
            base_text = (knowledge / "knowledge.base").read_text(encoding="utf-8")
            self.assertIn("O''Brien", base_text)
            self.assertIn('\\"Alpha\\"', base_text)
            self.assertIn('name: "Reading Queue"', base_text)
            self.assertIn("![[knowledge.base]]", (knowledge / "index.md").read_text(encoding="utf-8"))
            self.assertFalse((project / "Research Base").exists())
            self.assertTrue(payload["obsidian_bases"]["created"])

    def test_research_base_flag_creates_base_and_project_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            self.init_project(project, "--project-name", "Project Alpha")
            result = self.run_cli(
                "init-research-base",
                "--project-path",
                str(project),
                "--with-obsidian-bases",
                "--yes",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            base = project / "Research Base"
            self.assertTrue((base / "research.base").is_file())
            self.assertIn("![[research.base]]", (base / "index.md").read_text(encoding="utf-8"))
            template = (base / "_templates" / "topic-exploration.md").read_text(encoding="utf-8")
            self.assertIn('project: "Project Alpha"', template)
            self.assertIn("tags: []", template)

    def test_custom_research_base_path_receives_dynamic_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            self.init_project(project, "--research-base-path", "Research Lab")
            result = self.run_cli(
                "init-research-base",
                "--project-path",
                str(project),
                "--with-obsidian-bases",
                "--yes",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((project / "Research Lab" / "research.base").is_file())
            self.assertFalse((project / "Research Base").exists())

    def test_all_scope_skips_absent_research_base(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            self.init_project(project)
            result = self.run_cli(
                "init-obsidian-bases",
                "--project-path",
                str(project),
                "--scope",
                "all",
                "--yes",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["skipped"][0]["scope"], "research")
            self.assertTrue((project / "knowledge.base").is_file())
            self.assertFalse((project / "Research Base").exists())

    def test_existing_schema_one_config_is_upgraded_without_losing_custom_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            (project / ".research-wiki").mkdir(parents=True)
            (project / "KB").mkdir()
            (project / "KB" / "index.md").write_text("# Index\n", encoding="utf-8")
            (project / ".research-wiki" / "config.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "knowledge_base_path": "KB",
                        "research_base_path": "Research Lab",
                        "custom_setting": "preserve-me",
                    }
                ),
                encoding="utf-8",
            )
            result = self.run_cli(
                "init-obsidian-bases",
                "--project-path",
                str(project),
                "--scope",
                "knowledge",
                "--yes",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads((project / ".research-wiki" / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["schema_version"], 2)
            self.assertEqual(config["knowledge_base_path"], "KB")
            self.assertEqual(config["custom_setting"], "preserve-me")
            self.assertEqual(config["project_name"], "project")

    def test_source_note_uses_multiline_abstract_callout_without_duplicate_placeholders(self) -> None:
        item = {
            "key": "MULTI1",
            "data": {
                "title": "Multiline Abstract",
                "creators": [],
                "date": "2026",
                "abstractNote": "First line.\nSecond line.",
            },
        }
        content = research_wiki.render_source_note(item, [], "Project", "low")
        self.assertIn("> [!abstract] 摘要\n> First line.\n> Second line.", content)
        self.assertNotIn("- 摘要：", content)
        self.assertEqual(content.count("- 需要补充的 Zotero 注释："), 1)

    def test_check_obsidian_filters_to_project_and_validates_base_views(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp) / "Vault"
            project = vault / "Project"
            self.init_project(project, "--with-obsidian-bases")

            def completed(arguments: list[str], stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
                return subprocess.CompletedProcess(arguments, returncode, stdout=stdout, stderr=stderr)

            def fake_cli(arguments: list[str], _executable: str) -> subprocess.CompletedProcess[str]:
                if arguments == ["vaults", "verbose"]:
                    return completed(arguments, f"Test Vault\t{vault}\n")
                if "unresolved" in arguments:
                    return completed(
                        arguments,
                        json.dumps(
                            [
                                {"link": "Missing", "count": "1", "sources": "Project/sources/a.md"},
                                {"link": "Elsewhere", "count": "1", "sources": "Other/b.md"},
                            ]
                        ),
                    )
                if "orphans" in arguments:
                    return completed(arguments, "Project/concepts/orphan.md\nOther/orphan.md\n")
                if "deadends" in arguments:
                    return completed(arguments, "Project/claims/dead.md\n")
                if "base:query" in arguments:
                    return completed(arguments, "\n" if "view=Synthesis" in arguments else "[]\n")
                raise AssertionError(arguments)

            args = argparse.Namespace(
                project_path=str(project),
                project=None,
                vault=str(vault),
                obsidian_cli="obsidian",
                report_only=False,
            )
            output = io.StringIO()
            with mock.patch.object(research_wiki, "run_obsidian_cli", side_effect=fake_cli), contextlib.redirect_stdout(output):
                result = research_wiki.command_check_obsidian(args)
            payload = json.loads(output.getvalue())
            self.assertEqual(result, 1)
            self.assertEqual({entry["code"] for entry in payload["errors"]}, {"unresolved_link"})
            self.assertEqual(
                {entry["code"] for entry in payload["warnings"]},
                {"graph_orphan", "deadend"},
            )
            self.assertEqual(payload["stats"]["base_views_checked"], 4)

    def test_check_obsidian_reports_missing_cli_as_machine_readable_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            self.init_project(project)
            result = self.run_cli(
                "check-obsidian",
                "--project-path",
                str(project),
                "--obsidian-cli",
                str(project / "missing-obsidian"),
            )
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["errors"][0]["code"], "obsidian_cli_unavailable")

    def test_check_obsidian_reports_failed_base_query(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp) / "Vault"
            project = vault / "Project"
            self.init_project(project, "--with-obsidian-bases")

            def fake_cli(arguments: list[str], _executable: str) -> subprocess.CompletedProcess[str]:
                if arguments == ["vaults", "verbose"]:
                    return subprocess.CompletedProcess(arguments, 0, stdout=f"Vault\t{vault}\n", stderr="")
                if "unresolved" in arguments:
                    return subprocess.CompletedProcess(arguments, 0, stdout="[]", stderr="")
                if "orphans" in arguments or "deadends" in arguments:
                    return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")
                if "base:query" in arguments and "view=Reading Queue" in arguments:
                    return subprocess.CompletedProcess(arguments, 0, stdout="Error: Invalid base\n", stderr="")
                if "base:query" in arguments:
                    return subprocess.CompletedProcess(arguments, 0, stdout="[]", stderr="")
                raise AssertionError(arguments)

            args = argparse.Namespace(
                project_path=str(project),
                project=None,
                vault=str(vault),
                obsidian_cli="obsidian",
                report_only=False,
            )
            output = io.StringIO()
            with mock.patch.object(research_wiki, "run_obsidian_cli", side_effect=fake_cli), contextlib.redirect_stdout(output):
                result = research_wiki.command_check_obsidian(args)
            payload = json.loads(output.getvalue())
            self.assertEqual(result, 1)
            self.assertIn("base_query_failed", {entry["code"] for entry in payload["errors"]})
            self.assertEqual(payload["stats"]["base_views_checked"], 3)

    def test_release_docs_and_version_are_consistent(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        integration = (ROOT / "references" / "obsidian-integration.md").read_text(encoding="utf-8")
        self.assertIn('version: "0.3.0"', skill)
        self.assertIn("Version: `0.3.0`", readme)
        self.assertIn("npx skills add https://github.com/kepano/obsidian-skills", readme)
        self.assertIn("npx skills add https://github.com/kepano/obsidian-skills", integration)


if __name__ == "__main__":
    unittest.main()
