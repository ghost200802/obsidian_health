#!/usr/bin/env python3
"""Hybrid PDF extractor for text PDFs and scanned PDFs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pypdfium2 as pdfium
from pypdf import PdfReader
from rapidocr_onnxruntime import RapidOCR


DEFAULT_MIN_TEXT_CHARS = 80
DEFAULT_OCR_SCALE = 2.0
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_ROOT = REPO_ROOT / ".derived" / "pdf_extract"


@dataclass
class PageExtraction:
    page_number: int
    method: str
    text: str
    text_chars: int


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def build_page_indices(page_count: int, page_from: int, page_to: int | None) -> list[int]:
    start = max(1, page_from)
    end = page_count if page_to is None else min(page_count, page_to)
    if start > end:
        return []
    return list(range(start - 1, end))


def extract_text_layer(page) -> str:
    try:
        text = page.extract_text() or ""
    except Exception:
        return ""
    return normalize_text(text)


def render_page_for_ocr(document: pdfium.PdfDocument, page_index: int, scale: float) -> np.ndarray:
    page = document[page_index]
    bitmap = page.render(scale=scale)
    image = bitmap.to_pil()
    return np.array(image)


def ocr_page(engine: RapidOCR, image: np.ndarray) -> str:
    result, _ = engine(image)
    if not result:
        return ""
    return normalize_text("\n".join(item[1] for item in result))


def inspect_document(
    pdf_path: Path,
    sample_pages: int,
) -> dict[str, object]:
    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)
    indices = build_page_indices(page_count, 1, min(sample_pages, page_count))
    text_lengths = []
    for idx in indices:
        text = extract_text_layer(reader.pages[idx])
        text_lengths.append(
            {
                "page": idx + 1,
                "text_chars": len(text),
                "has_text_layer": bool(text),
            }
        )

    text_pages = sum(1 for item in text_lengths if item["has_text_layer"])
    sample_count = len(text_lengths)
    if sample_count == 0:
        mode = "empty"
    elif text_pages == sample_count:
        mode = "text"
    elif text_pages == 0:
        mode = "scan"
    else:
        mode = "hybrid"

    return {
        "path": str(pdf_path),
        "pages": page_count,
        "sample_pages": sample_count,
        "sample_mode": mode,
        "sample": text_lengths,
    }


def extract_document(
    pdf_path: Path,
    strategy: str,
    page_from: int,
    page_to: int | None,
    min_text_chars: int,
    ocr_scale: float,
) -> tuple[list[PageExtraction], dict[str, int]]:
    reader = PdfReader(str(pdf_path))
    renderer = pdfium.PdfDocument(str(pdf_path))
    page_indices = build_page_indices(len(reader.pages), page_from, page_to)
    engine = RapidOCR()

    results: list[PageExtraction] = []
    stats = {"text": 0, "ocr": 0, "empty": 0}

    for page_index in page_indices:
        text_layer = extract_text_layer(reader.pages[page_index])
        use_text = strategy == "text"
        use_ocr = strategy == "ocr"

        if strategy == "auto":
            use_text = len(text_layer) >= min_text_chars
            use_ocr = not use_text
        elif strategy == "hybrid":
            use_text = bool(text_layer)
            use_ocr = not use_text

        if use_text:
            text = text_layer
            method = "text"
        else:
            image = render_page_for_ocr(renderer, page_index, ocr_scale)
            text = ocr_page(engine, image)
            method = "ocr"

        if not text and strategy in {"auto", "hybrid"} and method == "text":
            image = render_page_for_ocr(renderer, page_index, ocr_scale)
            text = ocr_page(engine, image)
            method = "ocr"

        text_chars = len(text)
        if text_chars == 0:
            stats["empty"] += 1
        else:
            stats[method] += 1

        results.append(
            PageExtraction(
                page_number=page_index + 1,
                method=method,
                text=text,
                text_chars=text_chars,
            )
        )

    return results, stats


def format_text_output(
    pdf_path: Path,
    pages: Iterable[PageExtraction],
    stats: dict[str, int],
) -> str:
    page_list = list(pages)
    lines = [
        f"# Extracted PDF",
        f"",
        f"- source: {pdf_path}",
        f"- pages_extracted: {len(page_list)}",
        f"- text_pages: {stats['text']}",
        f"- ocr_pages: {stats['ocr']}",
        f"- empty_pages: {stats['empty']}",
        "",
    ]
    for page in page_list:
        lines.append(f"## Page {page.page_number} [{page.method}]")
        lines.append("")
        lines.append(page.text if page.text else "[NO TEXT]")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def write_output(content: str, output_path: Path | None) -> None:
    if output_path is None:
        sys.stdout.write(content)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def load_json_output(output_path: Path) -> dict[str, object] | None:
    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_cache_key(pdf_path: Path) -> Path:
    try:
        return pdf_path.relative_to(REPO_ROOT)
    except ValueError:
        digest = hashlib.sha1(str(pdf_path).encode("utf-8")).hexdigest()[:12]
        return Path("external") / f"{pdf_path.stem}-{digest}{pdf_path.suffix}"


def build_range_tag(page_from: int, page_to: int | None) -> str:
    if page_from == 1 and page_to is None:
        return "full"
    if page_to is None:
        return f"p{page_from:04d}-end"
    return f"p{page_from:04d}-p{page_to:04d}"


def build_cache_paths(
    pdf_path: Path,
    cache_root: Path,
    strategy: str,
    page_from: int,
    page_to: int | None,
) -> tuple[Path, Path]:
    cache_key = build_cache_key(pdf_path)
    range_tag = build_range_tag(page_from, page_to)
    variant = f"{range_tag}.{strategy}"
    cache_dir = cache_root / cache_key.parent / cache_key.stem
    markdown_path = cache_dir / f"{variant}.md"
    json_path = cache_dir / f"{variant}.json"
    return markdown_path, json_path


def build_json_payload(
    pdf_path: Path,
    pages: Iterable[PageExtraction],
    stats: dict[str, int],
    strategy: str,
    page_from: int,
    page_to: int | None,
    min_text_chars: int,
    ocr_scale: float,
    markdown_path: Path | None = None,
    json_path: Path | None = None,
) -> dict[str, object]:
    stat = pdf_path.stat()
    try:
        source_rel_path = str(pdf_path.relative_to(REPO_ROOT))
    except ValueError:
        source_rel_path = None

    page_list = list(pages)
    return {
        "source": str(pdf_path),
        "source_rel_path": source_rel_path,
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "strategy": strategy,
        "page_from": page_from,
        "page_to": page_to,
        "min_text_chars": min_text_chars,
        "ocr_scale": ocr_scale,
        "pages_extracted": len(page_list),
        "stats": stats,
        "cache_markdown": str(markdown_path) if markdown_path else None,
        "cache_json": str(json_path) if json_path else None,
        "pages": [
            {
                "page_number": page.page_number,
                "method": page.method,
                "text_chars": page.text_chars,
                "text": page.text,
            }
            for page in page_list
        ],
    }


def cache_is_fresh(
    payload: dict[str, object] | None,
    pdf_path: Path,
    strategy: str,
    page_from: int,
    page_to: int | None,
    min_text_chars: int,
    ocr_scale: float,
    markdown_path: Path,
) -> bool:
    if not payload or not markdown_path.is_file():
        return False

    stat = pdf_path.stat()
    try:
        cached_ocr_scale = float(payload.get("ocr_scale", -1))
    except (TypeError, ValueError):
        return False

    return (
        payload.get("source") == str(pdf_path)
        and payload.get("source_size") == stat.st_size
        and payload.get("source_mtime_ns") == stat.st_mtime_ns
        and payload.get("strategy") == strategy
        and payload.get("page_from") == page_from
        and payload.get("page_to") == page_to
        and payload.get("min_text_chars") == min_text_chars
        and abs(cached_ocr_scale - ocr_scale) < 1e-9
    )


def cache_document(
    pdf_path: Path,
    cache_root: Path,
    strategy: str,
    page_from: int,
    page_to: int | None,
    min_text_chars: int,
    ocr_scale: float,
    force: bool,
) -> tuple[dict[str, object], Path, Path, str]:
    markdown_path, json_path = build_cache_paths(
        pdf_path=pdf_path,
        cache_root=cache_root,
        strategy=strategy,
        page_from=page_from,
        page_to=page_to,
    )
    if not force and json_path.is_file():
        payload = load_json_output(json_path)
        if cache_is_fresh(
            payload=payload,
            pdf_path=pdf_path,
            strategy=strategy,
            page_from=page_from,
            page_to=page_to,
            min_text_chars=min_text_chars,
            ocr_scale=ocr_scale,
            markdown_path=markdown_path,
        ):
            return payload, markdown_path, json_path, "fresh"

    pages, stats = extract_document(
        pdf_path=pdf_path,
        strategy=strategy,
        page_from=page_from,
        page_to=page_to,
        min_text_chars=min_text_chars,
        ocr_scale=ocr_scale,
    )
    markdown_content = format_text_output(pdf_path, pages, stats)
    payload = build_json_payload(
        pdf_path=pdf_path,
        pages=pages,
        stats=stats,
        strategy=strategy,
        page_from=page_from,
        page_to=page_to,
        min_text_chars=min_text_chars,
        ocr_scale=ocr_scale,
        markdown_path=markdown_path,
        json_path=json_path,
    )
    write_output(markdown_content, markdown_path)
    write_output(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", json_path)
    return payload, markdown_path, json_path, "written"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract text from PDFs with text-layer first and OCR fallback."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect whether a PDF is text, scan, or hybrid.")
    inspect_parser.add_argument("pdf_path", help="Path to the PDF file.")
    inspect_parser.add_argument("--sample-pages", type=int, default=8, help="How many leading pages to sample.")
    inspect_parser.add_argument("--json", action="store_true", help="Emit JSON.")

    extract_parser = subparsers.add_parser("extract", help="Extract text from a PDF.")
    extract_parser.add_argument("pdf_path", help="Path to the PDF file.")
    extract_parser.add_argument(
        "--strategy",
        choices=("auto", "text", "ocr", "hybrid"),
        default="auto",
        help="Extraction strategy. 'auto' uses text layer when sufficiently dense, otherwise OCR.",
    )
    extract_parser.add_argument("--page-from", type=int, default=1, help="1-based start page.")
    extract_parser.add_argument("--page-to", type=int, default=None, help="1-based end page.")
    extract_parser.add_argument(
        "--min-text-chars",
        type=int,
        default=DEFAULT_MIN_TEXT_CHARS,
        help="Minimum extracted text chars before a page counts as text-layer usable in auto mode.",
    )
    extract_parser.add_argument(
        "--ocr-scale",
        type=float,
        default=DEFAULT_OCR_SCALE,
        help="Rasterization scale for OCR pages.",
    )
    extract_parser.add_argument("--output", help="Optional output file path.")
    extract_parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown-like text.")

    cache_parser = subparsers.add_parser(
        "cache",
        help="Extract text and persist reusable markdown/json output under .derived/pdf_extract.",
    )
    cache_parser.add_argument("pdf_path", help="Path to the PDF file.")
    cache_parser.add_argument(
        "--strategy",
        choices=("auto", "text", "ocr", "hybrid"),
        default="auto",
        help="Extraction strategy. 'auto' uses text layer when sufficiently dense, otherwise OCR.",
    )
    cache_parser.add_argument("--page-from", type=int, default=1, help="1-based start page.")
    cache_parser.add_argument("--page-to", type=int, default=None, help="1-based end page.")
    cache_parser.add_argument(
        "--min-text-chars",
        type=int,
        default=DEFAULT_MIN_TEXT_CHARS,
        help="Minimum extracted text chars before a page counts as text-layer usable in auto mode.",
    )
    cache_parser.add_argument(
        "--ocr-scale",
        type=float,
        default=DEFAULT_OCR_SCALE,
        help="Rasterization scale for OCR pages.",
    )
    cache_parser.add_argument(
        "--cache-root",
        default=str(DEFAULT_CACHE_ROOT),
        help="Root directory for persistent extraction cache.",
    )
    cache_parser.add_argument("--force", action="store_true", help="Ignore fresh cache and re-extract.")
    cache_parser.add_argument("--json", action="store_true", help="Emit JSON summary.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    pdf_path = Path(args.pdf_path).expanduser().resolve()
    if not pdf_path.is_file():
        parser.error(f"PDF not found: {pdf_path}")

    if args.command == "inspect":
        payload = inspect_document(pdf_path, args.sample_pages)
        if args.json:
            sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        else:
            sys.stdout.write(
                "\n".join(
                    [
                        f"path: {payload['path']}",
                        f"pages: {payload['pages']}",
                        f"sample_mode: {payload['sample_mode']}",
                        "sample:",
                        *[
                            f"  - page {item['page']}: text_chars={item['text_chars']} has_text_layer={item['has_text_layer']}"
                            for item in payload["sample"]
                        ],
                    ]
                )
                + "\n"
            )
        return 0

    if args.command == "extract":
        pages, stats = extract_document(
            pdf_path=pdf_path,
            strategy=args.strategy,
            page_from=args.page_from,
            page_to=args.page_to,
            min_text_chars=args.min_text_chars,
            ocr_scale=args.ocr_scale,
        )
        if args.json:
            payload = build_json_payload(
                pdf_path=pdf_path,
                pages=pages,
                stats=stats,
                strategy=args.strategy,
                page_from=args.page_from,
                page_to=args.page_to,
                min_text_chars=args.min_text_chars,
                ocr_scale=args.ocr_scale,
            )
            content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        else:
            content = format_text_output(pdf_path, pages, stats)
        output_path = Path(args.output).expanduser().resolve() if args.output else None
        write_output(content, output_path)
        return 0

    if args.command == "cache":
        cache_root = Path(args.cache_root).expanduser().resolve()
        payload, markdown_path, json_path, cache_status = cache_document(
            pdf_path=pdf_path,
            cache_root=cache_root,
            strategy=args.strategy,
            page_from=args.page_from,
            page_to=args.page_to,
            min_text_chars=args.min_text_chars,
            ocr_scale=args.ocr_scale,
            force=args.force,
        )
        if args.json:
            sys.stdout.write(
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
                + "\n"
            )
        else:
            stats = payload["stats"]
            sys.stdout.write(
                "\n".join(
                    [
                        f"source: {payload['source']}",
                        f"cache_status: {cache_status}",
                        f"markdown: {markdown_path}",
                        f"json: {json_path}",
                        f"pages_extracted: {payload['pages_extracted']}",
                        f"text_pages: {stats['text']}",
                        f"ocr_pages: {stats['ocr']}",
                        f"empty_pages: {stats['empty']}",
                    ]
                )
                + "\n"
            )
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
