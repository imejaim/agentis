#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.3 / 씨드-업그레이드
"""
씨드-업그레이드 — 자기 씨드(.clinerules / agentis.md)를 표준 씨드와 절(§) 단위로 비교·갱신·내보내기.

핵심:
- 씨드 절은 `<!-- @section: N -->` 앵커로 식별 (씨드 v1.3+).
- 절별 분류: UNCHANGED / NEW(표준에만) / LOCAL-CUSTOM(나만) / DIFF(둘 다 있는데 다름)
- 적용은 절 단위 `take`(표준 채택) / `keep`(내 것 유지) / `replace-with-file:<경로>`(머지본 파일).
- 결정론: 같은 입력 → 같은 plan.json → 같은 결과 씨드.
- 표준 라이브러리만, 사내망/오프라인 OK.

사용:
    python 씨드-업그레이드.py --check [--from <표준씨드>]
        → 절별 보고서(seed-upgrade-report.md) + plan.json 템플릿 출력
    python 씨드-업그레이드.py --apply --plan plan.json [--from <표준씨드>]
        → 결정 반영해 자기 씨드 갱신 (이전 버전은 .kit-mirror/seed/backup-YYYY-MM-DD.md)
    python 씨드-업그레이드.py --export-branch
        → seed-브랜치-YYYY-MM-DD/ 폴더 생성 (메인 큐레이터에게 송신용)
"""
from __future__ import annotations
import argparse
import datetime as _dt
import json
import re
import shutil
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# ─── 정규식 ──────────────────────────────────────────────────────────────────
SECTION_ANCHOR_RE = re.compile(r"^\s*<!--\s*@section:\s*([A-Za-z0-9._\-]+)\s*-->\s*$", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)
SEED_VERSION_RE = re.compile(r"seed-version:\s*([0-9.]+)")
# 본문 인라인 코드와 구분하기 위해 검색 범위는 항상 header 영역으로 (parse_sections 의 첫 반환).
LOCAL_MODS_RE = re.compile(r"local-mods:\s*([^\n`║│|]+?)\s*(?:[║│|]|$)", re.MULTILINE)


# ─── 위치 탐색 ──────────────────────────────────────────────────────────────
def find_seed_file(start: Path) -> Path | None:
    """작업 폴더 추정 후 .clinerules 또는 .clinerules/agentis.md 를 찾는다."""
    p = (start if start.is_dir() else start.parent).resolve()
    # agentis/workflows/ 에서 시작하면 ../../ 가 작업 폴더
    for c in [p, *p.parents]:
        for cand in (c / ".clinerules" / "agentis.md", c / ".clinerules"):
            if cand.is_file():
                try:
                    head = cand.read_text(encoding="utf-8", errors="replace")[:1000]
                    if "Agentis" in head or "agentis.md" in head:
                        return cand
                except Exception:
                    pass
    return None


def find_standard_seed(work_root: Path, from_arg: Path | None) -> Path | None:
    """표준 씨드 위치 — --from 우선, 그 다음 .kit-mirror/seed/agentis.md."""
    if from_arg:
        p = from_arg.resolve()
        return p if p.is_file() else None
    for cand in (
        work_root / "agentis" / ".kit-mirror" / "seed" / "agentis.md",
        work_root / ".kit-mirror" / "seed" / "agentis.md",
    ):
        if cand.is_file():
            return cand
    return None


# ─── 절 파싱 ─────────────────────────────────────────────────────────────────
def parse_sections(text: str) -> tuple[str, dict]:
    """씨드 텍스트를 (header, sections_dict) 로 자른다.
    sections: {anchor: {"anchor", "title", "body"}}, 표준 순서 유지 (Python 3.7+ dict).
    """
    sections: dict = {}
    matches = list(SECTION_ANCHOR_RE.finditer(text))
    if not matches:
        return text, {}
    header = text[: matches[0].start()]
    for i, m in enumerate(matches):
        anchor = m.group(1).strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        title = ""
        hm = HEADING_RE.search(body, m.end() - start)
        if hm:
            title = hm.group(2).strip()
        sections[anchor] = {"anchor": anchor, "title": title, "body": body}
    return header, sections


def normalize_for_diff(s: str) -> str:
    """공백·줄바꿈 정규화. 의미상 같은 변경은 같게 본다."""
    lines = [ln.rstrip() for ln in s.splitlines()]
    out = []
    prev_blank = False
    for ln in lines:
        if not ln:
            if prev_blank:
                continue
            prev_blank = True
        else:
            prev_blank = False
        out.append(ln)
    return "\n".join(out).strip()


