#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
checklist-대조 — 요구 체크리스트 ↔ 제출 문서 목록 대조 (누락 찾기).

[[concepts/체크리스트-대조-원칙]] 의 규칙을 코드로:
  1) 정규화 후 비교  2) 동의어 사전  3) 개수 검증  4) OK/누락/미확인 3분류

표준 라이브러리만 사용. 결정론적(같은 입력 → 같은 출력).

사용:
    python run.py --checklist 요구체크리스트.txt --submitted 제출문서목록.txt --out 대조결과.md

종료 코드: 누락 또는 미확인이 하나라도 있으면 1, 전부 OK면 0. (개수 검증 실패 시 2)
"""
from __future__ import annotations
import argparse
import re
import sys
import unicodedata
from pathlib import Path

# Windows 콘솔(cp949) 등에서 한글/이모지 출력 시 깨지거나 죽지 않게 — 표준출력을 utf-8로.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# 동의어 사전: 한 줄 = 같은 것으로 취급하는 표현들 (정규화 전 표기 그대로 적어도 됨 — 아래에서 정규화함).
# 새 별칭(특히 '미확인'으로 빠진 항목)을 만나면 해당 줄에 추가한다 = 스킬 개선.
SYNONYMS: list[set[str]] = [
    {"부품표", "부품표(BOM)", "자재명세서", "자재명세서(BOM)", "BOM"},
    {"회로도", "회로도 (블록도 포함)", "회로도 및 블록도", "회로도(블럭도 포함)"},
    {"사용설명서", "사용설명서(한글)", "취급설명서", "한글 사용설명서"},
    {"인증 신청서", "신청서", "인증서 신청서"},
    {"핵심부품 인증서", "핵심부품 인증서 사본", "핵심부품 성적서"},
    {"EMC 시험성적서", "전자파 시험성적서", "EMC성적서"},
    {"시험성적서", "안전 시험성적서"},  # 주: EMC 성적서는 별도 그룹
]


def normalize(s: str) -> str:
    """공백/괄호/구두점/전각·반각/대소문자 제거 후 비교용 키."""
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    s = re.sub(r"[\s()\[\]{}<>·.,;:/\\\-_~'\"`!?]+", "", s)
    return s


# 정규화 키 -> 동의어 그룹 대표(group id). 사전에 없으면 자기 자신이 대표.
_SYN_MAP: dict[str, str] = {}
for group in SYNONYMS:
    rep = sorted(group)[0]
    for member in group:
        _SYN_MAP[normalize(member)] = rep


def canon(key: str) -> str:
    return _SYN_MAP.get(key, key)


def read_items(path: Path) -> list[str]:
    """한 줄 = 한 항목. 빈 줄과 '#' 주석 줄은 무시. 원문(트림만) 리스트 반환."""
    items: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        t = line.strip()
        if not t or t.startswith("#"):
            continue
        items.append(t)
    return items


def compare(checklist: list[str], submitted: list[str]):
    # 제출목록: 정규화 키 집합 + 정규 그룹 집합
    sub_norm = {normalize(x) for x in submitted}
    sub_canon = {canon(n) for n in sub_norm}

    rows = []  # (체크리스트 원문, 상태, 비고)
    for raw in checklist:
        n = normalize(raw)
        c = canon(n)
        if n in sub_norm or c in sub_canon:
            rows.append((raw, "OK", ""))
            continue
        # 미확인: 정규화 키 일부가 겹치는 후보가 제출목록에 있나? (부분 일치 — 사람 확인용)
        near = [s for s in submitted if n and (n in normalize(s) or normalize(s) in n)]
        if near:
            rows.append((raw, "미확인", "유사: " + " / ".join(sorted(set(near)))))
        else:
            rows.append((raw, "누락", ""))
    return rows


def render_md(rows, checklist, submitted, checklist_path, submitted_path) -> str:
    n_ok = sum(1 for _, s, _ in rows if s == "OK")
    n_missing = sum(1 for _, s, _ in rows if s == "누락")
    n_unknown = sum(1 for _, s, _ in rows if s == "미확인")
    # 제출됐는데 체크리스트엔 없는 것(참고)
    cl_canon = {canon(normalize(x)) for x in checklist}
    extra = sorted({s for s in submitted if canon(normalize(s)) not in cl_canon})

    out = []
    out.append(f"# 체크리스트 대조 결과\n")
    out.append(f"- 체크리스트: `{checklist_path}` ({len(checklist)}건)")
    out.append(f"- 제출문서목록: `{submitted_path}` ({len(submitted)}건)")
    out.append(f"- 결과: ✅ OK {n_ok} · ❌ **누락 {n_missing}** · ⚠ 미확인 {n_unknown}\n")
    if n_missing:
        out.append("## ❌ 누락 (체크리스트엔 있는데 제출 목록에 없음 — 반드시 확인)")
        for raw, s, _ in rows:
            if s == "누락":
                out.append(f"- [ ] {raw}")
        out.append("")
    if n_unknown:
        out.append("## ⚠ 미확인 (이름이 비슷한 게 있음 — 사람 확인 필요. 같은 거면 run.py SYNONYMS에 추가)")
        for raw, s, note in rows:
            if s == "미확인":
                out.append(f"- {raw}  — {note}")
        out.append("")
    out.append("## 전체")
    out.append("| 체크리스트 항목 | 상태 | 비고 |")
    out.append("|---|---|---|")
    for raw, s, note in rows:
        mark = {"OK": "✅ OK", "누락": "❌ 누락", "미확인": "⚠ 미확인"}[s]
        out.append(f"| {raw} | {mark} | {note} |")
    out.append("")
    if extra:
        out.append("## (참고) 제출됐지만 체크리스트엔 없는 항목")
        for e in extra:
            out.append(f"- {e}")
        out.append("")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="요구 체크리스트 ↔ 제출 문서 목록 대조")
    ap.add_argument("--checklist", type=Path, required=True, help="요구 체크리스트 .txt (한 줄=한 항목)")
    ap.add_argument("--submitted", type=Path, required=True, help="제출 문서 목록 .txt (한 줄=한 항목)")
    ap.add_argument("--out", type=Path, required=True, help="대조 결과 .md 출력 경로")
    args = ap.parse_args(argv)

    for p in (args.checklist, args.submitted):
        if not p.is_file():
            print(f"[checklist-대조] 파일 없음: {p}", file=sys.stderr)
            return 2

    checklist = read_items(args.checklist)
    submitted = read_items(args.submitted)
    rows = compare(checklist, submitted)

    # ── 개수 검증 ([[concepts/체크리스트-대조-원칙]] §3) ──
    if len(rows) != len(checklist):
        print(f"[checklist-대조] 개수 검증 실패: 대조 {len(rows)}건 != 체크리스트 {len(checklist)}건", file=sys.stderr)
        return 2

    md = render_md(rows, checklist, submitted, args.checklist, args.submitted)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")

    n_ok = sum(1 for _, s, _ in rows if s == "OK")
    n_missing = sum(1 for _, s, _ in rows if s == "누락")
    n_unknown = sum(1 for _, s, _ in rows if s == "미확인")
    print(f"[checklist-대조] 개수 검증 OK ({len(rows)}=={len(checklist)})")
    print(f"[checklist-대조] OK {n_ok} / 누락 {n_missing} / 미확인 {n_unknown}  ->  {args.out}")
    if n_missing:
        print("  [누락] " + " | ".join(raw for raw, s, _ in rows if s == "누락"))
    if n_unknown:
        print("  [미확인] " + " | ".join(raw for raw, s, _ in rows if s == "미확인"))
    return 1 if (n_missing or n_unknown) else 0


if __name__ == "__main__":
    raise SystemExit(main())
