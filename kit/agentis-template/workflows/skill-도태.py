#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.5 / skill-도태
"""
skill-도태.py — 30일+ 안 쓰인 스킬을 skills/_attic/ 으로 이동(보관). 삭제 X.

사용 횟수 카운트:
  memory/log.md 의 `## [YYYY-MM-DD] task | ... uses: <스킬>` 패턴.
  (구버전 호환: 본문에 `[[skills/<이름>]]` 링크가 나오는 것도 사용으로 침)

발상: 씨드 §3-7 의 자가 도태 — 안 쓰는 스킬은 두뇌 검색 잡음만 늘림.
보관(attic)으로 옮겨두고 필요해지면 사용자가 다시 꺼내쓰면 됨.

사용:
  python skill-도태.py                # 보고서만
  python skill-도태.py --apply        # 실제 이동 (_attic/<이름>/ 으로)
  python skill-도태.py --days 60      # 임계 일수 변경
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

LOG_ENTRY_RE = re.compile(r"^##\s*\[(\d{4}-\d{2}-\d{2})\]\s*(\w+)\s*\|\s*(.+?)$", re.MULTILINE)
USES_RE = re.compile(r"uses\s*[:=]\s*([^\n,;]+)", re.IGNORECASE)
SKILL_LINK_RE = re.compile(r"\[\[skills/([^\[\]/|]+)(?:/[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]")


def find_root(start: Path) -> Path:
    p = (start if start.is_dir() else start.parent).resolve()
    for c in [p, *p.parents]:
        if (c / "agent.md").exists() or (c / "skills").is_dir():
            return c
    return p


def parse_skill_uses(log_path: Path) -> dict[str, _dt.date]:
    """{스킬이름: 가장 최근 사용일}."""
    last: dict[str, _dt.date] = {}
    if not log_path.is_file():
        return last
    text = log_path.read_text(encoding="utf-8", errors="replace")
    # 항목별 블록 — 헤더 다음 줄부터 다음 헤더 전까지
    headers = list(LOG_ENTRY_RE.finditer(text))
    for i, m in enumerate(headers):
        try:
            d = _dt.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        start = m.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end]
        # uses: <스킬>
        for um in USES_RE.finditer(block):
            for name in um.group(1).split(","):
                n = name.strip().strip("[]").strip()
                if not n:
                    continue
                if "/" in n:
                    n = n.split("/", 1)[-1]
                if n not in last or last[n] < d:
                    last[n] = d
        # [[skills/<이름>]]
        for sm in SKILL_LINK_RE.finditer(block):
            n = sm.group(1).strip()
            if n not in last or last[n] < d:
                last[n] = d
    return last


def list_skills(root: Path) -> list[Path]:
    sd = root / "skills"
    if not sd.is_dir():
        return []
    out: list[Path] = []
    for d in sorted(sd.iterdir()):
        if not d.is_dir():
            continue
        if d.name.startswith("_"):
            continue  # _attic 등 제외
        if (d / "SKILL.md").is_file():
            out.append(d)
    return out


def move_to_attic(skill_dir: Path) -> Path:
    attic = skill_dir.parent / "_attic"
    attic.mkdir(parents=True, exist_ok=True)
    today = _dt.date.today().isoformat()
    dst = attic / f"{skill_dir.name}__retired-{today}"
    if dst.exists():
        # 같은 날 여러 번 — 번호 붙임
        i = 2
        while (attic / f"{skill_dir.name}__retired-{today}-{i}").exists():
            i += 1
        dst = attic / f"{skill_dir.name}__retired-{today}-{i}"
    shutil.move(str(skill_dir), str(dst))
    return dst


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="agentis 자가 도태 — 안 쓰는 스킬 보관")
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--days", type=int, default=30, help="이 일수 이상 미사용이면 도태 후보 (기본 30)")
    ap.add_argument("--apply", action="store_true", help="실제로 이동")
    args = ap.parse_args(argv)

    start = args.root if args.root else Path(__file__).resolve().parent
    root = find_root(start)
    log_path = root / "memory" / "log.md"
    last_used = parse_skill_uses(log_path)
    today = _dt.date.today()
    threshold = today - _dt.timedelta(days=args.days)

    skills = list_skills(root)
    if not skills:
        print(f"[skill-도태] skills/ 에 후보 없음 (root={root})")
        return 0

    report: list[dict] = []
    for sd in skills:
        last = last_used.get(sd.name)
        if last is None:
            status = "사용 기록 없음"
            stale = True
        else:
            status = f"마지막 사용 {last.isoformat()} (D-{(today - last).days})"
            stale = last < threshold
        report.append({"skill": sd.name, "stale": stale, "status": status, "path": sd})

    print(f"[skill-도태] root={root}  임계={args.days}일  오늘={today}")
    moved: list[str] = []
    for r in report:
        mark = "🗑️ 도태" if r["stale"] else "  활성"
        print(f"  {mark}  {r['skill']:30s}  — {r['status']}")
        if r["stale"] and args.apply:
            dst = move_to_attic(r["path"])
            moved.append(f"{r['skill']} → {dst.relative_to(root)}")

    if args.apply:
        print(f"\n[skill-도태] 이동 완료: {len(moved)}개")
        for m in moved:
            print(f"  • {m}")
        # 로그에 기록
        if moved and log_path.is_file():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            line = f"## [{today.isoformat()}] lint | 자가 도태 — {len(moved)}개 스킬 _attic/ 으로 보관\n- " + "\n- ".join(moved) + "\n\n"
            # 첫 ## 헤더 앞에 삽입
            m = re.search(r"^---\s*$", log_text, re.MULTILINE)
            insert_at = 0
            for mm in LOG_ENTRY_RE.finditer(log_text):
                insert_at = mm.start()
                break
            if insert_at > 0:
                log_text = log_text[:insert_at] + line + log_text[insert_at:]
            else:
                log_text = log_text.rstrip() + "\n\n" + line
            log_path.write_text(log_text, encoding="utf-8")
    else:
        stale_n = sum(1 for r in report if r["stale"])
        print(f"\n[skill-도태] dry-run: 도태 후보 {stale_n}개. 실제 이동은 --apply.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
