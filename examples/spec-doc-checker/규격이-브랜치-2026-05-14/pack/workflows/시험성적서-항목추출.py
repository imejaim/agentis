#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
시험성적서-항목추출 — 시험성적서 텍스트에서 시험 항목 표를 뽑아 csv 로.

입력: 텍스트 파일. 본문 어딘가에 '|' 로 칸을 구분한 표가 있고, 헤더 행에 '시험항목' 이 포함됨.
출력: csv ([[concepts/시험성적서-항목-스키마]]: 시험항목,규격조항,요구값,측정값,판정,비고)

검증(콘솔):
  - 추출 데이터 행 수 == 입력 표의 데이터 행 수  (아니면 종료코드 2)
  - '??' 들어간 칸 목록 (사람 확인 필요)
  - 판정이 '부적합' 인 행 (강조)

표준 라이브러리만. 결정론적.

사용:
    python 시험성적서-항목추출.py --in 성적서.txt --out 항목표.csv
종료 코드: 정상 0, '??' 나 '부적합' 있으면 1, 검증 실패 2
"""
from __future__ import annotations
import argparse
import csv
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows 콘솔에서 한글 출력 안전하게
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

COLUMNS = ["시험항목", "규격조항", "요구값", "측정값", "판정", "비고"]
MISSING = "??"


def find_table(text: str):
    """'|' 가 2개 이상인 연속 줄 블록 중, 헤더에 '시험항목' 이 있는 첫 블록을 표로 본다."""
    lines = text.splitlines()
    blocks = []
    cur = []
    for ln in lines:
        if ln.count("|") >= 2:
            cur.append(ln)
        else:
            if cur:
                blocks.append(cur)
                cur = []
    if cur:
        blocks.append(cur)
    for b in blocks:
        if "시험항목" in b[0].replace(" ", ""):
            return b
    # 헤더 못 찾으면 가장 큰 블록을 표로 (헤더 없음 가정)
    return max(blocks, key=len) if blocks else []


def split_row(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def is_separator(cells: list[str]) -> bool:
    """'---|---|---' 같은 마크다운 구분 줄?"""
    joined = "".join(cells)
    return joined != "" and set(joined) <= set("-: ")


def normalize_cell(c: str) -> str:
    c = c.strip()
    if c in ("", "-", "—", "·", "n/a", "N/A", "?", "???"):
        # 빈/불명 표시는 보수적으로 처리: 완전히 비면 빈칸, 물음표류면 MISSING
        return MISSING if "?" in c else c
    return c


def extract(text: str):
    block = find_table(text)
    if not block:
        return [], 0, []  # rows, data_row_count, warnings

    rows_raw = [split_row(ln) for ln in block]
    rows_raw = [r for r in rows_raw if not is_separator(r)]
    if not rows_raw:
        return [], 0, []

    # 헤더 처리
    header = rows_raw[0]
    has_header = "시험항목" in "".join(header).replace(" ", "")
    data_rows = rows_raw[1:] if has_header else rows_raw
    data_row_count = len(data_rows)

    # 컬럼 매핑: 헤더가 있으면 헤더명으로, 없으면 위치순(앞 6칸)
    out_rows = []
    warnings = []  # (행번호, 컬럼, 값)
    for i, r in enumerate(data_rows, start=1):
        cells = [normalize_cell(c) for c in r]
        row = {col: "" for col in COLUMNS}
        if has_header:
            hdr_norm = [h.replace(" ", "") for h in header]
            for col in COLUMNS:
                # 헤더에서 col 을 포함하는 첫 칸
                for j, h in enumerate(hdr_norm):
                    if col in h and j < len(cells):
                        row[col] = cells[j]
                        break
        else:
            for j, col in enumerate(COLUMNS):
                row[col] = cells[j] if j < len(cells) else ""
        # 필수 칸 비면 MISSING 으로 (시험항목/규격조항/판정)
        for col in ("시험항목", "규격조항", "판정"):
            if row[col] == "":
                row[col] = MISSING
        for col in COLUMNS:
            if MISSING in row[col]:
                warnings.append((i, col, row[col]))
        out_rows.append(row)
    return out_rows, data_row_count, warnings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="시험성적서 텍스트 → 항목표 csv")
    ap.add_argument("--in", dest="inp", type=Path, required=True, help="시험성적서 텍스트 .txt")
    ap.add_argument("--out", type=Path, required=True, help="항목표 .csv 출력 경로")
    args = ap.parse_args(argv)

    if not args.inp.is_file():
        print(f"[항목추출] 입력 파일 없음: {args.inp}", file=sys.stderr)
        return 2

    text = args.inp.read_text(encoding="utf-8", errors="replace")
    rows, data_row_count, warnings = extract(text)

    if not rows:
        print("[항목추출] 표를 찾지 못했습니다. 입력에 '|' 구분 표가 있는지 확인하세요.", file=sys.stderr)
        return 2

    # ── 검증: 추출 행 수 == 입력 표 데이터 행 수 ──
    if len(rows) != data_row_count:
        print(f"[항목추출] 행 수 검증 실패: 추출 {len(rows)} != 표 데이터 {data_row_count}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    fails = [(i, r) for i, r in enumerate(rows, 1) if r["판정"].replace(" ", "") == "부적합"]
    print(f"[항목추출] 행 수 검증 OK ({len(rows)}=={data_row_count})  ->  {args.out}")
    if warnings:
        print(f"[항목추출] [확인필요] 못 읽은 칸 {len(warnings)}개:")
        for i, col, val in warnings:
            print(f"   {i}행 '{col}' = {val}")
    if fails:
        print(f"[항목추출] [부적합] 판정 '부적합' 행 {len(fails)}개:")
        for i, r in fails:
            print(f"   {i}행: {r['시험항목']} / {r['규격조항']} / 측정 {r['측정값']}")
    return 1 if (warnings or fails) else 0


if __name__ == "__main__":
    raise SystemExit(main())
