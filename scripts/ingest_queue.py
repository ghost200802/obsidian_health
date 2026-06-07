#!/usr/bin/env python3
"""Inspect raw/ coverage and emit one-file-at-a-time ingest queues."""

from __future__ import annotations

import argparse
import json
import os
import posixpath
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "raw"
SOURCE_ROOT = REPO_ROOT / "source"
PDF_CACHE_ROOT = REPO_ROOT / ".derived" / "pdf_extract"
IGNORED_FILE_NAMES = {".DS_Store"}
TRACKED_SOURCE_KEYS = ("raw_path", "raw_variants", "pdf")

BOOK_REINGEST_FIELD = "ingest_version"
BOOK_REINGEST_VERSION = "book-detailed-v2"
RAW_REVIEW_FIELD = "raw_review_version"
RAW_REVIEW_VERSION = "single-file-detailed-v1"
BOOK_ALLOWED_SUFFIXES = {".pdf", ".epub"}
BOOK_INCLUDE_ROOTS = (
    "raw/营养书籍",
    "raw/减肥营养书",
    "raw/心理学",
    "raw/高敏感人群",
    "raw/商业职场",
    "raw/个人成长",
    "raw/教练思维",
    "raw/中国营养学会",
)
BOOK_EXCLUDE_PREFIXES = (
    "raw/中国营养学会/2026发布食养指南/",
    "raw/中国营养学会/其它指南/",
    "raw/中国营养学会/8个-卫健委发布的食养指南-正文+问答/",
)
BOOK_EXCLUDE_KEYWORDS = (
    "指南",
    "规范",
    "标准",
    "共识",
    "问答",
    "原则",
    "行动20条",
    "单页卡",
    "营养导航",
    "画像",
    "正式版",
    "issueCover",
    "issueContent",
    "表述",
)


@dataclass(frozen=True)
class CoverageState:
    raw_files: tuple[str, ...]
    covered_files: frozenset[str]
    covered_dirs: tuple[str, ...]
    pending_files: tuple[str, ...]


@dataclass(frozen=True)
class SourceRecord:
    source_file: str
    frontmatter: dict[str, object]
    raw_path_refs: tuple[str, ...]
    raw_variant_refs: tuple[str, ...]
    pdf_refs: tuple[str, ...]
    all_raw_refs: tuple[str, ...]


@dataclass(frozen=True)
class BookQueueItem:
    raw_path: str
    source_file: str | None
    done: bool
    ingest_done: bool
    raw_review_done: bool
    cached: bool
    cache_markdown: str | None
    cache_json: str | None


@dataclass(frozen=True)
class BookQueueState:
    ingest_version: str
    raw_review_version: str
    candidate_books: tuple[BookQueueItem, ...]
    pending_books: tuple[BookQueueItem, ...]


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def normalize_repo_path(value: str) -> str | None:
    value = strip_quotes(value).replace("\\", "/").strip()
    if not value:
        return None
    if value.startswith("./"):
        value = value[2:]
    repo_prefix = f"{REPO_ROOT.as_posix()}/"
    if value.startswith(repo_prefix):
        value = value[len(repo_prefix) :]
    return posixpath.normpath(value)


def extract_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return ""
    parts = content.split("---", 2)
    if len(parts) < 3:
        return ""
    return parts[1]


def parse_frontmatter(path: Path) -> dict[str, object]:
    frontmatter = extract_frontmatter(path.read_text(encoding="utf-8", errors="ignore"))
    if not frontmatter:
        return {}

    parsed: dict[str, object] = {}
    current_list_key: str | None = None

    for raw_line in frontmatter.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        if line.startswith("  - "):
            if current_list_key is not None:
                parsed.setdefault(current_list_key, [])
                assert isinstance(parsed[current_list_key], list)
                parsed[current_list_key].append(strip_quotes(line[4:].strip()))
            continue

        if ":" not in line:
            current_list_key = None
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            parsed[key] = []
            current_list_key = key
            continue

        parsed[key] = strip_quotes(value)
        current_list_key = None

    return parsed


