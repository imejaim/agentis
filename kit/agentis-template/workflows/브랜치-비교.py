#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.3 / 브랜치-비교
"""
브랜치-비교 — 두 에이전트(또는 두 브랜치)의 스킬/워크플로우/개념 디프 보고서.

입력: 두 경로. 각 경로는 agentis/ 또는 브랜치 폴더(`fork/` 가 안에 있음) 또는 pack/.
출력: 콘솔 요약 + 마크다운 보고서 한 장.

비교 차원:
  - 한쪽에만 있음 (한쪽에서 메인으로 채택 후보)
  - 양쪽에 있고 내용 동일 (정렬됨)
  - 양쪽에 있고 내용 다름 (=충돌, 사람 결정)
  - 비슷한 이름 가능성 (휴리스틱: 슬러그 prefix/suffix)

표준 라이브러리만. 결정론적.
"""
from __future__ import annotations
import argparse
import hashlib
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def resolve_input(p: Path) -> Path:
    """입력 경로를 '비교 가능한 루트'로 해석한다.
       - <X>/agent.md 있음 → X (agentis/ 자체)
       - <X>/fork/ 있고 fork/agent.md 있음 → X/fork (브랜치 폴더)
       - <X>/pack.meta.md 있음 → X (pack 폴더; agent.md 없음)
       - 그 외 → 그대로
    """
    p = p.resolve()
    if (p / "fork").is_dir() and (p / "fork" / "agent.md").is_file():
        return p / "fork"
    return p


def short_label(p: Path) -> str:
    return p.name + ("/" + p.parent.name if p.parent.name else "")


def norm_text(text: str) -> bytes:
    """공백·줄바꿈 정규화 후 해시 입력으로."""
    t = "\n".join(line.rstrip() for line in text.splitlines())
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t.encode("utf-8")


def hash_file(p: Path) -> str:
    try:
        return hashlib.sha1(norm_text(p.read_text(encoding="utf-8", errors="replace"))).hexdigest()[:12]
    except Exception:
        return "??"


