#!/usr/bin/env python3
"""Regression tests for configuration, source-note, refresh, and wiki checks."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "research_wiki.py"
SPEC = importlib.util.spec_from_file_location("research_wiki", SCRIPT)
assert SPEC and SPEC.loader
research_wiki = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(research_wiki)


def sample_item(key: str = "ABC123", title: str = "A Test Paper", version: int = 1) -> dict[str, object]:
    return {
        "key": key,
        "version": version,
        "data": {
            "itemType": "journalArticle",
            "title": title,
            "creators": [{"firstName": "Ada", "lastName": "Lovelace"}],
            "date": "2025",
            "publicationTitle": "Journal of Tests",
            "DOI": "10.1000/test",
            "url": "https://example.test/paper",
            "abstractNote": "Abstract evidence.",
            "dateModified": "2026-07-14T01:02:03Z",
            "tags": [{"tag": "core"}],
        },
    }


class ResearchWikiRegressionTests(unittest.TestCase):
    def run_cli(self, *args: str, offline: bool = False) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if offline:
            env["ZOTERO_LOCAL_API"] = "http://127.0.0.1:1"
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def init_project(self, project: Path, knowledge_base_path: str | None = None) -> Path:
        args = ["init-project", "--project-path", str(project), "--yes"]
        if knowledge_base_path:
            args.extend(["--knowledge-base-path", knowledge_base_path])
        result = self.run_cli(*args, offline=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(json.loads(result.stdout)["knowledge_base_path"])

    def write_source_fixture(
        self,
        project: Path,
        knowledge_base: Path,
        item: dict[str, object],
        priority: str,
        need_fulltext_read: bool | None = None,
    ) -> Path:
        content = research_wiki.render_source_note(
            item,
            [],
            project.name,
            priority,
            need_fulltext_read=need_fulltext_read,
        )
        path = knowledge_base / "sources" / research_wiki.source_note_name(item)
        path.write_text(content, encoding="utf-8")
        research_wiki.add_source_to_index(knowledge_base, path, item)
        fingerprint = research_wiki.source_fingerprint(item, [])
        cache_path = project / ".research-wiki" / "cache" / "items" / f"{item['key']}.json"
        cache_path.write_text(json.dumps({"summary": {"source_fingerprint": fingerprint}}), encoding="utf-8")
        return path

    def test_init_project_without_collection_is_zotero_independent_and_writes_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            knowledge_base = self.init_project(project, "Knowledge Base")
            self.assertEqual(knowledge_base, (project / "Knowledge Base").resolve())
            config = json.loads((project / ".research-wiki" / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["knowledge_base_path"], "Knowledge Base")
            self.assertFalse((project / "Research Base").exists())

    def test_knowledge_and_research_base_checks_do_not_cross_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            self.init_project(project)
            initialized = self.run_cli("init-research-base", "--project-path", str(project), "--yes", offline=True)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            checked = self.run_cli("check", "--project-path", str(project), offline=True)
            payload = json.loads(checked.stdout)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertTrue(payload["valid"])
            serialized = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("Research Base/", serialized)

    def test_full_handoff_and_priority_defaults(self) -> None:
        content = research_wiki.render_source_note(
            sample_item(),
            [],
            "Project Alpha",
            "medium",
            boss_category="theory_mechanism",
            boss_screening_reason="Core mechanism source",
            pdf_status="manual_pdf_pending",
            project_use="mechanism",
            read_level="intro_design_conclusion",
            source_route="google_scholar",
            verification_status="verified",
        )
        fields = research_wiki.parse_frontmatter(content)
        assert fields is not None
        self.assertEqual(fields["project"], "Project Alpha")
        self.assertEqual(fields["boss_category"], "theory_mechanism")
        self.assertEqual(fields["boss_screening_reason"], "Core mechanism source")
        self.assertEqual(fields["pdf_status"], "manual_pdf_pending")
        self.assertEqual(fields["project_use"], "mechanism")
        self.assertEqual(fields["source_route"], "google_scholar")
        self.assertEqual(fields["verification_status"], "verified")
        self.assertTrue(fields["need_fulltext_read"])
        self.assertEqual(fields["read_level"], "intro_design_conclusion")

        overridden = research_wiki.parse_frontmatter(
            research_wiki.render_source_note(sample_item(), [], "Project Alpha", "medium", need_fulltext_read=False)
        )
        assert overridden is not None
        self.assertFalse(overridden["need_fulltext_read"])

    def test_low_and_exclude_do_not_require_fulltext(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            knowledge_base = self.init_project(project)
            self.write_source_fixture(project, knowledge_base, sample_item("LOW001", "Low Priority Paper"), "low")
            self.write_source_fixture(project, knowledge_base, sample_item("EXC001", "Excluded Paper"), "exclude")
            result = self.run_cli("check", "--project-path", str(project), offline=True)
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("missing_required_fulltext", {entry["code"] for entry in payload["warnings"]})

    def test_refresh_preserves_read_state_manual_sections_and_created_date(self) -> None:
        original_item = sample_item()
        original = research_wiki.render_source_note(original_item, [], "Project Alpha", "high")
        original = original.replace("status: \"screened\"", "status: \"deep_read_done\"")
        original = original.replace("need_fulltext_read: true", "need_fulltext_read: false")
        original = original.replace("deep_read_completed: ", "deep_read_completed: \"2026-07-01\"")
        original = original.replace("read_level: \"abstract\"", "read_level: \"fulltext\"")
        original = original.replace("### 5.1 主要结论\n-", "### 5.1 主要结论\n- MANUAL-CONCLUSION")
        original = research_wiki.replace_frontmatter_fields(original, {"created": "2020-01-01T00:00:00+00:00"})
        original_fields = research_wiki.parse_frontmatter(original)
        assert original_fields is not None

        changed_item = sample_item(title="A Revised Test Paper", version=2)
        fresh = research_wiki.render_source_note(
            changed_item,
            [{"key": "ANN1", "data": {"itemType": "annotation", "annotationText": "New annotation"}}],
            "Project Alpha",
            "high",
        )
        refreshed = research_wiki.refresh_source_note_content(original, fresh)
        refreshed_fields = research_wiki.parse_frontmatter(refreshed)
        assert refreshed_fields is not None
        self.assertEqual(refreshed_fields["status"], "deep_read_done")
        self.assertFalse(refreshed_fields["need_fulltext_read"])
        self.assertEqual(refreshed_fields["read_level"], "fulltext")
        self.assertEqual(refreshed_fields["deep_read_completed"], "2026-07-01")
        self.assertEqual(refreshed_fields["created"], "2020-01-01T00:00:00+00:00")
        self.assertEqual(refreshed_fields["title"], "A Revised Test Paper")
        self.assertIn("MANUAL-CONCLUSION", refreshed)
        self.assertIn("New annotation", refreshed)

    def test_deprecated_overwrite_needs_second_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            knowledge_base = self.init_project(project)
            item = sample_item()
            path = self.write_source_fixture(project, knowledge_base, item, "high")
            before = path.read_text(encoding="utf-8") + "\nMANUAL\n"
            path.write_text(before, encoding="utf-8")
            args = argparse.Namespace(
                project_path=str(project), project=None, vault=str(project.parent), knowledge_base_path=None,
                yes=True, item_key="ABC123", project_name=None, priority="high", boss_category=None,
                boss_screening_reason=None, pdf_status="unknown", project_use=None, need_fulltext_read=None,
                read_level="abstract", deep_read_completed=None, source_route="unknown",
                verification_status="unverified", overwrite=True, confirm_destructive_overwrite=False,
            )
            with mock.patch.object(research_wiki, "item_by_key", return_value=item), mock.patch.object(
                research_wiki, "child_notes_and_annotations", return_value=[]
            ):
                with self.assertRaises(research_wiki.ResearchWikiError):
                    research_wiki.command_source_note(args)
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_check_reports_stale_fingerprint_and_only_required_fulltext(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            knowledge_base = self.init_project(project)
            item = sample_item("HIGH01")
            self.write_source_fixture(project, knowledge_base, item, "high")
            cache = project / ".research-wiki" / "cache" / "items" / "HIGH01.json"
            cache.write_text(json.dumps({"summary": {"source_fingerprint": "changed"}}), encoding="utf-8")
            result = self.run_cli("check", "--project-path", str(project), offline=True)
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0, result.stderr)
            codes = {entry["code"] for entry in payload["warnings"]}
            self.assertEqual(codes, {"missing_required_fulltext", "stale_source_fingerprint"})

    def test_duplicate_filenames_require_path_qualified_index_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            knowledge_base = self.init_project(project)
            (knowledge_base / "concepts" / "shared.md").write_text("# Concept\n", encoding="utf-8")
            (knowledge_base / "methods" / "shared.md").write_text("# Method\n", encoding="utf-8")
            index = knowledge_base / "index.md"
            index.write_text(index.read_text(encoding="utf-8") + "\n- [[shared]]\n", encoding="utf-8")
            result = self.run_cli("check", "--project-path", str(project), offline=True)
            payload = json.loads(result.stdout)
            self.assertEqual(result.returncode, 1)
            unindexed = [entry for entry in payload["errors"] if entry["code"] == "unindexed_page"]
            self.assertEqual(len(unindexed), 2)
            compatible = self.run_cli("check", "--project-path", str(project), "--report-only", offline=True)
            self.assertEqual(compatible.returncode, 0)

    def test_multiline_yaml_list_and_promotion_state_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            initialized = self.run_cli("init-research-base", "--project-path", str(project), "--yes", offline=True)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            base = project / "Research Base"
            note = base / "01_Topic_Exploration" / "promoted.md"
            note.write_text(
                """---
