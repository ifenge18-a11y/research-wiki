#!/usr/bin/env python3
"""Regression tests for the opt-in Research Base helper commands."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "research_wiki.py"


class ResearchBaseCommandTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            check=False,
            capture_output=True,
            text=True,
        )

    def init_base(self, project: Path) -> Path:
        result = self.run_cli("init-research-base", "--project-path", str(project), "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        return project / "Research Base"

    def check_base(self, project: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        result = self.run_cli("check-research-base", "--project-path", str(project))
        return result, json.loads(result.stdout)

    @staticmethod
    def note(note_type: str, status: str = "exploratory", evidence: str = "unverified") -> str:
        return f"""---
type: {note_type}
status: {status}
evidence_status: {evidence}
created: 2026-07-14
last_updated: 2026-07-14
kb_promotion: false
related_kb_pages: []
supersedes:
---
# Test note
"""

    def test_dry_run_does_not_create_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            result = self.run_cli("init-research-base", "--project-path", str(project))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(project.exists())
            self.assertTrue(json.loads(result.stdout)["dry_run"])

    def test_init_creates_complete_default_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = self.init_base(Path(temp) / "project")
            for name in ("README.md", "index.md", "log.md"):
                self.assertTrue((base / name).is_file())
            for name in (
                "00_Conversation_Notes",
                "01_Topic_Exploration",
                "02_Method_Prototypes",
                "03_Data_Feasibility",
                "04_Design_Alternatives",
                "90_Archived_or_Rejected",
                "_templates",
            ):
                self.assertTrue((base / name).is_dir())
            self.assertEqual(len(list((base / "_templates").glob("*.md"))), 5)

    def test_explicit_research_base_path_overrides_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            custom_base = root / "custom-research-base"
            result = self.run_cli(
                "init-research-base",
                "--project-path",
                str(project),
                "--research-base-path",
                str(custom_base),
                "--yes",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((custom_base / "README.md").is_file())
            self.assertFalse((project / "Research Base").exists())

    def test_valid_prototype_passes_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            base = self.init_base(project)
            note = base / "02_Method_Prototypes" / "prototype.md"
            note.write_text(self.note("method_prototype"), encoding="utf-8")
            (base / "index.md").write_text(
                (base / "index.md").read_text(encoding="utf-8")
                + "\n- [[02_Method_Prototypes/prototype]] - test prototype\n",
                encoding="utf-8",
            )
            result, payload = self.check_base(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(payload["valid"])

    def test_duplicate_source_note_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            base = self.init_base(project)
            note = base / "01_Topic_Exploration" / "bad-source.md"
            note.write_text(
                self.note("topic_exploration").replace("supersedes:\n", "supersedes:\nzotero_item_key: ABC123\n"),
                encoding="utf-8",
            )
            (base / "index.md").write_text(
                (base / "index.md").read_text(encoding="utf-8") + "\n- [[01_Topic_Exploration/bad-source]]\n",
                encoding="utf-8",
            )
            result, payload = self.check_base(project)
            self.assertEqual(result.returncode, 1)
            self.assertIn("duplicate_source_note", {item["code"] for item in payload["findings"]})

    def test_invalid_promotion_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            base = self.init_base(project)
            note = base / "04_Design_Alternatives" / "promotion.md"
            note.write_text(self.note("design_alternative", status="promoted"), encoding="utf-8")
            (base / "index.md").write_text(
                (base / "index.md").read_text(encoding="utf-8") + "\n- [[04_Design_Alternatives/promotion]]\n",
                encoding="utf-8",
            )
            result, payload = self.check_base(project)
            self.assertEqual(result.returncode, 1)
            codes = {item["code"] for item in payload["findings"]}
            self.assertTrue({"promotion_without_verified_evidence", "promotion_flag_missing", "promotion_link_missing"} <= codes)

    def test_archived_note_remains_valid_and_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            base = self.init_base(project)
            note = base / "90_Archived_or_Rejected" / "rejected.md"
            note.write_text(self.note("design_alternative", status="rejected"), encoding="utf-8")
            (base / "index.md").write_text(
                (base / "index.md").read_text(encoding="utf-8") + "\n- [[90_Archived_or_Rejected/rejected]] - rejected path\n",
                encoding="utf-8",
            )
            result, payload = self.check_base(project)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(payload["valid"])


if __name__ == "__main__":
    unittest.main()
