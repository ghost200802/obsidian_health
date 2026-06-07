#!/usr/bin/env python3
"""Extract readable markdown and structured JSON from EPUB files."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from shutil import copyfile
from typing import Iterable
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_ROOT = REPO_ROOT / ".derived" / "epub_extract"
DC_NS = "http://purl.org/dc/elements/1.1/"
OPF_NS = "http://www.idpf.org/2007/opf"
CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
NS = {"dc": DC_NS, "opf": OPF_NS, "ct": CONTAINER_NS}


@dataclass
class ChapterExtraction:
    index: int
    item_id: str
    href: str
    title: str
    text: str
    text_chars: int


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\r\n?", "\n", text)
    lines = [line.strip() for line in text.splitlines()]
    compacted: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = not line
        if is_blank:
            if not previous_blank:
                compacted.append("")
            previous_blank = True
            continue
        compacted.append(re.sub(r"[ \t]+", " ", line))
        previous_blank = False
    return "\n".join(compacted).strip()


def write_json_file(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json_file(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def resolve_epub_path(epub_path: Path) -> Path:
    resolved = epub_path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"EPUB not found: {resolved}")
    return resolved


def repo_relative_without_suffix(source_path: Path) -> Path:
    repo_relative = source_path.relative_to(REPO_ROOT)
    return repo_relative.parent / repo_relative.stem


def target_dir_for(source_path: Path, cache_root: Path) -> Path:
    return cache_root / repo_relative_without_suffix(source_path)


def source_stat_fields(source_path: Path) -> dict[str, object]:
    stat = source_path.stat()
    return {
        "source": str(source_path),
        "source_rel_path": str(source_path.relative_to(REPO_ROOT)) if source_path.is_relative_to(REPO_ROOT) else None,
        "source_type": source_path.suffix.lower().lstrip("."),
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
    }


def manifest_is_fresh(manifest_path: Path, source_path: Path) -> bool:
    payload = read_json_file(manifest_path)
    if not payload or payload.get("status") != "success":
        return False
    source_info = source_stat_fields(source_path)
    for key, value in source_info.items():
        if payload.get(key) != value:
            return False
    artifacts = payload.get("artifacts", {})
    markdown = artifacts.get("markdown")
    json_path = artifacts.get("json")
    return bool(markdown and json_path and Path(markdown).is_file() and Path(json_path).is_file())


def find_opf_path(epub: zipfile.ZipFile) -> str:
    container = ET.fromstring(epub.read("META-INF/container.xml"))
    rootfile = container.find(".//ct:rootfile", NS)
    if rootfile is None:
        raise RuntimeError("EPUB container.xml missing rootfile entry")
    full_path = rootfile.attrib.get("full-path")
    if not full_path:
        raise RuntimeError("EPUB rootfile entry missing full-path")
    return full_path


def extract_metadata(package_root: ET.Element) -> dict[str, object]:
    metadata = package_root.find("opf:metadata", NS)
    if metadata is None:
        return {}

    def first_text(xpath: str) -> str | None:
        node = metadata.find(xpath, NS)
        if node is None or node.text is None:
            return None
        text = normalize_text(node.text)
        return text or None

    creators = []
    for node in metadata.findall("dc:creator", NS):
        text = normalize_text(node.text or "")
        if text:
            creators.append(text)

    subjects = []
    for node in metadata.findall("dc:subject", NS):
        text = normalize_text(node.text or "")
        if text:
            subjects.append(text)

    return {
        "title": first_text("dc:title"),
        "creator": creators[0] if creators else None,
        "creators": creators,
        "language": first_text("dc:language"),
        "publisher": first_text("dc:publisher"),
        "description": first_text("dc:description"),
        "subjects": subjects,
    }


def chapter_to_markdown(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "xml")
    body = soup.body or soup
    title = None
    title_node = body.find(["h1", "h2", "title"])
    if title_node:
        title = normalize_text(title_node.get_text(" ", strip=True))

    parts: list[str] = []
    for node in body.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        text = normalize_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if node.name == "h1":
            parts.append(f"# {text}")
        elif node.name == "h2":
            parts.append(f"## {text}")
        elif node.name == "h3":
            parts.append(f"### {text}")
        elif node.name == "h4":
            parts.append(f"#### {text}")
        elif node.name == "li":
            parts.append(f"- {text}")
        elif node.name == "blockquote":
            parts.append(f"> {text}")
        else:
            parts.append(text)

    markdown = normalize_text("\n\n".join(parts))
    if not title:
        title = f"Chapter"
    return title, markdown


def extract_epub(epub_path: Path) -> tuple[dict[str, object], list[ChapterExtraction]]:
    with zipfile.ZipFile(epub_path) as epub:
        opf_path = find_opf_path(epub)
        package_root = ET.fromstring(epub.read(opf_path))
        metadata = extract_metadata(package_root)

        manifest: dict[str, str] = {}
        for item in package_root.findall("opf:manifest/opf:item", NS):
            item_id = item.attrib.get("id")
            href = item.attrib.get("href")
            if item_id and href:
                manifest[item_id] = href

        opf_dir = posixpath.dirname(opf_path)
        chapters: list[ChapterExtraction] = []
        for index, itemref in enumerate(package_root.findall("opf:spine/opf:itemref", NS), start=1):
            item_id = itemref.attrib.get("idref")
            if not item_id or item_id not in manifest:
                continue
            href = manifest[item_id]
            chapter_zip_path = posixpath.normpath(posixpath.join(opf_dir, href))
            if chapter_zip_path not in epub.namelist():
                continue
            html = epub.read(chapter_zip_path).decode("utf-8", errors="replace")
            title, markdown = chapter_to_markdown(html)
            if not markdown:
                continue
            chapters.append(
                ChapterExtraction(
                    index=index,
                    item_id=item_id,
                    href=chapter_zip_path,
                    title=title,
                    text=markdown,
                    text_chars=len(markdown),
                )
            )

    if not chapters:
        raise RuntimeError("EPUB extraction produced no readable chapters")
    return metadata, chapters


def build_markdown(epub_path: Path, metadata: dict[str, object], chapters: Iterable[ChapterExtraction]) -> str:
    chapter_list = list(chapters)
    lines = [
        f"# {metadata.get('title') or epub_path.stem}",
        "",
        f"- source: {epub_path}",
        f"- generated_at: {now_iso()}",
        f"- chapter_count: {len(chapter_list)}",
    ]
    if metadata.get("creator"):
        lines.append(f"- creator: {metadata['creator']}")
    if metadata.get("language"):
        lines.append(f"- language: {metadata['language']}")
    lines.append("")
    for chapter in chapter_list:
        lines.append(f"## Chapter {chapter.index}: {chapter.title}")
        lines.append("")
        lines.append(chapter.text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_json_payload(epub_path: Path, metadata: dict[str, object], chapters: Iterable[ChapterExtraction]) -> dict[str, object]:
    chapter_list = list(chapters)
    return {
        **source_stat_fields(epub_path),
        "generated_at": now_iso(),
        "status": "success",
        "tool": {
            "name": "epub_extract.py",
            "parser": "zipfile+xml+beautifulsoup",
        },
        "metadata": metadata,
        "chapter_count": len(chapter_list),
        "stats": {
            "total_text_chars": sum(chapter.text_chars for chapter in chapter_list),
        },
        "chapters": [
            {
                "index": chapter.index,
                "item_id": chapter.item_id,
                "href": chapter.href,
                "title": chapter.title,
                "text_chars": chapter.text_chars,
                "text": chapter.text,
            }
            for chapter in chapter_list
        ],
    }


def build_manifest(epub_path: Path, markdown_path: Path, json_path: Path) -> dict[str, object]:
    return {
        **source_stat_fields(epub_path),
        "generated_at": now_iso(),
        "status": "success",
        "tool": {
            "name": "epub_extract.py",
            "parser": "zipfile+xml+beautifulsoup",
        },
        "artifacts": {
            "markdown": str(markdown_path),
            "json": str(json_path),
        },
    }


def cache_document(epub_path: Path, cache_root: Path, force: bool) -> tuple[dict[str, object], Path, Path, str]:
    target_dir = target_dir_for(epub_path, cache_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = target_dir / "full.md"
    json_path = target_dir / "full.json"
    manifest_path = target_dir / "manifest.json"

    if not force and manifest_is_fresh(manifest_path, epub_path):
        payload = read_json_file(json_path)
        if payload is None:
            raise RuntimeError(f"Fresh manifest exists but JSON payload is missing or unreadable: {json_path}")
        return payload, markdown_path, json_path, "fresh"

    metadata, chapters = extract_epub(epub_path)
    markdown_content = build_markdown(epub_path, metadata, chapters)
    payload = build_json_payload(epub_path, metadata, chapters)
    markdown_path.write_text(markdown_content, encoding="utf-8")
    write_json_file(json_path, payload)
    write_json_file(manifest_path, build_manifest(epub_path, markdown_path, json_path))
    return payload, markdown_path, json_path, "written"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract text and structure from EPUB files.")
    parser.add_argument("epub_path", help="Path to the EPUB file.")
    parser.add_argument("--cache-root", default=str(DEFAULT_CACHE_ROOT), help="Root directory for persistent extraction cache.")
    parser.add_argument("--force", action="store_true", help="Ignore fresh cache and re-extract.")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary.")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    epub_path = resolve_epub_path(Path(args.epub_path))
    cache_root = Path(args.cache_root).expanduser().resolve()
    payload, markdown_path, json_path, cache_status = cache_document(epub_path, cache_root, args.force)
    if args.json:
        print(
            json.dumps(
                {
                    "cache_status": cache_status,
                    "markdown": str(markdown_path),
                    "json": str(json_path),
                    "payload": payload,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"source: {payload['source']}")
        print(f"cache_status: {cache_status}")
        print(f"markdown: {markdown_path}")
        print(f"json: {json_path}")
        print(f"chapter_count: {payload['chapter_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
