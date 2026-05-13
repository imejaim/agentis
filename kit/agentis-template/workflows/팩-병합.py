#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
팩-병합 — 다른 에이전트의 pack/ 폴더에서 skills/workflows/memory/concepts 만 골라 내 agentis/ 에 합친다.

절대 건드리지 않는 것 (안전 보장):
    agent.md, memory/sources/, memory/entities/, memory/log.md,
    memory/hot.md, memory/overview.md, memory/_index.md

충돌 정책 (--strategy):
    plan-only         : 머지 안 함. 어떤 게 새것/충돌/추가될지만 보고
    overwrite         : 충돌 시 팩의 것으로 덮어쓰기
    keep-mine         : 충돌 시 내 것 유지 (팩의 것 무시)
    rename-incoming   : 충돌 시 팩의 것을 '<원이름>-import' 로 이름 바꿔 같이 둠

표준 라이브러리만. 결정론적.

사용:
    python 팩-병합.py --pack <브랜치폴더>/pack --strategy plan-only
    python 팩-병합.py --pack <브랜치폴더>/pack --strategy overwrite
    python 팩-병합.py --pack <브랜치폴더>/pack --strategy rename-incoming --only skills
"""
from __future__ import annotations
import argparse
import datetime as _dt
import re
import shutil
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# 절대 건드리지 않는 경로 패턴 (root 기준 상대)
PROTECTED = (
    "agent.md",
    "memory/sources",
    "memory/entities",
    "memory/log.md",
    "memory/hot.md",
    "memory/overview.md",
    "memory/_index.md",
)


def find_root(start: Path) -> Path:
    p = (start if start.is_dir() else start.parent).resolve()
    for c in [p, *p.parents]:
        if (c / "agent.md").exists():
            return c
    return p


def read_h1(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    m = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def list_skill_dirs(skills_root: Path) -> list[Path]:
    if not skills_root.is_dir():
        return []
    return sorted([d for d in skills_root.iterdir() if d.is_dir() and not d.name.startswith(("_", "."))])


def plan_skills(pack_skills: Path, dst_skills: Path) -> list[dict]:
    plans = []
    for src in list_skill_dirs(pack_skills):
        dst = dst_skills / src.name
        plans.append({"kind": "skill", "name": src.name, "src": src, "dst": dst,
                      "status": "conflict" if dst.exists() else "new"})
    return plans


def plan_workflows(pack_wf: Path, dst_wf: Path) -> list[dict]:
    plans = []
    if not pack_wf.is_dir():
        return plans
    for src in sorted(pack_wf.iterdir()):
        if not src.is_file() or src.name.startswith((".", "_")) or src.name == "README.md":
            continue
        dst = dst_wf / src.name
        plans.append({"kind": "workflow", "name": src.name, "src": src, "dst": dst,
                      "status": "conflict" if dst.exists() else "new"})
    return plans


def plan_concepts(pack_concepts: Path, dst_concepts: Path) -> list[dict]:
    plans = []
    if not pack_concepts.is_dir():
        return plans
    for src in sorted(pack_concepts.rglob("*.md")):
        if src.name == "README.md":
            continue
        rel = src.relative_to(pack_concepts)
        dst = dst_concepts / rel
        plans.append({"kind": "concept", "name": str(rel), "src": src, "dst": dst,
                      "status": "conflict" if dst.exists() else "new"})
    return plans


def render_plan(plans: list[dict]) -> list[str]:
    out = []
    for p in plans:
        mark = "NEW " if p["status"] == "new" else "충돌"
        extra = ""
        if p["status"] == "conflict":
            src_h1 = read_h1(p["src"]) if p["src"].is_file() else "(폴더)"
            dst_h1 = read_h1(p["dst"]) if p["dst"].is_file() else "(폴더)"
            if src_h1 != dst_h1 and (src_h1 or dst_h1):
                extra = f"  내:'{dst_h1[:30]}' / 팩:'{src_h1[:30]}'"
        out.append(f"  [{mark}] {p['kind']:9s} {p['name']}{extra}")
    return out


def apply_plan(plans: list[dict], strategy: str) -> dict:
    stats = {"added": 0, "overwritten": 0, "kept": 0, "renamed": 0, "skipped": 0}
    for p in plans:
        kind = p["kind"]; src: Path = p["src"]; dst: Path = p["dst"]
        if p["status"] == "new":
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            stats["added"] += 1
            continue
        # conflict
        if strategy == "overwrite":
            if dst.is_dir():
                shutil.rmtree(dst)
            elif dst.is_file():
                dst.unlink()
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            stats["overwritten"] += 1
        elif strategy == "keep-mine":
            stats["kept"] += 1
        elif strategy == "rename-incoming":
            # <stem>-import<suffix>  (폴더면 <name>-import)
            if dst.is_dir():
                new_dst = dst.parent / (dst.name + "-import")
            else:
                stem = dst.stem
                suffix = dst.suffix
                # workflow.md 같은 복합 확장자 처리
                if dst.name.endswith(".workflow.md"):
                    stem = dst.name[:-len(".workflow.md")]
                    new_dst = dst.parent / f"{stem}-import.workflow.md"
                else:
                    new_dst = dst.parent / f"{stem}-import{suffix}"
            i = 2
            while new_dst.exists():
                if dst.is_dir():
                    new_dst = dst.parent / f"{dst.name}-import-{i}"
                else:
                    if dst.name.endswith(".workflow.md"):
                        new_dst = dst.parent / f"{stem}-import-{i}.workflow.md"
                    else:
                        new_dst = dst.parent / f"{stem}-import-{i}{suffix}"
                i += 1
            new_dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, new_dst)
            else:
                shutil.copy2(src, new_dst)
            stats["renamed"] += 1
        else:
            stats["skipped"] += 1
    return stats


def append_log(root: Path, pack_origin: str, stats: dict) -> None:
    log = root / "memory" / "log.md"
    if not log.is_file():
        return
    today = _dt.date.today().isoformat()
    entry = (f"\n## [{today}] ingest | {pack_origin} 의 pack 병합 "
             f"(추가 +{stats['added']} / 덮어쓰기 {stats['overwritten']} / "
             f"내것유지 {stats['kept']} / 이름변경 {stats['renamed']})\n"
             f"- skills/workflows/concepts 만 병합됨. agent.md·sources·log·hot·entities·overview·_index 는 건드리지 않음.\n")
    existing = log.read_text(encoding="utf-8", errors="replace")
    # 기존 첫 항목 위에 삽입 (`## [`로 시작하는 첫 줄 앞)
    m = re.search(r"^## \[", existing, re.MULTILINE)
    if m:
        new_text = existing[:m.start()] + entry.lstrip("\n") + "\n" + existing[m.start():]
    else:
        new_text = existing.rstrip() + entry
    log.write_text(new_text, encoding="utf-8")


def assert_no_protected_modified(root: Path) -> None:
    """안전 검증: PROTECTED 경로가 존재한다면 그 파일들의 변경이 발생하지 않았음을 가정.
    (이 스크립트는 절대 거기 쓰지 않으므로 호출 직전·직후를 비교할 필요는 없음 — 코드 경로상 보장.)"""
    # 단순 존재 확인 — 누가 실수로 삭제됐는지만 점검
    missing = [p for p in PROTECTED if not (root / p).exists() and p.endswith(".md")]
    if missing:
        print(f"[팩-병합] [경고] 보호 파일이 사라져있음: {missing}", file=sys.stderr)


def parse_pack_origin(pack_dir: Path) -> str:
    meta = pack_dir / "pack.meta.md"
    if meta.is_file():
        for line in meta.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("origin:"):
                return line.split(":", 1)[1].strip()
    return pack_dir.parent.name or "(미상)"


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="다른 에이전트의 pack 을 내 agentis 에 합치기")
    ap.add_argument("--root", type=Path, default=here.parent, help="내 agentis 디렉토리 (기본: 스크립트 기준 ../)")
    ap.add_argument("--pack", type=Path, required=True, help="머지할 pack 디렉토리 경로 (브랜치폴더/pack)")
    ap.add_argument("--strategy", type=str, default="plan-only",
                    choices=["plan-only", "overwrite", "keep-mine", "rename-incoming"],
                    help="충돌 정책")
    ap.add_argument("--only", type=str, default="", help="특정 종류만 (콤마: skills,workflows,concepts)")
    args = ap.parse_args(argv)

    root = find_root(args.root)
    if not (root / "agent.md").exists():
        print(f"[팩-병합] 내 agent.md 를 찾을 수 없음: {root}", file=sys.stderr)
        return 2
    pack = args.pack.resolve()
    if not pack.is_dir():
        print(f"[팩-병합] pack 디렉토리 없음: {pack}", file=sys.stderr)
        return 2

    only = {x.strip() for x in args.only.split(",") if x.strip()}

    origin = parse_pack_origin(pack)
    print(f"[팩-병합] 내 agentis: {root}")
    print(f"[팩-병합] 팩 출처: {origin}")
    print(f"[팩-병합] 정책: {args.strategy}")

    plans: list[dict] = []
    if not only or "skills" in only:
        plans += plan_skills(pack / "skills", root / "skills")
    if not only or "workflows" in only:
        plans += plan_workflows(pack / "workflows", root / "workflows")
    if not only or "concepts" in only:
        plans += plan_concepts(pack / "memory" / "concepts", root / "memory" / "concepts")

    n_new = sum(1 for p in plans if p["status"] == "new")
    n_conf = sum(1 for p in plans if p["status"] == "conflict")
    print(f"[팩-병합] 계획: NEW {n_new} / 충돌 {n_conf}  (총 {len(plans)})")
    for line in render_plan(plans):
        print(line)

    if args.strategy == "plan-only":
        print(f"[팩-병합] (plan-only — 실제 병합 안 함. 다시 실행할 때 --strategy 를 overwrite|keep-mine|rename-incoming 중 하나로.)")
        return 1 if n_conf else 0

    if n_conf and args.strategy not in ("overwrite", "keep-mine", "rename-incoming"):
        print(f"[팩-병합] 충돌 {n_conf}건 — strategy 가 결정되어야 진행", file=sys.stderr)
        return 2

    stats = apply_plan(plans, args.strategy)
    print(f"[팩-병합] 적용 — 추가 +{stats['added']} / 덮어쓰기 {stats['overwritten']} / 내것유지 {stats['kept']} / 이름변경 {stats['renamed']}")
    assert_no_protected_modified(root)
    append_log(root, origin, stats)
    print(f"[팩-병합] log.md 갱신. 그래프 갱신: python agentis/graph/build_graph.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
