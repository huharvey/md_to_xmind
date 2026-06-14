import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from md2xmind import Node
from md2xmind import build_xmind_content
from md2xmind import convert_file
from md2xmind import parse_markdown
from md2xmind import save_xmind


class MarkdownParsingTests(unittest.TestCase):
    def test_parse_markdown_builds_expected_tree(self):
        markdown = """# Project Plan

Background summary.

## Goals
- Define scope
  - Draft prototype
1. Build delivery

> Review risks

| Type | Example |
| --- | --- |
| A | B |
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "note.md"
            md_path.write_text(markdown, encoding="utf-8")

            root = parse_markdown(str(md_path))

        self.assertIsNotNone(root)
        self.assertEqual(root.title, "note")
        self.assertEqual(root.children[0].title, "Project Plan")

        heading = root.children[0]
        self.assertEqual(heading.children[0].title, "Background summary.")
        self.assertEqual(heading.children[1].title, "Goals")

        target = heading.children[1]
        self.assertEqual(target.children[0].title, "Define scope")
        self.assertEqual(target.children[0].children[0].title, "Draft prototype")
        self.assertEqual(target.children[1].title, "Build delivery")
        self.assertEqual(target.children[2].title, "Review risks")
        self.assertEqual(target.children[3].title, "Type | Example\nA | B")


class XMindArchiveTests(unittest.TestCase):
    def test_save_xmind_writes_expected_archive_structure(self):
        root = Node("Root")
        child = root.add(Node("Child"))
        child.add(Node("Leaf"))

        content = build_xmind_content(root)

        with tempfile.TemporaryDirectory() as tmpdir:
            xmind_path = Path(tmpdir) / "sample.xmind"
            save_xmind(content, str(xmind_path))

            self.assertTrue(xmind_path.exists())

            with zipfile.ZipFile(xmind_path, "r") as archive:
                names = set(archive.namelist())
                self.assertEqual(names, {"content.json", "metadata.json", "manifest.json"})

                content_data = json.loads(archive.read("content.json"))
                self.assertEqual(content_data[0]["rootTopic"]["title"], "Root")

    def test_convert_file_creates_output_next_to_markdown(self):
        markdown = "# Title\n\n- Child item\n"

        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "outline.md"
            md_path.write_text(markdown, encoding="utf-8")

            convert_file(str(md_path))

            xmind_path = md_path.with_suffix(".xmind")
            self.assertTrue(xmind_path.exists())


if __name__ == "__main__":
    unittest.main()