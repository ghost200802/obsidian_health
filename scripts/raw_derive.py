#!/usr/bin/env python3
"""Derive reusable .derived artifacts from raw files."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = REPO_ROOT / "raw"
DERIVED_ROOT = REPO_ROOT / ".derived"
MINERU_EXE = REPO_ROOT / ".venv-mineru" / "Scripts" / "mineru.exe"
MINERU_PYTHON = REPO_ROOT / ".venv-mineru" / "Scripts" / "python.exe"
PDF_SCRIPT = REPO_ROOT / "scripts" / "pdf_extract.py"
EPUB_SCRIPT = REPO_ROOT / "scripts" / "epub_extract.py"

PDF_EXTENSIONS = {".pdf"}
DOC_EXTENSIONS = {".docx"}
LEGACY_DOC_EXTENSIONS = {".doc"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def write_json_file(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json_file(path: Path | None) -> dict[str, object] | None:
    if path is None or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_progress(progress_path: Path | None, payload: dict[str, object]) -> None:
    if progress_path is None:
        return
    write_json_file(progress_path, {"updated_at": now_iso(), **payload})


def ensure_raw_path(source_path: Path) -> Path:
    resolved = source_path.expanduser().resolve()
    try:
        resolved.relative_to(RAW_ROOT)
    except ValueError as exc:
        raise ValueError(f"source must be under raw/: {resolved}") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"source file not found: {resolved}")
    return resolved


def repo_relative_without_suffix(source_path: Path) -> Path:
    repo_relative = source_path.relative_to(REPO_ROOT)
    return repo_relative.parent / repo_relative.stem


def derive_kind(source_path: Path) -> str:
    suffix = source_path.suffix.lower()
    if suffix in PDF_EXTENSIONS:
        return "pdf_extract"
    if suffix in DOC_EXTENSIONS:
        return "doc_extract"
    if suffix in LEGACY_DOC_EXTENSIONS:
        return "legacy_doc_extract"
    if suffix in IMAGE_EXTENSIONS:
        return "image_extract"
    if suffix == ".epub":
        return "epub_extract"
    return "unsupported"


def target_dir_for(source_path: Path) -> Path:
    return DERIVED_ROOT / derive_kind(source_path) / repo_relative_without_suffix(source_path)


def exception_path_for(source_path: Path) -> Path:
    return DERIVED_ROOT / "conversion_exceptions" / f"{repo_relative_without_suffix(source_path)}.md"


def source_stat_fields(source_path: Path) -> dict[str, object]:
    stat = source_path.stat()
    return {
        "source": str(source_path),
        "source_rel_path": str(source_path.relative_to(REPO_ROOT)),
        "source_size": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
    }


def manifest_is_fresh(manifest_path: Path, source_path: Path) -> bool:
    if not manifest_path.is_file():
        return False
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    if payload.get("status") != "success":
        return False

    source_info = source_stat_fields(source_path)
    for key, value in source_info.items():
        if payload.get(key) != value:
            return False

    artifacts = payload.get("artifacts", {})
    markdown = artifacts.get("markdown")
    json_path = artifacts.get("json")
    if not markdown or not json_path:
        return False
    return Path(markdown).is_file() and Path(json_path).is_file()


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_exception(source_path: Path, message: str) -> Path:
    output_path = exception_path_for(source_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(
        [
            f"# Conversion Exception",
            "",
            f"- generated_at: {now_iso()}",
            f"- source: {source_path}",
            f"- source_rel_path: {source_path.relative_to(REPO_ROOT)}",
            "",
            "## Message",
            "",
            message.strip(),
            "",
        ]
    )
    output_path.write_text(content, encoding="utf-8")
    return output_path


def clear_exception(source_path: Path) -> None:
    output_path = exception_path_for(source_path)
    if output_path.exists():
        output_path.unlink()


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def run_pdf(
    source_path: Path,
    force: bool,
    progress_path: Path | None = None,
    progress_every_pages: int = 10,
    files_total: int | None = None,
    current_file_index: int | None = None,
    files_completed: int | None = None,
) -> dict[str, object]:
    command = [
        str(MINERU_PYTHON),
        str(PDF_SCRIPT),
        "cache",
        str(source_path),
        "--json",
    ]
    if force:
        command.append("--force")
    if progress_path is not None:
        command += [
            "--progress-path",
            str(progress_path),
            "--progress-every-pages",
            str(progress_every_pages),
        ]
    if files_total is not None:
        command += ["--files-total", str(files_total)]
    if current_file_index is not None:
        command += ["--current-file-index", str(current_file_index)]
    if files_completed is not None:
        command += ["--files-completed", str(files_completed)]

    result = run_command(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "pdf_extract failed")

    payload = json.loads(result.stdout)
    return {
        "status": payload["cache_status"],
        "target_dir": str(target_dir_for(source_path)),
        "markdown": str(target_dir_for(source_path) / "full.md"),
        "json": str(target_dir_for(source_path) / "full.json"),
        "manifest": str(target_dir_for(source_path) / "manifest.json"),
    }


def choose_best_json(candidates: list[Path]) -> Path:
    priorities = [
        "_content_list_v2.json",
        "_content_list.json",
    ]
    for suffix in priorities:
        for candidate in candidates:
            if candidate.name.endswith(suffix):
                return candidate
    filtered = [
        candidate
        for candidate in candidates
        if not candidate.name.endswith("_model.json") and not candidate.name.endswith("_middle.json")
    ]
    if filtered:
        return sorted(filtered, key=lambda item: (len(item.parts), len(item.name)))[0]
    return sorted(candidates, key=lambda item: (len(item.parts), len(item.name)))[0]


def choose_best_markdown(candidates: list[Path]) -> Path:
    office_candidates = [candidate for candidate in candidates if "office" in {part.lower() for part in candidate.parts}]
    pool = office_candidates or candidates
    return sorted(pool, key=lambda item: (len(item.parts), len(item.name)))[0]


def build_mineru_manifest(source_path: Path, target_dir: Path, asset_root: Path) -> dict[str, object]:
    return {
        **source_stat_fields(source_path),
        "source_type": source_path.suffix.lower().lstrip("."),
        "generated_at": now_iso(),
        "status": "success",
        "tool": {
            "name": "mineru",
            "binary": str(MINERU_EXE),
            "backend": "pipeline",
            "mode": "auto",
            "language": "ch",
        },
        "artifacts": {
            "markdown": str(target_dir / "full.md"),
            "json": str(target_dir / "full.json"),
            "assets": str(target_dir / "assets"),
            "native_output": str(asset_root),
        },
    }


def run_mineru(source_path: Path, force: bool) -> dict[str, object]:
    target_dir = target_dir_for(source_path)
    manifest_path = target_dir / "manifest.json"
    if not force and manifest_is_fresh(manifest_path, source_path):
        return {
            "status": "fresh",
            "target_dir": str(target_dir),
            "markdown": str(target_dir / "full.md"),
            "json": str(target_dir / "full.json"),
            "manifest": str(manifest_path),
        }

    asset_root = target_dir / "assets" / "mineru_raw"
    target_dir.mkdir(parents=True, exist_ok=True)
    reset_dir(asset_root)

    command = [
        str(MINERU_EXE),
        "-p",
        str(source_path),
        "-o",
        str(asset_root),
        "-b",
        "pipeline",
        "-m",
        "auto",
        "-l",
        "ch",
    ]
    result = run_command(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "mineru failed")

    markdown_candidates = list(asset_root.rglob("*.md"))
    json_candidates = list(asset_root.rglob("*.json"))
    if not markdown_candidates:
        raise RuntimeError("MinerU succeeded but no markdown output was found")
    if not json_candidates:
        raise RuntimeError("MinerU succeeded but no json output was found")

    best_markdown = choose_best_markdown(markdown_candidates)
    best_json = choose_best_json(json_candidates)
    shutil.copyfile(best_markdown, target_dir / "full.md")
    shutil.copyfile(best_json, target_dir / "full.json")

    manifest = build_mineru_manifest(source_path, target_dir, asset_root)
    manifest["tool"]["stdout_tail"] = result.stdout.strip()[-1000:]
    if result.stderr.strip():
        manifest["tool"]["stderr_tail"] = result.stderr.strip()[-1000:]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "written",
        "target_dir": str(target_dir),
        "markdown": str(target_dir / "full.md"),
        "json": str(target_dir / "full.json"),
        "manifest": str(manifest_path),
    }


def run_epub(source_path: Path, force: bool) -> dict[str, object]:
    target_dir = target_dir_for(source_path)
    manifest_path = target_dir / "manifest.json"
    if not force and manifest_is_fresh(manifest_path, source_path):
        return {
            "status": "fresh",
            "target_dir": str(target_dir),
            "markdown": str(target_dir / "full.md"),
            "json": str(target_dir / "full.json"),
            "manifest": str(manifest_path),
        }

    command = [
        str(MINERU_PYTHON),
        str(EPUB_SCRIPT),
        str(source_path),
        "--cache-root",
        str(DERIVED_ROOT / "epub_extract"),
        "--json",
    ]
    if force:
        command.append("--force")
    result = run_command(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "epub_extract failed")

    payload = json.loads(result.stdout)
    return {
        "status": payload["cache_status"],
        "target_dir": str(target_dir),
        "markdown": str(target_dir / "full.md"),
        "json": str(target_dir / "full.json"),
        "manifest": str(manifest_path),
    }


def derive_one(
    source_arg: str,
    force: bool,
    progress_path: Path | None = None,
    progress_every_pages: int = 10,
    files_total: int | None = None,
    current_file_index: int | None = None,
    files_completed: int | None = None,
) -> dict[str, object]:
    source_path = ensure_raw_path(Path(source_arg))
    kind = derive_kind(source_path)

    if kind == "pdf_extract":
        result = {
            "source": str(source_path),
            "kind": kind,
            **run_pdf(
                source_path,
                force,
                progress_path=progress_path,
                progress_every_pages=progress_every_pages,
                files_total=files_total,
                current_file_index=current_file_index,
                files_completed=files_completed,
            ),
        }
        clear_exception(source_path)
        return result
    if kind in {"doc_extract", "image_extract"}:
        result = {"source": str(source_path), "kind": kind, **run_mineru(source_path, force)}
        clear_exception(source_path)
        return result
    if kind == "epub_extract":
        result = {"source": str(source_path), "kind": kind, **run_epub(source_path, force)}
        clear_exception(source_path)
        return result

    if kind == "legacy_doc_extract":
        message = "DOC extraction needs a stable DOC -> DOCX conversion step before MinerU."
    else:
        message = f"Unsupported file type: {source_path.suffix.lower()}"

    exception_path = write_exception(source_path, message)
    return {
        "source": str(source_path),
        "kind": kind,
        "status": "failed",
        "exception": str(exception_path),
        "message": message,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Derive persistent .derived artifacts from raw files.")
    parser.add_argument("paths", nargs="+", help="One or more raw file paths.")
    parser.add_argument("--force", action="store_true", help="Regenerate even when the manifest is fresh.")
    parser.add_argument("--json", action="store_true", help="Emit JSON results.")
    parser.add_argument("--progress-path", help="Optional JSON file to receive compact job progress updates.")
    parser.add_argument("--progress-every-pages", type=int, default=10, help="Write PDF progress every N processed pages.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    progress_path = Path(args.progress_path).expanduser().resolve() if args.progress_path else None

    if not MINERU_PYTHON.is_file():
        parser.error(f"Missing Python runtime: {MINERU_PYTHON}")
    if not MINERU_EXE.is_file():
        parser.error(f"Missing MinerU binary: {MINERU_EXE}")

    results = []
    exit_code = 0
    total_files = len(args.paths)
    failed_files = 0
    files_completed = 0

    write_progress(
        progress_path,
        {
            "status": "running",
            "phase": "queued",
            "files_total": total_files,
            "files_completed": 0,
            "failed_files": 0,
            "current_file_index": None,
            "current_source": None,
            "current_kind": None,
        },
    )

    for index, source_arg in enumerate(args.paths, start=1):
        source_path = Path(source_arg).expanduser().resolve()
        current_kind = derive_kind(source_path) if source_path.exists() else "unknown"
        write_progress(
            progress_path,
            {
                "status": "running",
                "phase": "starting_file",
                "files_total": total_files,
                "files_completed": files_completed,
                "failed_files": failed_files,
                "current_file_index": index,
                "current_source": str(source_path),
                "current_kind": current_kind,
            },
        )
        try:
            result = derive_one(
                source_arg,
                force=args.force,
                progress_path=progress_path,
                progress_every_pages=args.progress_every_pages,
                files_total=total_files,
                current_file_index=index,
                files_completed=files_completed,
            )
        except Exception as exc:
            if source_path.is_file():
                exception_path = write_exception(source_path, str(exc))
                result = {
                    "source": str(source_path),
                    "kind": derive_kind(source_path),
                    "status": "failed",
                    "exception": str(exception_path),
                    "message": str(exc),
                }
            else:
                result = {
                    "source": str(source_path),
                    "kind": "unknown",
                    "status": "failed",
                    "message": str(exc),
                }
            exit_code = 1
        if result.get("status") == "failed":
            exit_code = 1
            failed_files += 1
        results.append(result)
        files_completed += 1
        existing_progress = read_json_file(progress_path)
        write_progress(
            progress_path,
            {
                "status": "running",
                "phase": "file_finished",
                "files_total": total_files,
                "files_completed": files_completed,
                "failed_files": failed_files,
                "current_file_index": index,
                "current_source": result.get("source"),
                "current_kind": result.get("kind"),
                "current_result_status": result.get("status"),
                "total_pages": existing_progress.get("total_pages") if existing_progress else None,
                "processed_pages": existing_progress.get("processed_pages") if existing_progress else None,
                "current_page": existing_progress.get("current_page") if existing_progress else None,
                "method": existing_progress.get("method") if existing_progress else None,
            },
        )

    final_progress = read_json_file(progress_path)
    write_progress(
        progress_path,
        {
            "status": "finished" if exit_code == 0 else "failed",
            "phase": "job_done",
            "files_total": total_files,
            "files_completed": files_completed,
            "failed_files": failed_files,
            "current_file_index": total_files if total_files else None,
            "current_source": results[-1]["source"] if results else None,
            "current_kind": results[-1]["kind"] if results else None,
            "total_pages": final_progress.get("total_pages") if final_progress else None,
            "processed_pages": final_progress.get("processed_pages") if final_progress else None,
            "current_page": final_progress.get("current_page") if final_progress else None,
            "method": final_progress.get("method") if final_progress else None,
        },
    )

    if args.json:
        sys.stdout.write(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    else:
        for result in results:
            sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