def hash_dir(d: Path) -> str:
    """디렉토리의 .md/.py 파일들을 정렬해 합쳐 해시."""
    h = hashlib.sha1()
    if not d.is_dir():
        return "??"
    for f in sorted(d.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in (".md", ".py"):
            continue
        rel = f.relative_to(d).as_posix()
        h.update(rel.encode("utf-8")); h.update(b"\0")
        try:
            h.update(norm_text(f.read_text(encoding="utf-8", errors="replace")))
        except Exception:
            pass
        h.update(b"\0")
    return h.hexdigest()[:12]


def list_skills(root: Path) -> dict[str, Path]:
    sk = root / "skills"
    if not sk.is_dir():
        return {}
    return {d.name: d for d in sk.iterdir() if d.is_dir() and not d.name.startswith(("_", "."))}


def list_workflows(root: Path) -> dict[str, Path]:
    wf = root / "workflows"
    if not wf.is_dir():
        return {}
    out = {}
    for f in wf.iterdir():
        if f.is_file() and not f.name.startswith((".", "_")) and f.name != "README.md":
            out[f.name] = f
    return out


def list_concepts(root: Path) -> dict[str, Path]:
    c = root / "memory" / "concepts"
    if not c.is_dir():
        return {}
    out = {}
    for f in c.rglob("*.md"):
        if f.name == "README.md":
            continue
        out[f.relative_to(c).as_posix()] = f
    return out


def read_h1(p: Path) -> str:
    if not p.is_file():
        # 폴더의 대표 H1: 그 안 SKILL.md
        skill_md = p / "SKILL.md" if p.is_dir() else None
        if skill_md and skill_md.is_file():
            p = skill_md
        else:
            return ""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    m = H1_RE.search(text)
    return m.group(1).strip() if m else ""


def compare_set(a_map: dict[str, Path], b_map: dict[str, Path], hasher) -> list[dict]:
    keys = sorted(set(a_map) | set(b_map))
    rows = []
    for k in keys:
        a = a_map.get(k); b = b_map.get(k)
        if a and not b:
            rows.append({"name": k, "status": "A에만", "note": f"A에서 추가됨 (`{read_h1(a)[:40]}`)"})
        elif b and not a:
            rows.append({"name": k, "status": "B에만", "note": f"B에서 추가됨 (`{read_h1(b)[:40]}`)"})
        else:
            ha = hasher(a); hb = hasher(b)
            if ha == hb:
                rows.append({"name": k, "status": "양쪽-동일", "note": ""})
            else:
                ah1 = read_h1(a)[:30]; bh1 = read_h1(b)[:30]
                rows.append({"name": k, "status": "충돌", "note": f"내용 다름 (A:`{ah1}` / B:`{bh1}`)"})
    # 비슷한 이름 휴리스틱
    a_only = [r["name"] for r in rows if r["status"] == "A에만"]
    b_only = [r["name"] for r in rows if r["status"] == "B에만"]
    for an in a_only:
        for bn in b_only:
            ax = an.lower().rstrip(".md"); bx = bn.lower().rstrip(".md")
            if (len(ax) >= 4 and (ax in bx or bx in ax)):
                for r in rows:
                    if r["name"] == an:
                        r["note"] += f"  (B의 `{bn}` 와 이름 비슷 — 의미 매칭 확인 권장)"
                        break
                break
    return rows


def render_section(title: str, rows: list[dict]) -> list[str]:
    out = [f"## {title}\n"]
    n_a = sum(1 for r in rows if r["status"] == "A에만")
    n_b = sum(1 for r in rows if r["status"] == "B에만")
    n_same = sum(1 for r in rows if r["status"] == "양쪽-동일")
    n_conf = sum(1 for r in rows if r["status"] == "충돌")
    out.append(f"- A에만 {n_a} / B에만 {n_b} / 양쪽-동일 {n_same} / 충돌 **{n_conf}**\n")
    out.append("| 이름 | 상태 | 비고 |")
    out.append("|---|---|---|")
    for r in rows:
        out.append(f"| {r['name']} | {r['status']} | {r['note']} |")
    out.append("")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="두 에이전트/브랜치의 스킬·워크플로우·개념 디프 보고서")
    ap.add_argument("a", type=Path, help="A 경로 (agentis/ 또는 브랜치 폴더 또는 fork/)")
    ap.add_argument("b", type=Path, help="B 경로 (동일)")
    ap.add_argument("--out", type=Path, default=None, help="보고서 출력 경로 (.md). 미지정 시 콘솔만.")
    ap.add_argument("--filter", type=str, default="", help="비교 대상 좁히기 (콤마: skills,workflows,concepts)")
    args = ap.parse_args(argv)

    a = resolve_input(args.a); b = resolve_input(args.b)
    if not a.is_dir() or not b.is_dir():
        print("[비교] 두 경로 모두 디렉토리여야 합니다.", file=sys.stderr)
        return 2
    only = {x.strip() for x in args.filter.split(",") if x.strip()}

    print(f"[비교] A: {a}")
    print(f"[비교] B: {b}")

    sections = []
    if not only or "skills" in only:
        rows = compare_set(list_skills(a), list_skills(b), hash_dir)
        sections.append(("Skills", rows))
    if not only or "workflows" in only:
        rows = compare_set(list_workflows(a), list_workflows(b), hash_file)
        sections.append(("Workflows", rows))
    if not only or "concepts" in only:
        rows = compare_set(list_concepts(a), list_concepts(b), hash_file)
        sections.append(("Concepts", rows))

    lines: list[str] = []
    lines.append(f"# 브랜치 비교 — {short_label(a)} vs {short_label(b)}\n")
    lines.append(f"- A: `{a}`")
    lines.append(f"- B: `{b}`")
    lines.append("")
    total_conf = 0
    for title, rows in sections:
        lines += render_section(title, rows)
        total_conf += sum(1 for r in rows if r["status"] == "충돌")
    lines.append("## 결정 가이드")
    lines.append("- **A에만 / B에만**: 보통 양쪽 메인으로 가져갈 후보. 도메인 차이로 적용 안 되는 것만 빼고.")
    lines.append("- **양쪽-동일**: 이미 정렬됨, 메인에 그대로.")
    lines.append("- **충돌**: 관리자(사람)가 H1·본문 비교하고 더 일반화된/검증된 쪽 채택. 둘 다 가치 있으면 이름 갈라서(`<이름>-A`, `<이름>-B`) 둘 다 채택.")
    lines.append("- **이름 비슷 의심**: 의미 매칭 확인 후 통합 여부 결정.")
    report = "\n".join(lines)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"[비교] -> {args.out}")
    else:
        # 콘솔에 요약만
        for title, rows in sections:
            n_a = sum(1 for r in rows if r["status"] == "A에만")
            n_b = sum(1 for r in rows if r["status"] == "B에만")
            n_same = sum(1 for r in rows if r["status"] == "양쪽-동일")
            n_conf = sum(1 for r in rows if r["status"] == "충돌")
            print(f"[비교] {title}: A에만 {n_a} / B에만 {n_b} / 동일 {n_same} / 충돌 {n_conf}")
    return 1 if total_conf else 0


if __name__ == "__main__":
    raise SystemExit(main())
