#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.8 / 프로젝트-정리
"""
프로젝트-정리.py — 프로젝트 폴더의 정리 후보를 보고하고, 승인 시 _archive 로 보관 이동한다.

원칙:
  - 삭제하지 않는다. 기본은 보고서(dry-run)만 만든다.
  - --apply 를 줘도 _archive/agentis-cleanup-YYYY-MM-DDTHHMMSS/ 로 이동만 한다.
  - .git, agentis, .clinerules, _archive 는 기본 제외한다.
  - 중복 파일은 같은 SHA-256 그룹에서 하나(보존본)를 남기고 나머지만 후보로 잡는다.
  - 임시/생성물 후보: __pycache__, .DS_Store, *.pyc, *.tmp, *.bak, *.orig, node_modules, dist, build, .pytest_cache 등.

사용:
  python agentis/workflows/프로젝트-정리.py                  # 보고서만
  python agentis/workflows/프로젝트-정리.py --apply          # _archive 로 이동
  python agentis/workflows/프로젝트-정리.py --project PATH    # 프로젝트 루트 지정
  python agentis/workflows/프로젝트-정리.py --report out.md  # 보고서 경로 지정
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import shutil
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

EXCLUDE_DIRS = {".git", "agentis", ".clinerules", "_archive", ".idea", ".vscode"}
GENERATED_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", "dist", "build", "coverage", ".next", ".turbo"}
TEMP_SUFFIXES = {".pyc", ".pyo", ".tmp", ".temp", ".bak", ".orig", ".swp", ".swo"}
TEMP_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}


def find_project_root(start: Path) -> Path:
    p = start.resolve()
    if p.is_file():
        p = p.parent
    # 스크립트가 agentis/workflows 안에서 실행되면 프로젝트 루트는 agentis 의 부모.
    for cand in [p, *p.parents]:
        if cand.name == "agentis" and (cand / "agent.md").exists():
            return cand.parent
    for cand in [p, *p.parents]:
        if (cand / ".clinerules").exists() or (cand / "agentis").is_dir() or (cand / ".git").is_dir():
            return cand
    return p


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_excluded(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return any(part in EXCLUDE_DIRS for part in parts)


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        # 제외 폴더는 내려가지 않음
        dirnames[:] = [x for x in dirnames if x not in EXCLUDE_DIRS]
        for name in filenames:
            fp = d / name
            if not is_excluded(fp, root):
                yield fp


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_candidates(root: Path) -> list[dict]:
    candidates: list[dict] = []
    files = list(iter_files(root))

    # 1) 명백한 임시/생성물 후보
    for fp in files:
        parts = fp.relative_to(root).parts
        if any(part in GENERATED_DIRS for part in parts[:-1]):
            candidates.append({"path": fp, "reason": "생성물/캐시 폴더", "group": "generated"})
            continue
        if fp.name in TEMP_NAMES or fp.suffix.lower() in TEMP_SUFFIXES:
            candidates.append({"path": fp, "reason": "임시/백업 파일", "group": "temp"})

    seen = {c["path"] for c in candidates}

    # 2) 동일 내용 중복 후보: 큰 파일도 안전하게 sha 계산. 같은 sha 그룹에서 가장 짧은 경로/이른 이름을 보존.
    by_size: dict[int, list[Path]] = {}
    for fp in files:
        if fp in seen:
            continue
        try:
            size = fp.stat().st_size
        except OSError:
            continue
        if size == 0:
            continue
        by_size.setdefault(size, []).append(fp)

    for same_size in by_size.values():
        if len(same_size) < 2:
            continue
        by_hash: dict[str, list[Path]] = {}
        for fp in same_size:
            try:
                by_hash.setdefault(sha256(fp), []).append(fp)
            except OSError:
                continue
        for group in by_hash.values():
            if len(group) < 2:
                continue
            group_sorted = sorted(group, key=lambda p: (len(rel(p, root)), rel(p, root)))
            keep = group_sorted[0]
            for dup in group_sorted[1:]:
                candidates.append({"path": dup, "reason": f"중복 파일 — 보존본: {rel(keep, root)}", "group": "duplicate"})

    # 중복 제거
    out = []
    used: set[Path] = set()
    for c in sorted(candidates, key=lambda x: rel(x["path"], root)):
        if c["path"] in used:
            continue
        used.add(c["path"])
        out.append(c)
    return out


def write_report(root: Path, candidates: list[dict], archive_dir: Path | None, report_path: Path) -> str:
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# Agentis 프로젝트 정리 보고서",
        "",
        f"- 생성: {now}",
        f"- 프로젝트: `{root}`",
        f"- 후보 수: {len(candidates)}",
        f"- 적용 모드: {'archive 이동 완료' if archive_dir else 'dry-run / 이동 없음'}",
    ]
    if archive_dir:
        lines.append(f"- 보관 위치: `{archive_dir}`")
    lines += ["", "## 원칙", "", "- 삭제하지 않음: 모든 적용 작업은 `_archive/` 보관 이동만 수행", "- `.git`, `agentis`, `.clinerules`, `_archive` 는 기본 제외", "- 사용자가 영구 삭제를 원하면 보고서를 보고 별도 승인 후 처리", ""]
    if not candidates:
        lines += ["## 결과", "", "정리 후보가 없습니다."]
    else:
        lines += ["## 정리 후보", ""]
        for i, c in enumerate(candidates, 1):
            lines.append(f"{i}. `{rel(c['path'], root)}` — {c['reason']} ({c['group']})")
    text = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    return text


def archive_candidates(root: Path, candidates: list[dict]) -> Path:
    stamp = _dt.datetime.now().strftime("%Y-%m-%dT%H%M%S")
    archive_dir = root / "_archive" / f"agentis-cleanup-{stamp}"
    archive_dir.mkdir(parents=True, exist_ok=False)
    for c in candidates:
        src: Path = c["path"]
        if not src.exists():
            continue
        dst = archive_dir / rel(src, root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    return archive_dir


def append_log(project_root: Path, candidates: list[dict], archive_dir: Path | None, report_path: Path) -> None:
    log = project_root / "agentis" / "memory" / "log.md"
    if not log.is_file():
        return
    today = _dt.date.today().isoformat()
    title = "프로젝트 정리 dry-run" if archive_dir is None else "프로젝트 정리 보관 이동"
    body = [f"## [{today}] lint [aux] | {title}", f"- candidates: {len(candidates)}", f"- report: [[{rel(report_path, project_root)}]]"]
    if archive_dir:
        body.append(f"- archive: `{rel(archive_dir, project_root)}`")
    body.append("")
    text = log.read_text(encoding="utf-8", errors="replace")
    log.write_text("\n".join(body) + "\n" + text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Agentis 프로젝트 정리 후보 보고 및 _archive 보관")
    ap.add_argument("--project", type=Path, default=None, help="프로젝트 루트. 기본: 현재 위치에서 자동 탐색")
    ap.add_argument("--apply", action="store_true", help="정리 후보를 _archive 로 실제 이동")
    ap.add_argument("--report", type=Path, default=None, help="보고서 경로. 기본: agentis/memory/sources/프로젝트-정리-보고서.md")
    args = ap.parse_args(argv)

    start = args.project if args.project else Path.cwd()
    root = find_project_root(start)
    report_path = args.report or (root / "agentis" / "memory" / "sources" / "프로젝트-정리-보고서.md")

    candidates = collect_candidates(root)
    archive_dir = archive_candidates(root, candidates) if args.apply and candidates else None
    report = write_report(root, candidates, archive_dir, report_path)
    append_log(root, candidates, archive_dir, report_path)

    print(report)
    if not args.apply and candidates:
        print("\n[프로젝트-정리] dry-run 입니다. 실제 보관 이동은 --apply 를 붙여 실행하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
