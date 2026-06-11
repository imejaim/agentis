#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a minimal internal Agentis distribution repo.

The public/development repo can contain plans, examples, tests, generated demos,
and research notes.  The internal distribution repo should contain only the
bootstrap surface needed by Cline:

  - install.py / install.sh / install.bat
  - .clinerules/agentis.md and routing rule
  - seed/10-agent-routing.md for installer source compatibility
  - kit/agentis-template/**
  - a concise README with the exact Cline prompt

No git metadata, examples, docs, root generated html, __pycache__, or local state
are copied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "_dist" / "agentis-seed"

INCLUDE_PATHS = [
    "install.py",
    "install.sh",
    "install.bat",
    ".clinerules/agentis.md",
    ".clinerules/10-agent-routing.md",
    "seed/10-agent-routing.md",
    "kit/README.md",
    "kit/agentis-template",
]

EXCLUDE_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".DS_Store",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

README_TEMPLATE = """# Agentis Seed — Internal Distribution

Agentis v1.10 minimal install package.

이 레포는 사내용 배포본입니다. 개발 문서, 예제, 테스트, 개인 작업물은 제외하고 설치에 필요한 씨드와 키트만 담습니다.

## Cline에 붙여넣을 설치 프롬프트

```text
이 사내 GitHub 레포를 지금 이 작업 폴더에 Agentis로 셋업해줘:
{repo_url}

반드시 아래 순서로 해줘. kit 폴더를 수동 복사하지 말고 install.py를 실행해.

1) 현재 작업 폴더 안이 아닌 임시 폴더에 git clone.
2) 클론한 레포 루트에서 다음 명령을 실행:
   python install.py --target "<현재 작업 폴더 절대경로>"
3) 설치 후 현재 작업 폴더 루트에 아래가 있는지 확인:
   .clinerules/agentis.md
   .clinerules/workflows/
   agentis/
   workflows.html
   holonomic-brain.html
   holonomic-brain.json
4) 임시 clone 폴더는 삭제.
5) 완료되면 나에게 "안녕"이라고 말 걸어줘.
```

## 기존 프로젝트 업데이트

```bash
python install.py --target "<작업폴더>" --upgrade-kit
```

`--upgrade-kit`은 기존 `.clinerules/agentis.md`, `.clinerules/workflows/`, `agentis/memory/`, `agentis/skills/`, 기존 생성 HTML/그래프를 덮어쓰지 않습니다.

## 포함 항목

- `install.py`, `install.sh`, `install.bat`
- `.clinerules/agentis.md`
- `.clinerules/10-agent-routing.md`
- `seed/10-agent-routing.md`
- `kit/agentis-template/`

## 제외 항목

- 개발용 `examples/`, `docs/`, `tests/`, `PLAN.md`, root generated demo HTML
- `.git/`, `__pycache__/`, `.pyc`, 로컬 상태 파일
"""


def should_skip(path: Path) -> bool:
    if any(part in EXCLUDE_PARTS for part in path.parts):
        return True
    if path.suffix in EXCLUDE_SUFFIXES:
        return True
    return False


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def copy_tree(src: Path, dst: Path) -> list[Path]:
    copied: list[Path] = []
    if src.is_file():
        if should_skip(src):
            return copied
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(dst)
        return copied
    for item in sorted(src.rglob("*")):
        rel = item.relative_to(src)
        if should_skip(rel) or should_skip(item):
            continue
        out = dst / rel
        if item.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, out)
            copied.append(out)
    return copied


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(out: Path) -> dict:
    files = []
    for p in sorted(x for x in out.rglob("*") if x.is_file()):
        rel = p.relative_to(out).as_posix()
        files.append({"path": rel, "bytes": p.stat().st_size, "sha256": sha256(p)})
    return {"name": "agentis-seed", "version": "1.10", "file_count": len(files), "files": files}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build minimal Agentis internal distribution")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    ap.add_argument("--repo-url", default="<사내깃-URL>", help="internal repo URL to put in README")
    args = ap.parse_args(argv)

    out = args.out.resolve()
    clean_dir(out)

    copied: list[Path] = []
    for rel_s in INCLUDE_PATHS:
        src = ROOT / rel_s
        if not src.exists():
            raise SystemExit(f"missing required source: {src}")
        copied.extend(copy_tree(src, out / rel_s))

    readme = README_TEMPLATE.format(repo_url=args.repo_url)
    (out / "README.md").write_text(readme, encoding="utf-8")

    manifest = build_manifest(out)
    (out / "DIST-MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    required = [
        out / "install.py",
        out / ".clinerules" / "agentis.md",
        out / "seed" / "10-agent-routing.md",
        out / "kit" / "agentis-template" / "graph" / "refresh_views.py",
        out / "kit" / "agentis-template" / "graph" / "build_workflows.py",
        out / "kit" / "agentis-template" / "graph" / "build_holonomic_brain.py",
    ]
    missing = [p for p in required if not p.is_file()]
    if missing:
        raise SystemExit("missing in dist: " + ", ".join(str(p) for p in missing))

    print(f"[build-dist] -> {out}")
    print(f"[build-dist] files={manifest['file_count']}")
    print("[build-dist] required OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