def diff_sections(mine: dict, theirs: dict) -> list:
    """절별 분류. 표준 순서 → LOCAL-CUSTOM 은 뒤에."""
    out = []
    seen = set()
    for k, t in theirs.items():
        m = mine.get(k)
        if m:
            if normalize_for_diff(m["body"]) == normalize_for_diff(t["body"]):
                status, action = "UNCHANGED", "keep"
            else:
                status, action = "DIFF", "review"
        else:
            status, action = "NEW", "take"
        out.append({
            "anchor": k,
            "title": t["title"],
            "status": status,
            "action_default": action,
            "mine_lines": len(m["body"].splitlines()) if m else 0,
            "theirs_lines": len(t["body"].splitlines()),
        })
        seen.add(k)
    for k, m in mine.items():
        if k in seen:
            continue
        out.append({
            "anchor": k,
            "title": m["title"],
            "status": "LOCAL-CUSTOM",
            "action_default": "keep",
            "mine_lines": len(m["body"].splitlines()),
            "theirs_lines": 0,
        })
    return out


# ─── 보고서 / plan 템플릿 ───────────────────────────────────────────────────
def render_report(diff: list, mine_ver: str, theirs_ver: str) -> str:
    lines = [f"# 씨드 업그레이드 점검 — 내 씨드 v{mine_ver or '?'} → 표준 v{theirs_ver or '?'}", ""]
    counts: dict = {}
    for d in diff:
        counts[d["status"]] = counts.get(d["status"], 0) + 1
    lines.append("절별 분류: " + " / ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    lines.append("")
    lines.append("| 절 | 제목 | 상태 | 권장 | 내 / 표준 라인 수 |")
    lines.append("|---|---|---|---|---|")
    for d in diff:
        lines.append(f"| §{d['anchor']} | {d['title']} | {d['status']} | `{d['action_default']}` | {d['mine_lines']} / {d['theirs_lines']} |")
    lines.append("")
    lines.append("## 다음 단계")
    lines.append("1. 위 표를 보고 `plan.json` 의 각 항목 `action` 을 결정한다:")
    lines.append("   - `take` — 표준 절로 덮어쓰기 (보통 NEW · UPDATED 에 권장)")
    lines.append("   - `keep` — 내 절 유지 (LOCAL-CUSTOM 에 권장)")
    lines.append("   - `replace-with-file:<경로>` — 사람(또는 LLM)이 머지한 파일로 교체 (DIFF 에 권장)")
    lines.append("2. 결정한 plan.json 으로:")
    lines.append("   `python agentis/workflows/씨드-업그레이드.py --apply --plan plan.json --from <표준씨드>`")
    lines.append("3. 적용 후 `memory/log.md` 에 한 줄 기록:")
    lines.append("   `## [날짜] seed | upgrade vX → vY (적용 N / 보류 M)`")
    return "\n".join(lines)


def render_plan_template(diff: list) -> dict:
    return {
        "_doc": "각 항목의 action 을 정하세요: take / keep / replace-with-file:<경로>",
        "items": [
            {"anchor": d["anchor"], "title": d["title"], "status": d["status"], "action": d["action_default"]}
            for d in diff
        ],
    }


# ─── apply ───────────────────────────────────────────────────────────────────
def apply_plan(mine_text: str, theirs_text: str, plan: dict, work_root: Path) -> tuple[str, dict]:
    mine_header, mine_secs = parse_sections(mine_text)
    theirs_header, theirs_secs = parse_sections(theirs_text)
    stats = {"take": 0, "keep": 0, "replace": 0, "skipped": 0, "new": 0}

    decisions = {it["anchor"]: it.get("action", "keep") for it in plan.get("items", [])}

    # header — 표준 사용. local-mods 보존.
    new_header = theirs_header
    lm = LOCAL_MODS_RE.search(mine_header)
    if lm and "local-mods:" not in new_header:
        new_header = new_header.rstrip() + f"\n\nlocal-mods: {lm.group(1).strip()}\n"

    body_parts = [new_header]
    used: set = set()
    for anchor, sec in theirs_secs.items():
        action = decisions.get(anchor, "take" if anchor not in mine_secs else "keep")
        if action == "take":
            body_parts.append(sec["body"])
            stats["take"] += 1
            if anchor not in mine_secs:
                stats["new"] += 1
        elif action == "keep":
            if anchor in mine_secs:
                body_parts.append(mine_secs[anchor]["body"])
                stats["keep"] += 1
            else:
                body_parts.append(sec["body"])
                stats["take"] += 1
                stats["new"] += 1
        elif action.startswith("replace-with-file:"):
            path = action.split(":", 1)[1].strip()
            p = (work_root / path) if not Path(path).is_absolute() else Path(path)
            p = p.resolve()
            if p.is_file():
                body_parts.append(p.read_text(encoding="utf-8", errors="replace"))
                stats["replace"] += 1
            else:
                if anchor in mine_secs:
                    body_parts.append(mine_secs[anchor]["body"])
                else:
                    body_parts.append(sec["body"])
                stats["skipped"] += 1
        else:
            if anchor in mine_secs:
                body_parts.append(mine_secs[anchor]["body"])
            stats["skipped"] += 1
        used.add(anchor)

    # LOCAL-CUSTOM 절: 표준에 없는 내 절은 뒤에 붙임
    for anchor, sec in mine_secs.items():
        if anchor not in used:
            body_parts.append(sec["body"])
            stats["keep"] += 1

    new_text = "\n".join(part.rstrip("\n") for part in body_parts) + "\n"
    return new_text, stats


# ─── export-branch ─────────────────────────────────────────────────────────
def export_branch(mine_seed: Path, work_root: Path, today: str) -> Path:
    out_dir = work_root / f"seed-브랜치-{today}"
    if out_dir.exists():
        raise SystemExit(f"[씨드-업그레이드] 출력 폴더가 이미 있음: {out_dir}")
    out_dir.mkdir(parents=True)
    shutil.copy2(mine_seed, out_dir / "agentis.seed.md")

    txt = mine_seed.read_text(encoding="utf-8", errors="replace")
    header, _ = parse_sections(txt)
    vm = SEED_VERSION_RE.search(txt)
    ver = vm.group(1) if vm else "?"
    lm = LOCAL_MODS_RE.search(header)
    local_mods = lm.group(1).strip() if lm else "(없음 — 헤더 local-mods 가 비어있어요. §3-4 참고)"

    branch_md = f"""# 씨드 브랜치 — {today}

이 폴더는 **씨드(`.clinerules/agentis.md`) 자체의 브랜치 스냅샷**입니다.
메인 큐레이터에게 송신 → 다음 표준 씨드에 반영 검토.

## 출처
- 기반 표준 씨드 버전: v{ver}
- 사용자가 만진 절 (local-mods): {local_mods}
- 송신일: {today}

## 받는 사람(메인 큐레이터) 안내
- `agentis.seed.md` 를 표준 씨드와 절(§) 단위로 비교:
  ```
  python agentis/workflows/씨드-업그레이드.py --check --from <이폴더>/agentis.seed.md
  ```
- 좋은 보강(인터뷰 질문, 가드, 절차 등)은 다음 표준 씨드 릴리스에 반영.
- 개인 정보(이름·소속)는 씨드에는 보통 없지만, 사용자가 수동 입력했다면 마스킹 후 반영.

## 검토 체크리스트
- [ ] 절 추가가 일반화 가능한가? (특정 도메인 너무 한정?)
- [ ] 절 변경이 결정론·정확성 원칙과 일치하는가?
- [ ] 보안·외부유출 가드를 약화시키지 않는가?
- [ ] 다른 사용자의 기존 진화와 충돌하지 않는가?
"""
    (out_dir / "SEED-BRANCH.md").write_text(branch_md, encoding="utf-8")
    return out_dir


# ─── main ────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    here = Path(__file__).resolve()
    ap = argparse.ArgumentParser(description="씨드 절(§) 단위 비교·갱신·내보내기")
    ap.add_argument("--check", action="store_true", help="자기 씨드 vs 표준 씨드 절별 보고")
    ap.add_argument("--apply", action="store_true", help="plan.json 결정을 자기 씨드에 적용")
    ap.add_argument("--export-branch", action="store_true", help="자기 씨드를 브랜치 폴더로 묶기")
    ap.add_argument("--from", dest="from_path", type=Path, default=None, help="표준 씨드 파일 경로")
    ap.add_argument("--plan", type=Path, default=None, help="--apply 시 결정 파일 (plan.json)")
    ap.add_argument("--seed", type=Path, default=None, help="자기 씨드 경로 (기본: 자동 탐색)")
    ap.add_argument("--work-root", type=Path, default=None, help="작업 폴더 (기본: 자동 탐색)")
    ap.add_argument("--date", type=str, default=None, help="브랜치/백업 날짜 (기본: 오늘)")
    args = ap.parse_args(argv)

    today = args.date or _dt.date.today().isoformat()

    mine_seed = args.seed if (args.seed and args.seed.is_file()) else find_seed_file(here)
    if not mine_seed:
        print("[씨드-업그레이드] 자기 씨드(.clinerules / agentis.md)를 찾지 못했어요. --seed <경로> 로 지정하세요.", file=sys.stderr)
        return 2

    work_root = args.work_root.resolve() if args.work_root else mine_seed.parent.resolve()
    if work_root.name == ".clinerules":
        work_root = work_root.parent

    mine_text = mine_seed.read_text(encoding="utf-8", errors="replace")
    mine_ver_m = SEED_VERSION_RE.search(mine_text)
    mine_ver = mine_ver_m.group(1) if mine_ver_m else ""

    if args.export_branch:
        out = export_branch(mine_seed, work_root, today)
        print(f"[씨드-업그레이드] 씨드 브랜치 출력: {out}")
        print(f"[씨드-업그레이드] memory/log.md 에 한 줄: ## [{today}] seed | 씨드 브랜치 송신 (v{mine_ver or '?'})")
        return 0

    std_seed = find_standard_seed(work_root, args.from_path)
    if not std_seed:
        print("[씨드-업그레이드] 표준 씨드를 찾지 못했어요.", file=sys.stderr)
        print("  옵션 1) --from <경로> 로 직접 지정", file=sys.stderr)
        print("  옵션 2) 표준 씨드를 `<작업폴더>/.kit-mirror/seed/agentis.md` 로 다운로드 후 재실행", file=sys.stderr)
        print("  표준 씨드: https://github.com/imejaim/agentis/blob/main/seed/agentis.md", file=sys.stderr)
        return 2

    std_text = std_seed.read_text(encoding="utf-8", errors="replace")
    std_ver_m = SEED_VERSION_RE.search(std_text)
    std_ver = std_ver_m.group(1) if std_ver_m else ""

    _, mine_secs = parse_sections(mine_text)
    _, std_secs = parse_sections(std_text)

    if not std_secs:
        print("[씨드-업그레이드] 표준 씨드에 절 앵커(<!-- @section: N -->)가 없어요. v1.3+ 씨드만 지원합니다.", file=sys.stderr)
        return 2

    diff = diff_sections(mine_secs, std_secs)

    if args.apply:
        if not args.plan or not args.plan.is_file():
            print("[씨드-업그레이드] --apply 에는 --plan plan.json 이 필요합니다. 먼저 --check 로 템플릿을 만드세요.", file=sys.stderr)
            return 2
        try:
            plan = json.loads(args.plan.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[씨드-업그레이드] plan.json 파싱 실패: {e}", file=sys.stderr)
            return 2

        new_text, stats = apply_plan(mine_text, std_text, plan, work_root)

        # 백업
        agentis_dir = work_root / "agentis"
        backup_dir = (agentis_dir if agentis_dir.is_dir() else work_root) / ".kit-mirror" / "seed"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"backup-{today}.md"
        shutil.copy2(mine_seed, backup_path)

        mine_seed.write_text(new_text, encoding="utf-8")
        print(f"[씨드-업그레이드] 적용 완료. take {stats['take']} (new {stats['new']}) / keep {stats['keep']} / replace {stats['replace']} / skipped {stats['skipped']}")
        print(f"[씨드-업그레이드] 백업: {backup_path}")
        print(f"[씨드-업그레이드] 새 씨드: {mine_seed}  (v{mine_ver or '?'} → v{std_ver or '?'})")
        print(f"[씨드-업그레이드] memory/log.md 에 한 줄: ## [{today}] seed | upgrade v{mine_ver or '?'} → v{std_ver or '?'}")
        return 0

    # 기본: --check
    report = render_report(diff, mine_ver, std_ver)
    plan_template = render_plan_template(diff)
    report_path = work_root / "seed-upgrade-report.md"
    plan_path = work_root / "plan.json"
    report_path.write_text(report, encoding="utf-8")
    plan_path.write_text(json.dumps(plan_template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report)
    print()
    print(f"[씨드-업그레이드] 보고서: {report_path}")
    print(f"[씨드-업그레이드] plan.json 템플릿: {plan_path}")
    print(f"[씨드-업그레이드] 결정 후 실행: python {Path(__file__).name} --apply --plan {plan_path.name} --from {std_seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
