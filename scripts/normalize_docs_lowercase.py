\
#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from pathlib import Path

REPO_ROOT = Path.cwd()

MARKDOWN_EXTENSIONS = {".md", ".markdown"}
EXCLUDED_DIRS = {
    ".git",
    ".github",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
}

def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.parts)

def collect_markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if is_excluded(path.relative_to(root)):
            continue
        if path.suffix.lower() in MARKDOWN_EXTENSIONS:
            files.append(path)
    return sorted(files)

def build_rename_plan(files: list[Path], root: Path) -> dict[Path, Path]:
    plan: dict[Path, Path] = {}
    reserved_targets: dict[Path, Path] = {}

    for src in files:
        rel = src.relative_to(root)
        target_rel = Path(*(part.lower() for part in rel.parts))
        dst = root / target_rel

        if src == dst:
            continue

        if dst in reserved_targets and reserved_targets[dst] != src:
            raise RuntimeError(
                f"Rename collision detected: '{src}' and '{reserved_targets[dst]}' "
                f"would both become '{dst}'. Resolve manually."
            )

        reserved_targets[dst] = src
        plan[src] = dst

    return plan

def apply_renames(plan: dict[Path, Path]) -> None:
    if not plan:
        return

    temp_map: dict[Path, Path] = {}

    # Phase 1: move to temporary names to avoid case-only rename problems
    for i, (src, dst) in enumerate(sorted(plan.items(), key=lambda item: len(item[0].parts), reverse=True)):
        tmp = src.with_name(src.name + f".tmp_lowercase_{i}")
        src.rename(tmp)
        temp_map[tmp] = dst

    # Phase 2: move temp files to final names
    for tmp, dst in temp_map.items():
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp.rename(dst)

def normalize_link_target(target: str) -> str:
    stripped = target.strip()
    if not stripped:
        return target

    # Leave anchors, mailto, http(s), tel, and other schemes untouched except for .md path case
    if stripped.startswith("#"):
        return target
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", stripped):
        return target

    # Split anchor
    if "#" in stripped:
        path_part, anchor = stripped.split("#", 1)
        anchor_part = "#" + anchor
    else:
        path_part, anchor_part = stripped, ""

    # Split query
    if "?" in path_part:
        file_part, query = path_part.split("?", 1)
        query_part = "?" + query
    else:
        file_part, query_part = path_part, ""

    if file_part.lower().endswith(".md") or file_part.lower().endswith(".markdown"):
        return file_part.lower() + query_part + anchor_part

    return target

def update_markdown_links(text: str) -> str:
    # Standard markdown links and images
    def replace_inline(match: re.Match[str]) -> str:
        label = match.group(1)
        target = match.group(2)
        normalized = normalize_link_target(target)
        return f"]({normalized})"

    text = re.sub(r"\]\(([^)]+)\)", replace_inline, text)

    # Reference-style link definitions: [id]: path/to/file.md
    def replace_reference(match: re.Match[str]) -> str:
        prefix = match.group(1)
        target = match.group(2)
        suffix = match.group(3) or ""
        normalized = normalize_link_target(target)
        return f"{prefix}{normalized}{suffix}"

    text = re.sub(r"^(\[[^\]]+\]:\s*)(\S+)(.*)$", replace_reference, text, flags=re.MULTILINE)

    return text

def update_file_contents(files: list[Path]) -> None:
    for path in files:
        original = path.read_text(encoding="utf-8")
        updated = update_markdown_links(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")

def main() -> None:
    markdown_files = collect_markdown_files(REPO_ROOT)
    rename_plan = build_rename_plan(markdown_files, REPO_ROOT)
    apply_renames(rename_plan)

    # Re-scan because file paths may have changed after rename
    markdown_files = collect_markdown_files(REPO_ROOT)
    update_file_contents(markdown_files)

    print("Markdown normalization complete.")
    if rename_plan:
        print("Renamed files:")
        for src, dst in sorted(rename_plan.items()):
            print(f" - {src.relative_to(REPO_ROOT)} -> {dst.relative_to(REPO_ROOT)}")
    else:
        print("No filename changes were required.")

if __name__ == "__main__":
    main()