def expand_source_refs(value: object) -> list[str]:
    if not value:
        return []

    if isinstance(value, list):
        refs: list[str] = []
        for item in value:
            refs.extend(expand_source_refs(item))
        return refs

    if not isinstance(value, str):
        return []

    if ";" in value:
        refs: list[str] = []
        for item in value.split(";"):
            item = item.strip()
            if item:
                refs.append(item)
        return refs

    return [value]


def normalize_refs(refs: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for ref in refs:
        path = normalize_repo_path(ref)
        if path and path.startswith("raw/"):
            normalized.append(path)
    return tuple(dict.fromkeys(normalized))


def iter_raw_files() -> Iterable[str]:
    if not RAW_ROOT.exists():
        return []

    files: list[str] = []
    for root, dirs, names in os.walk(RAW_ROOT):
        dirs[:] = [name for name in dirs if not name.startswith(".")]
        for name in names:
            if name.startswith(".") or name in IGNORED_FILE_NAMES:
                continue
            full_path = Path(root) / name
            files.append(full_path.relative_to(REPO_ROOT).as_posix())
    return sorted(files)


def iter_files_under(rel_dir: str) -> tuple[str, ...]:
    dir_path = REPO_ROOT / rel_dir
    if not dir_path.is_dir():
        return ()

    files: list[str] = []
    for root, dirs, names in os.walk(dir_path):
        dirs[:] = [name for name in dirs if not name.startswith(".")]
        for name in names:
            if name.startswith(".") or name in IGNORED_FILE_NAMES:
                continue
            files.append((Path(root) / name).relative_to(REPO_ROOT).as_posix())
    return tuple(sorted(files))


def is_covered_by_dir(path: str, covered_dirs: Iterable[str]) -> bool:
    for covered_dir in covered_dirs:
        prefix = covered_dir.rstrip("/") + "/"
        if path == covered_dir or path.startswith(prefix):
            return True
    return False


def build_source_records() -> tuple[SourceRecord, ...]:
    records: list[SourceRecord] = []
    for source_file in sorted(SOURCE_ROOT.glob("source-*.md")):
        frontmatter = parse_frontmatter(source_file)
        raw_path_refs = normalize_refs(expand_source_refs(frontmatter.get("raw_path")))
        raw_variant_refs = normalize_refs(expand_source_refs(frontmatter.get("raw_variants")))
        pdf_refs = normalize_refs(expand_source_refs(frontmatter.get("pdf")))

        all_raw_refs = list(raw_path_refs)
        for ref in raw_variant_refs + pdf_refs:
            if ref not in all_raw_refs:
                all_raw_refs.append(ref)

        records.append(
            SourceRecord(
                source_file=source_file.relative_to(REPO_ROOT).as_posix(),
                frontmatter=frontmatter,
                raw_path_refs=raw_path_refs,
                raw_variant_refs=raw_variant_refs,
                pdf_refs=pdf_refs,
                all_raw_refs=tuple(all_raw_refs),
            )
        )

    return tuple(records)


def build_coverage_state(source_records: tuple[SourceRecord, ...]) -> CoverageState:
    covered_files: set[str] = set()
    covered_dirs: set[str] = set()

    for record in source_records:
        for ref in record.all_raw_refs:
            full_path = REPO_ROOT / ref
            if full_path.is_dir():
                covered_dirs.add(ref)
            else:
                covered_files.add(ref)

    raw_files = tuple(iter_raw_files())
    pending_files = tuple(
        path
        for path in raw_files
        if path not in covered_files and not is_covered_by_dir(path, covered_dirs)
    )

    return CoverageState(
        raw_files=raw_files,
        covered_files=frozenset(covered_files),
        covered_dirs=tuple(sorted(covered_dirs)),
        pending_files=pending_files,
    )


def is_book_candidate(path: str) -> bool:
    if not any(path == root or path.startswith(root + "/") for root in BOOK_INCLUDE_ROOTS):
        return False

    if any(path.startswith(prefix) for prefix in BOOK_EXCLUDE_PREFIXES):
        return False

    if Path(path).suffix.lower() not in BOOK_ALLOWED_SUFFIXES:
        return False

    name = Path(path).name
    if any(keyword in name for keyword in BOOK_EXCLUDE_KEYWORDS):
        return False

    return True


def first_existing_file_ref(refs: Iterable[str]) -> str | None:
    for ref in refs:
        if (REPO_ROOT / ref).is_file():
            return ref
    return None


def build_book_cache_paths(raw_path: str) -> tuple[Path, Path]:
    rel_path = Path(raw_path)
    cache_dir = PDF_CACHE_ROOT / rel_path.parent / rel_path.stem
    return cache_dir / "full.auto.md", cache_dir / "full.auto.json"


def load_json_file(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def is_book_cache_fresh(raw_path: str, markdown_path: Path, json_path: Path) -> bool:
    if not markdown_path.is_file() or not json_path.is_file():
        return False

    pdf_path = REPO_ROOT / raw_path
    if not pdf_path.is_file():
        return False

    payload = load_json_file(json_path)
    if payload is None:
        return False

    stat = pdf_path.stat()
    return (
        payload.get("source") == str(pdf_path.resolve())
        and payload.get("source_rel_path") == raw_path
        and payload.get("source_size") == stat.st_size
        and payload.get("source_mtime_ns") == stat.st_mtime_ns
        and payload.get("strategy") == "auto"
        and payload.get("page_from") == 1
        and payload.get("page_to") is None
    )


def build_book_queue_state(source_records: tuple[SourceRecord, ...]) -> BookQueueState:
    candidate_files = {path for path in iter_raw_files() if is_book_candidate(path)}

    alias_to_canonical: dict[str, str] = {}
    canonical_to_source: dict[str, SourceRecord] = {}

    for record in source_records:
        canonical = first_existing_file_ref(ref for ref in record.raw_path_refs if ref in candidate_files)
        if canonical is None:
            canonical = first_existing_file_ref(ref for ref in record.pdf_refs if ref in candidate_files)
        if canonical is None:
            continue

        canonical_to_source.setdefault(canonical, record)

        for alias in record.raw_variant_refs + record.pdf_refs:
            if alias in candidate_files and alias != canonical:
                alias_to_canonical[alias] = canonical

    canonical_paths: list[str] = []
    seen: set[str] = set()
    for path in sorted(candidate_files):
        canonical = alias_to_canonical.get(path, path)
        if canonical in seen:
            continue
        seen.add(canonical)
        canonical_paths.append(canonical)

    candidate_books: list[BookQueueItem] = []
    pending_books: list[BookQueueItem] = []

    for path in canonical_paths:
        record = canonical_to_source.get(path)
        source_file = record.source_file if record else None
        ingest_version = ""
        raw_review_version = ""
        if record:
            raw_value = record.frontmatter.get(BOOK_REINGEST_FIELD, "")
            if isinstance(raw_value, str):
                ingest_version = strip_quotes(raw_value)
            raw_review_value = record.frontmatter.get(RAW_REVIEW_FIELD, "")
            if isinstance(raw_review_value, str):
                raw_review_version = strip_quotes(raw_review_value)
        ingest_done = ingest_version == BOOK_REINGEST_VERSION
        raw_review_done = raw_review_version == RAW_REVIEW_VERSION
        done = ingest_done and raw_review_done
        cache_markdown_path, cache_json_path = build_book_cache_paths(path)
        cached = is_book_cache_fresh(path, cache_markdown_path, cache_json_path)
        item = BookQueueItem(
            raw_path=path,
            source_file=source_file,
            done=done,
            ingest_done=ingest_done,
            raw_review_done=raw_review_done,
            cached=cached,
            cache_markdown=cache_markdown_path.relative_to(REPO_ROOT).as_posix() if cached else None,
            cache_json=cache_json_path.relative_to(REPO_ROOT).as_posix() if cached else None,
        )
        candidate_books.append(item)
        if not done:
            pending_books.append(item)

    return BookQueueState(
        ingest_version=BOOK_REINGEST_VERSION,
        raw_review_version=RAW_REVIEW_VERSION,
        candidate_books=tuple(candidate_books),
        pending_books=tuple(pending_books),
    )


def print_status(state: CoverageState) -> int:
    covered_count = len(state.raw_files) - len(state.pending_files)
    print("Mode: raw-coverage")
    print(f"Raw files: {len(state.raw_files)}")
    print(f"Covered by source/: {covered_count}")
    print(f"Pending ingest: {len(state.pending_files)}")
    if state.pending_files:
        print()
        print("Next pending:")
        print(f"1. {state.pending_files[0]}")
    return 0


def print_list(state: CoverageState, limit: int | None) -> int:
    pending = state.pending_files if limit is None else state.pending_files[:limit]
    if not pending:
        print("No pending raw files.")
        return 0

    for index, path in enumerate(pending, start=1):
        print(f"{index}. {path}")
    return 0


def resolve_prompt_target(state: CoverageState, path: str | None) -> str | None:
    if path:
        normalized = normalize_repo_path(path)
        if not normalized:
            return None
        return normalized
    if state.pending_files:
        return state.pending_files[0]
    return None


def print_prompt(state: CoverageState, path: str | None) -> int:
    target = resolve_prompt_target(state, path)
    if not target:
        print("No pending raw files.")
        return 0

    print("请严格按 `workflow/Ingest工作流.md` 执行 ingest，只处理这一个 raw 文件：")
    print()
    print(f"`{target}`")
    print()
    print("要求：")
    print("1. 先阅读并理解这个文件，不要顺带处理第二个 raw 文件。")
    print("2. 在 `source/` 创建或完善对应的 `source-*.md`。")
    print("3. 只新增或更新与该文件直接相关的 `wiki/` 页面，并补齐双链。")
    print("4. 完成后自检本次 `source/` 与 `wiki/` 改动，不要批量扫描其他 `raw/` 文件。")
    print("5. 如果文件很大，仍然只围绕这一个文件产出最关键的来源页和高价值知识页。")
    print()
    print("完成后重新运行：`python3 scripts/ingest_queue.py status`")
    return 0


def print_next(state: CoverageState) -> int:
    if not state.pending_files:
        print("No pending raw files.")
        return 0
    print(state.pending_files[0])
    return 0


def filter_book_items(items: tuple[BookQueueItem, ...], prefix: str | None) -> tuple[BookQueueItem, ...]:
    if not prefix:
        return items
    normalized = normalize_repo_path(prefix)
    if not normalized:
        return ()
    return tuple(item for item in items if item.raw_path == normalized or item.raw_path.startswith(normalized.rstrip("/") + "/"))


def print_books_status(state: BookQueueState, prefix: str | None) -> int:
    candidates = filter_book_items(state.candidate_books, prefix)
    pending = tuple(item for item in candidates if not item.done)
    cached = tuple(item for item in candidates if item.cached)
    ready = tuple(item for item in candidates if item.cached and not item.done)
    ingest_completed = sum(1 for item in candidates if item.ingest_done)
    raw_review_completed = sum(1 for item in candidates if item.raw_review_done)
    completed = len(candidates) - len(pending)
    print("Mode: books-reingest")
    print(f"Target ingest_version: {state.ingest_version}")
    print(f"Target {RAW_REVIEW_FIELD}: {state.raw_review_version}")
    if prefix:
        print(f"Scope: {normalize_repo_path(prefix)}")
    print(f"Candidate books: {len(candidates)}")
    print(f"Cached full-text ready: {len(cached)}")
    print(f"Pending cache: {len(candidates) - len(cached)}")
    print(f"Completed ingest_version: {ingest_completed}")
    print(f"Completed {RAW_REVIEW_FIELD}: {raw_review_completed}")
    print(f"Completed fully: {completed}")
    print(f"Pending detailed re-ingest: {len(pending)}")
    print(f"Ready to ingest from cache: {len(ready)}")
    if ready:
        print()
        print("Next ready-to-ingest book:")
        print(f"1. {ready[0].raw_path}")
    elif pending:
        print()
        print("Next pending book (cache not ready yet):")
        print(f"1. {pending[0].raw_path}")
    return 0


def print_books_list(state: BookQueueState, limit: int | None, prefix: str | None) -> int:
    pending_all = filter_book_items(state.pending_books, prefix)
    pending = pending_all if limit is None else pending_all[:limit]
    if not pending:
        print("No pending books for this ingest version.")
        return 0

    for index, item in enumerate(pending, start=1):
        print(f"{index}. {item.raw_path}")
    return 0


def filter_uncached_books(state: BookQueueState, prefix: str | None) -> tuple[BookQueueItem, ...]:
    return tuple(item for item in filter_book_items(state.pending_books, prefix) if not item.cached)


def filter_ready_books(state: BookQueueState, prefix: str | None) -> tuple[BookQueueItem, ...]:
    return tuple(item for item in filter_book_items(state.pending_books, prefix) if item.cached)


def resolve_book_target(state: BookQueueState, path: str | None, prefix: str | None) -> str | None:
    if path:
        normalized = normalize_repo_path(path)
        if not normalized:
            return None
        return normalized
    pending = filter_book_items(state.pending_books, prefix)
    if pending:
        return pending[0].raw_path
    return None


def resolve_uncached_book_target(state: BookQueueState, path: str | None, prefix: str | None) -> str | None:
    if path:
        normalized = normalize_repo_path(path)
        if not normalized:
            return None
        item = find_book_item(state, normalized)
        if item and not item.cached and not item.done:
            return normalized
        return None
    pending = filter_uncached_books(state, prefix)
    if pending:
        return pending[0].raw_path
    return None


def resolve_ready_book_target(state: BookQueueState, path: str | None, prefix: str | None) -> str | None:
    if path:
        normalized = normalize_repo_path(path)
        if not normalized:
            return None
        item = find_book_item(state, normalized)
        if item and item.cached and not item.done:
            return normalized
        return None
    pending = filter_ready_books(state, prefix)
    if pending:
        return pending[0].raw_path
    return None


def find_book_source_file(state: BookQueueState, raw_path: str) -> str | None:
    normalized = normalize_repo_path(raw_path)
    if not normalized:
        return None
    for item in state.candidate_books:
        if item.raw_path == normalized:
            return item.source_file
    return None


def find_book_item(state: BookQueueState, raw_path: str) -> BookQueueItem | None:
    normalized = normalize_repo_path(raw_path)
    if not normalized:
        return None
    for item in state.candidate_books:
        if item.raw_path == normalized:
            return item
    return None


def print_books_cache_status(state: BookQueueState, prefix: str | None) -> int:
    candidates = filter_book_items(state.candidate_books, prefix)
    uncached = tuple(item for item in candidates if not item.cached)
    print("Mode: books-cache")
    if prefix:
        print(f"Scope: {normalize_repo_path(prefix)}")
    print(f"Candidate books: {len(candidates)}")
    print(f"Cached full-text ready: {len(candidates) - len(uncached)}")
    print(f"Pending cache: {len(uncached)}")
    if uncached:
        print()
        print("Next uncached book:")
        print(f"1. {uncached[0].raw_path}")
    return 0


def print_books_cache_list(state: BookQueueState, limit: int | None, prefix: str | None) -> int:
    pending_all = filter_uncached_books(state, prefix)
    pending = pending_all if limit is None else pending_all[:limit]
    if not pending:
        print("No pending books for cache.")
        return 0

    for index, item in enumerate(pending, start=1):
        print(f"{index}. {item.raw_path}")
    return 0


def print_books_cache_next(state: BookQueueState, prefix: str | None) -> int:
    pending = filter_uncached_books(state, prefix)
    if not pending:
        print("No pending books for cache.")
        return 0
    print(pending[0].raw_path)
    return 0


def print_books_cache_prompt(state: BookQueueState, path: str | None, prefix: str | None) -> int:
    target = resolve_uncached_book_target(state, path, prefix)
    if not target:
        print("No pending books for cache.")
        return 0

    print("请先只做这一本书的本地 PDF 全书缓存，不要开始 ingest：")
    print()
    print(f"`{target}`")
    print()
    print("执行命令：")
    print(
        f"`source .venv-pdf/bin/activate && python scripts/pdf_extract.py cache \"{target}\"`"
    )
    print()
    print("要求：")
    print("1. 只缓存这一本文件，不顺带处理第二本。")
    print("2. 默认使用 `full.auto` 作为标准缓存产物。")
    print("3. 导出成功后不要删除该书的 PDF 导出结果；它位于 `.derived/pdf_extract/`，会长期作为参考层保留。")
    print("4. 不要立刻扩展任务范围，重新取下一本或交给 ingest 阶段消费。")
    print()
    if prefix:
        normalized_prefix = normalize_repo_path(prefix)
        print(
            f"完成后重新运行：`python3 scripts/ingest_queue.py books-cache-status --prefix \"{normalized_prefix}\"`"
        )
    else:
        print("完成后重新运行：`python3 scripts/ingest_queue.py books-cache-status`")
    return 0


def print_books_ready_status(state: BookQueueState, prefix: str | None) -> int:
    candidates = filter_book_items(state.candidate_books, prefix)
    ready = tuple(item for item in candidates if item.cached and not item.done)
    done = tuple(item for item in candidates if item.done)
    blocked = tuple(item for item in candidates if not item.cached and not item.done)
    print("Mode: books-ready")
    print(f"Target ingest_version: {state.ingest_version}")
    print(f"Target {RAW_REVIEW_FIELD}: {state.raw_review_version}")
    if prefix:
        print(f"Scope: {normalize_repo_path(prefix)}")
    print(f"Candidate books: {len(candidates)}")
    print(f"Ready to ingest from cache: {len(ready)}")
    print(f"Blocked by missing cache: {len(blocked)}")
    print(f"Completed for this version: {len(done)}")
    if ready:
        print()
        print("Next ready book:")
        print(f"1. {ready[0].raw_path}")
    return 0


def print_books_ready_list(state: BookQueueState, limit: int | None, prefix: str | None) -> int:
    pending_all = filter_ready_books(state, prefix)
    pending = pending_all if limit is None else pending_all[:limit]
    if not pending:
        print("No cached books are ready for ingest.")
        return 0

    for index, item in enumerate(pending, start=1):
        print(f"{index}. {item.raw_path}")
    return 0


def print_books_ready_next(state: BookQueueState, prefix: str | None) -> int:
    pending = filter_ready_books(state, prefix)
    if not pending:
        print("No cached books are ready for ingest.")
        return 0
    print(pending[0].raw_path)
    return 0


def print_books_ready_prompt(state: BookQueueState, path: str | None, prefix: str | None) -> int:
    target = resolve_ready_book_target(state, path, prefix)
    if not target:
        print("No cached books are ready for ingest.")
        return 0

    item = find_book_item(state, target)
    source_file = item.source_file if item else None

    print("请严格按 `workflow/Ingest工作流.md` 重新执行书籍 ingest，只处理这一本已缓存的书：")
    print()
    print(f"`{target}`")
    if source_file:
        print()
        print(f"现有来源页：`{source_file}`")
    if item and item.cache_markdown and item.cache_json:
        print()
        print("优先使用本地缓存：")
        print(f"- markdown: `{item.cache_markdown}`")
        print(f"- json: `{item.cache_json}`")
    print()
    print("要求：")
    print("1. 这是 ingest 阶段，不是重新跑 OCR；优先消费已缓存文本。")
    print("2. 重新按书的结构阅读，至少覆盖目录、核心章节、关键模型、重要论据和可回写的知识点。")
    print("3. 优先完善现有 `source-*.md`，把浅层摘要升级成详细来源页，而不是只追加几行。")
    print(f"4. 全部完成后在来源页 frontmatter 写入 `{BOOK_REINGEST_FIELD}: {state.ingest_version}`。")
    print(f"5. 同时写入 `{RAW_REVIEW_FIELD}: {state.raw_review_version}`，表示相关 raw 文件已完成详细单文件 ingest 复核。")
    print("6. 完成后不要删除该书的 PDF 导出结果；主 agent 后续补充共享知识点页时仍可继续引用。")
    print("7. 只新增或更新与这本书直接相关的 `wiki/` 页面，并补齐双链。")
    print("8. 不要顺带处理第二本书；这轮结束后再重新取下一本已缓存图书。")
    print()
    if prefix:
        normalized_prefix = normalize_repo_path(prefix)
        print(
            f"完成后重新运行：`python3 scripts/ingest_queue.py books-ready-status --prefix \"{normalized_prefix}\"`"
        )
    else:
        print("完成后重新运行：`python3 scripts/ingest_queue.py books-ready-status`")
    return 0


def print_books_prompt(state: BookQueueState, path: str | None, prefix: str | None) -> int:
    target = resolve_book_target(state, path, prefix)
    if not target:
        print("No pending books for this ingest version.")
        return 0

    source_file = find_book_source_file(state, target)

    print("请严格按 `workflow/Ingest工作流.md` 重新执行书籍 ingest，只处理这一本书：")
    print()
    print(f"`{target}`")
    if source_file:
        print()
        print(f"现有来源页：`{source_file}`")
    print()
    print("要求：")
    print("1. 这是重跑，不是补漏；不要因为已有 `source` 页就做最小改动。")
    print("2. 如果本书已有本地缓存，优先使用缓存结果；否则先去做缓存再回来 ingest。")
    print("3. 重新按书的结构阅读，至少覆盖目录、核心章节、关键模型、重要论据和可回写的知识点。")
    print("4. 优先完善现有 `source-*.md`，把浅层摘要升级成详细来源页，而不是只追加几行。")
    print(f"5. 完成后在来源页 frontmatter 写入 `{BOOK_REINGEST_FIELD}: {state.ingest_version}`，作为本轮重跑版本标记。")
    print(f"6. 同时写入 `{RAW_REVIEW_FIELD}: {state.raw_review_version}`，表示相关 raw 文件已完成详细单文件 ingest 复核。")
    print("7. 完成后不要删除该书的 PDF 导出结果；后续复核和补充共享页时仍需参考。")
    print("8. 只新增或更新与这本书直接相关的 `wiki/` 页面，并补齐双链。")
    print("9. 不要顺带处理第二本书；这轮结束后再重新取下一本。")
    print()
    print("完成后重新运行：`python3 scripts/ingest_queue.py books-status`")
    return 0


def print_books_next(state: BookQueueState, prefix: str | None) -> int:
    pending = filter_book_items(state.pending_books, prefix)
    if not pending:
        print("No pending books for this ingest version.")
        return 0
    print(pending[0].raw_path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect raw/ coverage and emit one-file-at-a-time ingest queues."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show raw/source coverage summary.")

    list_parser = subparsers.add_parser("list", help="List pending raw files.")
    list_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only print the first N pending files.",
    )

    subparsers.add_parser("next", help="Print the next pending raw file.")

    prompt_parser = subparsers.add_parser(
        "prompt",
        help="Print a ready-to-use ingest prompt for the next pending raw file.",
    )
    prompt_parser.add_argument(
        "--path",
        help="Use a specific raw path instead of the next pending file.",
    )

    books_status_parser = subparsers.add_parser(
        "books-status", help="Show detailed re-ingest status for books."
    )
    books_status_parser.add_argument(
        "--prefix",
        help="Restrict the queue to a raw/ subdirectory prefix.",
    )

    books_cache_status_parser = subparsers.add_parser(
        "books-cache-status",
        help="Show local PDF cache status for books.",
    )
    books_cache_status_parser.add_argument(
        "--prefix",
        help="Restrict the queue to a raw/ subdirectory prefix.",
    )

    books_cache_list_parser = subparsers.add_parser(
        "books-cache-list",
        help="List books that still need full local PDF cache.",
    )
    books_cache_list_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only print the first N pending books.",
    )
    books_cache_list_parser.add_argument(
        "--prefix",
        help="Restrict the queue to a raw/ subdirectory prefix.",
    )

    books_cache_next_parser = subparsers.add_parser(
        "books-cache-next",
        help="Print the next book that still needs full local PDF cache.",
    )
    books_cache_next_parser.add_argument(
        "--prefix",
        help="Restrict the queue to a raw/ subdirectory prefix.",
    )

    books_cache_prompt_parser = subparsers.add_parser(
        "books-cache-prompt",
        help="Print a ready-to-use prompt for the next PDF cache task.",
    )
    books_cache_prompt_parser.add_argument(
        "--path",
        help="Use a specific raw path instead of the next uncached book.",
    )
    books_cache_prompt_parser.add_argument(
        "--prefix",
        help="Restrict the queue to a raw/ subdirectory prefix.",
    )

    books_list_parser = subparsers.add_parser(
        "books-list",
        help="List books that still need detailed re-ingest.",
    )
    books_list_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only print the first N pending books.",
    )
    books_list_parser.add_argument(
        "--prefix",
        help="Restrict the queue to a raw/ subdirectory prefix.",
    )

    books_next_parser = subparsers.add_parser(
        "books-next", help="Print the next book that needs detailed re-ingest."
    )
    books_next_parser.add_argument(
        "--prefix",
        help="Restrict the queue to a raw/ subdirectory prefix.",
    )

    books_prompt_parser = subparsers.add_parser(
        "books-prompt",
        help="Print a ready-to-use prompt for the next book re-ingest task.",
    )
    books_prompt_parser.add_argument(
        "--path",
        help="Use a specific raw path instead of the next pending book.",
    )
    books_prompt_parser.add_argument(
        "--prefix",
        help="Restrict the queue to a raw/ subdirectory prefix.",
    )

    books_ready_status_parser = subparsers.add_parser(
        "books-ready-status",
        help="Show books that are cached and ready for detailed re-ingest.",
    )
    books_ready_status_parser.add_argument(
        "--prefix",
        help="Restrict the queue to a raw/ subdirectory prefix.",
    )

    books_ready_list_parser = subparsers.add_parser(
        "books-ready-list",
        help="List cached books that are ready for detailed re-ingest.",
    )
    books_ready_list_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only print the first N ready books.",
    )
    books_ready_list_parser.add_argument(
        "--prefix",
        help="Restrict the queue to a raw/ subdirectory prefix.",
    )

    books_ready_next_parser = subparsers.add_parser(
        "books-ready-next",
        help="Print the next cached book that is ready for detailed re-ingest.",
    )
    books_ready_next_parser.add_argument(
        "--prefix",
        help="Restrict the queue to a raw/ subdirectory prefix.",
    )

    books_ready_prompt_parser = subparsers.add_parser(
        "books-ready-prompt",
        help="Print a ready-to-use prompt for the next ready-to-ingest book.",
    )
    books_ready_prompt_parser.add_argument(
        "--path",
        help="Use a specific raw path instead of the next ready book.",
    )
    books_ready_prompt_parser.add_argument(
        "--prefix",
        help="Restrict the queue to a raw/ subdirectory prefix.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    source_records = build_source_records()
    coverage_state = build_coverage_state(source_records)
    book_state = build_book_queue_state(source_records)

    if args.command == "status":
        return print_status(coverage_state)
    if args.command == "list":
        return print_list(coverage_state, args.limit)
    if args.command == "next":
        return print_next(coverage_state)
    if args.command == "prompt":
        return print_prompt(coverage_state, args.path)
    if args.command == "books-status":
        return print_books_status(book_state, args.prefix)
    if args.command == "books-cache-status":
        return print_books_cache_status(book_state, args.prefix)
    if args.command == "books-cache-list":
        return print_books_cache_list(book_state, args.limit, args.prefix)
    if args.command == "books-cache-next":
        return print_books_cache_next(book_state, args.prefix)
    if args.command == "books-cache-prompt":
        return print_books_cache_prompt(book_state, args.path, args.prefix)
    if args.command == "books-list":
        return print_books_list(book_state, args.limit, args.prefix)
    if args.command == "books-next":
        return print_books_next(book_state, args.prefix)
    if args.command == "books-prompt":
        return print_books_prompt(book_state, args.path, args.prefix)
    if args.command == "books-ready-status":
        return print_books_ready_status(book_state, args.prefix)
    if args.command == "books-ready-list":
        return print_books_ready_list(book_state, args.limit, args.prefix)
    if args.command == "books-ready-next":
        return print_books_ready_next(book_state, args.prefix)
    if args.command == "books-ready-prompt":
        return print_books_ready_prompt(book_state, args.path, args.prefix)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