type: topic_exploration
status: promoted
evidence_status: verified
created: 2026-07-14
last_updated: 2026-07-14
kb_promotion: true
related_kb_pages:
  - "[[claims/promoted-claim]]"
supersedes:
promoted_at: 2026-07-14
superseded_by:
decision_reason: verified and reusable
---
# Promoted
""",
                encoding="utf-8",
            )
            index = base / "index.md"
            index.write_text(index.read_text(encoding="utf-8") + "\n- [[01_Topic_Exploration/promoted]]\n", encoding="utf-8")
            result = self.run_cli("check-research-base", "--project-path", str(project), offline=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(json.loads(result.stdout)["valid"])

    def test_custom_research_base_path_and_schema_from_project_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            (project / ".research-wiki").mkdir(parents=True)
            schema_path = project / ".research-wiki" / "custom-schema.json"
            schema_path.write_text(
                json.dumps(
                    {
                        "directories": ["Ideas", "_templates"],
                        "note_types": ["idea"],
                        "statuses": ["candidate", "promoted", "rejected", "superseded"],
                        "evidence_statuses": ["unchecked", "verified"],
                        "required_fields": list(research_wiki.RESEARCH_BASE_REQUIRED_FIELDS),
                    }
                ),
                encoding="utf-8",
            )
            (project / ".research-wiki" / "config.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "knowledge_base_path": ".",
                        "research_base_path": "Research Lab",
                        "research_base_schema_path": ".research-wiki/custom-schema.json",
                    }
                ),
                encoding="utf-8",
            )
            initialized = self.run_cli("init-research-base", "--project-path", str(project), "--yes", offline=True)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            base = project / "Research Lab"
            note = base / "Ideas" / "candidate.md"
            note.write_text(
                """---
type: idea
status: candidate
evidence_status: unchecked
created: 2026-07-14
last_updated: 2026-07-14
kb_promotion: false
related_kb_pages: []
supersedes:
---
# Candidate
""",
                encoding="utf-8",
            )
            index = base / "index.md"
            index.write_text(index.read_text(encoding="utf-8") + "\n- [[Ideas/candidate]]\n", encoding="utf-8")
            result = self.run_cli("check-research-base", "--project-path", str(project), offline=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(json.loads(result.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
