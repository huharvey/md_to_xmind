#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2xmind.py -- Convert Obsidian Markdown files to XMind Zen (.xmind) files.

Usage:
    python md2xmind.py <file.md>
    python md2xmind.py <directory>
"""

import json
import os
import re
import sys
import uuid
import zipfile


class Node:
    __slots__ = ("title", "children")

    def __init__(self, title: str):
        self.title = title
        self.children = []

    def add(self, child):
        self.children.append(child)
        return child


_RE_OBSIDIAN_IMG = re.compile(r"!\[\[.*?\]\]")
_RE_OBSIDIAN_LINK_DISPLAY = re.compile(r"\[\[([^\]]*?\|)([^\]]+?)\]\]")
_RE_OBSIDIAN_LINK_PLAIN = re.compile(r"\[\[([^\]]+?)\]\]")
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
_RE_HIGHLIGHT = re.compile(r"==(.+?)==")
_RE_INLINE_CODE = re.compile(r'`([^`]+)`')
_RE_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]+\)")
_RE_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
_RE_LIST_ITEM = re.compile(r"^(\s*)-\s+(.*)$")
_RE_ORDERED_ITEM = re.compile(r"^(\s*)\d+\.\s+(.*)$")
_RE_BLOCKQUOTE = re.compile(r"^>\s?(.*)")
_RE_TABLE_ROW = re.compile(r"^\|(.+?)\|$")
_RE_TABLE_SEP = re.compile(r"^\|[\s:|\-]+\|$")


def _clean_text(text: str) -> str:
    text = _RE_OBSIDIAN_IMG.sub("", text)
    text = _RE_OBSIDIAN_LINK_DISPLAY.sub(r"\2", text)
    text = _RE_OBSIDIAN_LINK_PLAIN.sub(r"\1", text)
    text = _RE_BOLD.sub(r"\1", text)
    text = _RE_HIGHLIGHT.sub(r"\1", text)
    text = _RE_MD_LINK.sub(r"\1", text)
    text = _RE_INLINE_CODE.sub(r"\1", text)
    return text.strip()


def _is_image_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("![[") and stripped.endswith("]]")


def _indent_level(leading_spaces: str, unit: int = 2) -> int:
    width = 0
    for ch in leading_spaces:
        if ch == "\t":
            width += 4
        else:
            width += 1
    return width // unit


def _add_list_item(parent, indent, text, base_indent):
    depth = indent - base_indent
    if depth <= 0 or not parent.children:
        parent.add(Node(text))
    else:
        _add_list_item(parent.children[-1], indent, text, base_indent + 1)


def parse_markdown(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not any(line.strip() for line in lines):
        return None

    basename = os.path.splitext(os.path.basename(filepath))[0]
    root = Node(basename)

    heading_stack = [(1, root)]
    para_buf = []
    current_parent = root
    in_code_block = False
    code_buf = []
    table_header = None
    table_rows = []

    def _flush_para():
        nonlocal para_buf
        if para_buf:
            text = " ".join(para_buf)
            text = _clean_text(text)
            if text:
                current_parent.add(Node(text))
            para_buf = []

    def _flush_code():
        nonlocal code_buf
        if code_buf:
            text = "\n".join(code_buf)
            if text.strip():
                current_parent.add(Node(text))
            code_buf = []

    def _flush_table():
        nonlocal table_header, table_rows
        if table_header is not None:
            lines_out = []
            lines_out.append(" | ".join(table_header))
            for row in table_rows:
                lines_out.append(" | ".join(row))
            node_text = "\n".join(lines_out)
            if node_text.strip():
                current_parent.add(Node(node_text))
        table_header = None
        table_rows = []

    i = 0
    while i < len(lines):
        raw_line = lines[i].rstrip("\n\r")
        i += 1

        if raw_line.strip().startswith("```"):
            if in_code_block:
                _flush_code()
                in_code_block = False
            else:
                _flush_para()
                _flush_table()
                in_code_block = True
            continue
        if in_code_block:
            code_buf.append(raw_line)
            continue

        if _is_image_line(raw_line):
            continue

        stripped = raw_line.strip()

        if stripped.startswith("![[") and stripped.endswith("]]"):
            continue

        if stripped == "":
            _flush_para()
            _flush_table()
            continue

        m_table = _RE_TABLE_ROW.match(stripped)
        if m_table:
            _flush_para()
            if _RE_TABLE_SEP.match(stripped):
                continue
            cells = [c.strip() for c in m_table.group(1).split("|")]
            cells = [_clean_text(c) for c in cells]
            if table_header is None:
                table_header = cells
            else:
                table_rows.append(cells)
            continue

        if table_header is not None:
            _flush_table()

        m_heading = _RE_HEADING.match(stripped)
        if m_heading:
            _flush_para()
            level = len(m_heading.group(1))
            title = _clean_text(m_heading.group(2))

            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()

            parent = heading_stack[-1][1] if heading_stack else root
            node = parent.add(Node(title))
            heading_stack.append((level, node))
            current_parent = node
            continue

        m_list = _RE_LIST_ITEM.match(raw_line)
        if m_list:
            _flush_para()
            indent = _indent_level(m_list.group(1))
            text = _clean_text(m_list.group(2))
            if not text:
                continue
            _add_list_item(current_parent, indent, text, 0)
            continue

        m_ord = _RE_ORDERED_ITEM.match(raw_line)
        if m_ord:
            _flush_para()
            indent = _indent_level(m_ord.group(1))
            text = _clean_text(m_ord.group(2))
            if not text:
                continue
            _add_list_item(current_parent, indent, text, 0)
            continue

        m_bq = _RE_BLOCKQUOTE.match(stripped)
        if m_bq:
            bq_text = _clean_text(m_bq.group(1))
            if bq_text:
                para_buf.append(bq_text)
            continue

        cleaned = _clean_text(stripped)
        if cleaned:
            para_buf.append(cleaned)

    _flush_para()
    _flush_code()
    _flush_table()

    return root


def _make_id() -> str:
    return uuid.uuid4().hex[:24]


def _node_to_topic(node) -> dict:
    topic = {
        "id": _make_id(),
        "class": "topic",
        "title": node.title,
    }
    if node.children:
        topic["children"] = {
            "attached": [_node_to_topic(c) for c in node.children]
        }
    return topic


def build_xmind_content(root) -> list:
    root_topic = _node_to_topic(root)
    root_topic["structureClass"] = "org.xmind.ui.map.unbalanced"

    sheet = {
        "id": _make_id(),
        "class": "sheet",
        "title": root.title,
        "rootTopic": root_topic,
    }
    return [sheet]


def save_xmind(content, output_path: str):
    metadata = {
        "creator": {
            "name": "md2xmind.py",
            "version": "1.0.0",
        }
    }
    manifest = {
        "file-entries": {
            "content.json": {},
            "metadata.json": {},
        }
    }
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.json", json.dumps(content, ensure_ascii=False, indent=2))
        zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))


def convert_file(md_path: str):
    root = parse_markdown(md_path)
    if root is None:
        print(f"  skip (empty): {md_path}")
        return
    xmind_path = os.path.splitext(md_path)[0] + ".xmind"
    content = build_xmind_content(root)
    save_xmind(content, xmind_path)
    print(f"  done: {xmind_path}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target = sys.argv[1]

    if os.path.isfile(target):
        if not target.lower().endswith(".md"):
            print(f"Error: not a .md file: {target}")
            sys.exit(1)
        print(f"Converting: {target}")
        convert_file(target)

    elif os.path.isdir(target):
        md_files = sorted(
            f for f in os.listdir(target)
            if f.lower().endswith(".md")
        )
        if not md_files:
            print(f"No .md files in: {target}")
            sys.exit(1)
        print(f"Batch converting: {target} ({len(md_files)} .md files)")
        for fname in md_files:
            convert_file(os.path.join(target, fname))
        print("All done!")

    else:
        print(f"Error: path not found: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
