#!/usr/bin/env python3
"""Tests for the collig-personas market repository and its data contract."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_personas import (  # noqa: E402
    build_index,
    render_index,
    secret_hits,
    slug_problem,
    validate_repository,
)


def make_persona(root: Path, slug: str = "test-persona", dossier: str = "# Test\n\nBody.\n", extra=None) -> Path:
    persona = root / "personas" / slug
    persona.mkdir(parents=True, exist_ok=True)
    meta = {
        "slug": slug,
        "name": "Test Persona",
        "display_name": "Test Persona",
        "canonical_name": "Test Persona",
        "description": "A test persona.",
        "updated_at": "2026-01-01T00:00:00",
        "aliases": ["Tester"],
        "sources": [{"title": "Example", "url": "https://example.com"}],
    }
    (persona / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (persona / "PERSONALITY.md").write_text(dossier, encoding="utf-8")
    (persona / "sources.md").write_text("# Sources\n\n- https://example.com\n", encoding="utf-8")
    if extra:
        (persona / extra).write_text("extra", encoding="utf-8")
    return persona


class PersonaMarketTests(unittest.TestCase):
    def test_repository_is_valid_and_index_is_current(self):
        report = validate_repository(ROOT, check_index=True)
        self.assertFalse(report.errors, "\n".join(report.errors))
        self.assertGreaterEqual(len(report.personas), 1)
        self.assertEqual((ROOT / "index.json").read_text(encoding="utf-8"), render_index(ROOT))

    def test_build_index_is_deterministic(self):
        first = build_index(ROOT)
        second = build_index(ROOT)
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], 1)
        self.assertEqual(first["persona_count"], len(first["personas"]))

    def test_slug_rejects_traversal_and_control_characters(self):
        self.assertTrue(slug_problem("../escape"))
        self.assertTrue(slug_problem("a/b"))
        self.assertTrue(slug_problem(".."))
        self.assertTrue(slug_problem(".hidden"))
        self.assertTrue(slug_problem("bad\x00name"))
        self.assertEqual(slug_problem("鲁迅"), "")
        self.assertEqual(slug_problem("anthony-albanese"), "")

    def test_secret_patterns_are_detected(self):
        self.assertIn("openai-key", secret_hits("key sk-" + "a" * 32))
        self.assertIn("github-token", secret_hits("ghp_" + "a" * 30))
        self.assertIn("private-key", secret_hits("-----BEGIN PRIVATE KEY-----"))
        self.assertEqual(secret_hits("# A literary note about tokens and secrets"), [])

    def test_valid_fixture_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_persona(root)
            self.assertTrue(validate_repository(root, check_index=False).ok)

    def test_extra_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_persona(root, extra="run.sh")
            report = validate_repository(root, check_index=False)
            self.assertFalse(report.ok)
            self.assertTrue(any("unexpected file" in error for error in report.errors))

    def test_missing_heading_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_persona(root, dossier="No heading here\n")
            report = validate_repository(root, check_index=False)
            self.assertFalse(report.ok)
            self.assertTrue(any("level-1" in error for error in report.errors))

    def test_secret_in_dossier_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_persona(root, dossier="# Test\n\nsk-" + "a" * 32 + "\n")
            report = validate_repository(root, check_index=False)
            self.assertFalse(report.ok)
            self.assertTrue(any("credential" in error for error in report.errors))

    def test_stale_index_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_persona(root)
            (root / "index.json").write_text("{}", encoding="utf-8")
            report = validate_repository(root, check_index=True)
            self.assertFalse(report.ok)
            self.assertTrue(any("stale" in error for error in report.errors))


if __name__ == "__main__":
    unittest.main()
