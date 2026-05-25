#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.5 / 사내깃-올리기.py
"""
사내깃-올리기 — agent.md 의 main_repo 필드가 설정된 에이전트를 사내 깃 레포로 내보낸다.

활성 조건: agent.md 에 'main_repo: <URL>' 가 있고 비어있지 않음.
           (없거나 비어있으면 안내 후 종료 — 에러 아님)

레벨 임계: agent-stats 기준 Level >= 5 이상이어야 자동 푸시 활성.

모드:
  --check      : 진단만 (변경 없음). main_repo 설정 여부 + 현재 Level + 마지막 푸시 시각.
  --init       : 첫 푸시 준비. main_repo 가 없으면 stdin 으로 입력받아 agent.md 에 기록.
                 새 레포 생성 안내 후 종료 (실제 push 없음).
  --push-prep  : 브랜치-내보내기 호출 → git init/add/commit/remote 설정.
                 사용자에게 push 명령 안내 (자동 push 없음).
  --push       : push-prep 절차 + git push -u origin main 까지 자동 수행.
                 성공 시 .last-push 기록 + memory/log.md 에 로그 추가.
  --auto       : Level 5 첫 도달 감지 시 큰 안내 출력 + .first-eligible 마커 생성.
                 cron / hook 용도.

표준 라이브러리만 (subprocess, pathlib, json, re, argparse). git 은 시스템에 있다고 가정.
사내망 가정 — 외부 git push 없음, 모든 것이 사내 git 으로만.
결정론적, 오프라인 OK (push 제외).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

# ── stdout/stderr utf-8 강제 ──────────────────────────────────────────────────
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# ── 상수 ─────────────────────────────────────────────────────────────────────
LEVEL_THRESHOLD = 5
LOG_HEADER_RE = re.compile(
    r"^##\s*\[(\d{4}-\d{2}-\d{2})\]\s*(\w+)\s*\|\s*(.+?)\s*$", re.MULTILINE
)
LAST_PUSH_FILE = ".last-push"
FIRST_ELIGIBLE_FILE = ".first-eligible"
URL_RE = re.compile(
    r"^https?://[^\s/$.?#].[^\s]*$|^git@[^\s:]+:[^\s]+\.git$", re.IGNORECASE
)


# ── 유틸 ─────────────────────────────────────────────────────────────────────

def find_root(start: Path) -> Path:
    """agentis/ 루트 (agent.md 가 있는 곳) 을 탐색해 반환."""
    p = (start if start.is_dir() else start.parent).resolve()
    for c in [p, *p.parents]:
        if (c / "agent.md").exists():
            return c
    return p


def parse_field(text: str, label: str) -> str:
    """- **{label}**: {value} 형태의 첫 줄에서 value 추출. 없으면 ''."""
    pat = re.compile(
        r"^[\-\*\s]*\*\*" + re.escape(label) + r"\*\*\s*[:：]\s*(.+?)\s*$",
        re.MULTILINE,
    )
    m = pat.search(text)
    if not m:
        return ""
    v = m.group(1).strip()
    # 주석이나 placeholder 면 비어있다고 간주
    if v.startswith("{{") or v.startswith("<!--") or v == "":
        return ""
    # 인라인 주석 제거 (<!-- ... -->)
    v = re.sub(r"<!--.*?-->", "", v).strip()
    return v


def parse_h1(text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip() if m else fallback


def have_git() -> bool:
    import shutil
    return shutil.which("git") is not None


def run_git(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        combined = (p.stdout or "") + (p.stderr or "")
        return p.returncode, combined
    except Exception as e:
        return 999, f"실행 실패: {e}"


# ── stats 계산 (agent-stats.py 의 핵심 로직을 인라인) ──────────────────────

def compute_level(root: Path) -> tuple[int, int]:
    """(level, xp) 반환. agent-stats.py 와 동일한 공식."""
    by_type: Counter[str] = Counter()
    tokens = 0

    log = root / "memory" / "log.md"
    if log.is_file():
        text = log.read_text(encoding="utf-8", errors="replace")
        for m in LOG_HEADER_RE.finditer(text):
            by_type[m.group(2).lower()] += 1
        for m in re.finditer(r"tokens?\s*[:=]\s*([\d,]+)", text, re.IGNORECASE):
            tokens += int(m.group(1).replace(",", ""))

    task = by_type.get("task", 0)
    ingest = by_type.get("ingest", 0)
    skill = by_type.get("skill", 0)
    lint = by_type.get("lint", 0)

    xp = task * 100 + ingest * 200 + skill * 500 + lint * 300 + (tokens // 1000)
    level = int(math.sqrt(xp) / 4) if xp > 0 else 0
    return level, xp


def level_progress_pct(xp: int, level: int) -> int:
    """현재 레벨 내 진행률 (0~100)."""
    if level <= 0:
        # 다음 레벨(1)에 필요한 XP: (4*(1))^2 = 16
        next_xp = 16
        return min(100, int(xp / next_xp * 100))
    cur_xp = (4 * level) ** 2
    next_xp = (4 * (level + 1)) ** 2
    span = next_xp - cur_xp
    if span <= 0:
        return 100
    return min(100, int((xp - cur_xp) / span * 100))


def read_last_push(root: Path) -> str:
    """agentis/.last-push 내용 읽기. 없으면 빈 문자열."""
    p = root / LAST_PUSH_FILE
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="replace").strip()
    return ""


def write_last_push(root: Path, sha: str) -> None:
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    content = json.dumps({"ts": ts, "sha": sha}, ensure_ascii=False)
    (root / LAST_PUSH_FILE).write_text(content + "\n", encoding="utf-8")


def append_log(root: Path, agent_name: str, level: int, repo_url: str) -> None:
    """memory/log.md 에 push 로그 한 줄 추가 (맨 위 삽입)."""
    log_path = root / "memory" / "log.md"
    today = _dt.date.today().isoformat()
    new_line = (
        f"\n## [{today}] push | {agent_name} Level {level} 사내 깃 푸시 ({repo_url})\n"
    )
    if log_path.is_file():
        original = log_path.read_text(encoding="utf-8", errors="replace")
        # 헤더(첫 줄 # 로그 등) 다음, 첫 ## 항목 위에 삽입
        # 구분선('---') 이후 첫 번째 ## 앞에 넣는다
        sep = "---"
        idx = original.find(sep)
        if idx != -1:
            insert_at = idx + len(sep)
            updated = original[:insert_at] + new_line + original[insert_at:]
        else:
            updated = new_line + original
        log_path.write_text(updated, encoding="utf-8")
    else:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        header = "# 로그\n\n새 항목은 맨 위에.\n\n---\n"
        log_path.write_text(header + new_line, encoding="utf-8")


def validate_url(url: str) -> bool:
    return bool(URL_RE.match(url))


def set_main_repo(root: Path, url: str) -> None:
    """agent.md 의 main_repo 필드 값을 url 로 업데이트."""
    agent_path = root / "agent.md"
    text = agent_path.read_text(encoding="utf-8", errors="replace")

    # 패턴 1: - **main_repo**: <anything>  (인라인 주석 포함)
    pat1 = re.compile(
        r"^([\-\*\s]*\*\*main_repo\*\*\s*[:：]\s*).*$", re.MULTILINE
    )
    # 패턴 2: main_repo: <anything>
    pat2 = re.compile(r"^(main_repo\s*[:：]\s*).*$", re.MULTILINE)

    if pat1.search(text):
        new_text = pat1.sub(r"\g<1>" + url, text, count=1)
    elif pat2.search(text):
        new_text = pat2.sub(r"\g<1>" + url, text, count=1)
    else:
        # 필드 자체가 없으면 한 줄 목적 바로 아래에 추가
        new_text = text.rstrip() + f"\n- **main_repo**: {url}\n"

    agent_path.write_text(new_text, encoding="utf-8")


# ── 모드 구현 ─────────────────────────────────────────────────────────────────

def mode_check(root: Path) -> int:
    """변경 없이 현재 상태를 진단한다."""
    agent_path = root / "agent.md"
    if not agent_path.is_file():
        print(f"[사내깃] agent.md 를 찾을 수 없음: {root}", file=sys.stderr)
        return 2

    agent_text = agent_path.read_text(encoding="utf-8", errors="replace")
    agent_name = parse_h1(agent_text, root.name)
    main_repo = parse_field(agent_text, "main_repo")

    print(f"[사내깃] 에이전트: {agent_name}")

    # main_repo 체크
    if not main_repo:
        print(
            "[사내깃] main_repo 미설정 — 사내 깃이 생기면 agent.md 의 main_repo: 필드에 URL 박으세요."
        )
        print("         `python workflows/사내깃-올리기.py --init` 으로 URL 을 지금 입력할 수도 있습니다.")
        return 0

    print(f"[사내깃] main_repo : {main_repo}")

    # 레벨 체크
    level, xp = compute_level(root)
    pct = level_progress_pct(xp, level)

    if level < LEVEL_THRESHOLD:
        print(
            f"[사내깃] 현재 Level {level} (XP {xp:,}) — "
            f"Level {LEVEL_THRESHOLD} 이상이 되면 자동 푸시 활성화됩니다. "
            f"(현재 {pct}% 진행)"
        )
    else:
        print(
            f"[사내깃] 현재 Level {level} (XP {xp:,}) — "
            f"푸시 준비됨. `--push-prep` 또는 `--push` 로 진행하세요."
        )

    # 마지막 푸시 시각
    last = read_last_push(root)
    if last:
        try:
            info = json.loads(last)
            print(f"[사내깃] 마지막 푸시: {info.get('ts', '?')}  (SHA: {info.get('sha', '?')})")
        except Exception:
            print(f"[사내깃] 마지막 푸시 기록: {last}")
    else:
        print("[사내깃] 마지막 푸시: 없음 (아직 한 번도 푸시하지 않았어요)")

    return 0


def mode_init(root: Path) -> int:
    """첫 푸시 준비. main_repo 없으면 stdin 으로 입력받아 agent.md 에 기록."""
    agent_path = root / "agent.md"
    if not agent_path.is_file():
        print(f"[사내깃] agent.md 를 찾을 수 없음: {root}", file=sys.stderr)
        return 2

    agent_text = agent_path.read_text(encoding="utf-8", errors="replace")
    agent_name = parse_h1(agent_text, root.name)
    main_repo = parse_field(agent_text, "main_repo")

    print(f"[사내깃] 에이전트: {agent_name}")

    if main_repo:
        print(f"[사내깃] main_repo 이미 설정됨: {main_repo}")
        print("         변경하려면 agent.md 를 직접 편집하거나 이 스크립트를 다시 실행하세요.")
        return 0

    # URL 입력 받기
    print(
        "[사내깃] 사내 깃 URL 을 입력하세요."
    )
    print(
        f"         예: https://gitlab.company.com/team/{agent_name}.git"
    )
    try:
        url = input("사내 깃 URL? ").strip()
    except EOFError:
        print("[사내깃] 입력이 없습니다. 종료합니다.", file=sys.stderr)
        return 1

    if not url:
        print("[사내깃] URL 이 비어있습니다. 종료합니다.", file=sys.stderr)
        return 1

    if not validate_url(url):
        print(
            f"[사내깃] URL 형식이 올바르지 않습니다: {url!r}",
            file=sys.stderr,
        )
        print(
            "         유효한 형식 예시: https://gitlab.company.com/team/agent.git",
            file=sys.stderr,
        )
        return 1

    # agent.md 에 URL 기록
    set_main_repo(root, url)
    print(f"[사내깃] agent.md 에 main_repo: {url}  을 기록했습니다.")
    print()
    print("[사내깃] 다음 단계:")
    print("  1) 사내 깃 관리자에게 새 레포 생성 요청이 필요할 수 있습니다.")
    print(f"     레포 이름 예시: {agent_name}  (또는 팀 규칙에 따라)")
    print("  2) 레포가 만들어졌다면 `python workflows/사내깃-올리기.py --push-prep` 으로 진행하세요.")

    return 0


def mode_push_prep(root: Path) -> int:
    """브랜치-내보내기 호출 + git init/add/commit/remote 설정 + 사용자에게 push 명령 안내."""
    agent_path = root / "agent.md"
    if not agent_path.is_file():
        print(f"[사내깃] agent.md 를 찾을 수 없음: {root}", file=sys.stderr)
        return 2

    agent_text = agent_path.read_text(encoding="utf-8", errors="replace")
    agent_name = parse_h1(agent_text, root.name)
    main_repo = parse_field(agent_text, "main_repo")

    if not main_repo:
        print("[사내깃] main_repo 미설정. 먼저 `--init` 을 실행하세요.", file=sys.stderr)
        return 1

    level, xp = compute_level(root)
    print(f"[사내깃] 에이전트: {agent_name}  Level {level} (XP {xp:,})")
    print(f"[사내깃] main_repo : {main_repo}")

    # 브랜치-내보내기 호출
    here = Path(__file__).resolve().parent
    export_script = here / "브랜치-내보내기.py"
    if not export_script.is_file():
        print(
            f"[사내깃] 브랜치-내보내기.py 를 찾을 수 없음: {export_script}",
            file=sys.stderr,
        )
        print("         키트에서 workflows/브랜치-내보내기.py 를 받아 두세요.", file=sys.stderr)
        return 2

    today = _dt.date.today().isoformat()
    bundle_name = f"{agent_name}-브랜치-{today}"
    out_parent = root.parent

    print(f"[사내깃] 브랜치-내보내기 실행 중...")
    try:
        result = subprocess.run(
            [sys.executable, str(export_script), "--root", str(root), "--out", str(out_parent)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
        if result.returncode not in (0, 1):
            # returncode=1 은 경고(누출 감지)이므로 진행 가능
            print(f"[사내깃] 브랜치-내보내기 실패 (종료 코드 {result.returncode})", file=sys.stderr)
            return result.returncode
    except Exception as e:
        print(f"[사내깃] 브랜치-내보내기 실행 중 오류: {e}", file=sys.stderr)
        return 2

    bundle_dir = out_parent / bundle_name
    if not bundle_dir.is_dir():
        print(f"[사내깃] 브랜치 폴더를 찾을 수 없음: {bundle_dir}", file=sys.stderr)
        return 2

    # git init + add + commit
    if not have_git():
        print("[사내깃] 'git' 이 설치돼 있어야 합니다.", file=sys.stderr)
        return 2

    print(f"\n[사내깃] git 초기화: {bundle_dir}")
    rc, out = run_git(["git", "init"], cwd=bundle_dir)
    if rc != 0:
        print(f"[사내깃] git init 실패:\n{out}", file=sys.stderr)
        return 2

    rc, out = run_git(["git", "add", "."], cwd=bundle_dir)
    if rc != 0:
        print(f"[사내깃] git add 실패:\n{out}", file=sys.stderr)
        return 2

    commit_msg = f"Agent: {agent_name} Level {level} baseline"
    rc, out = run_git(
        ["git", "commit", "-m", commit_msg], cwd=bundle_dir
    )
    if rc != 0:
        print(f"[사내깃] git commit 실패:\n{out}", file=sys.stderr)
        return 2
    print(f"[사내깃] git commit 완료: {commit_msg!r}")

    # remote origin 설정
    rc, _ = run_git(["git", "remote", "get-url", "origin"], cwd=bundle_dir)
    if rc == 0:
        # 이미 origin 있으면 set-url
        run_git(["git", "remote", "set-url", "origin", main_repo], cwd=bundle_dir)
        print(f"[사내깃] git remote set-url origin → {main_repo}")
    else:
        run_git(["git", "remote", "add", "origin", main_repo], cwd=bundle_dir)
        print(f"[사내깃] git remote add origin → {main_repo}")

    print()
    print("[사내깃] 푸시 준비됨. 다음 명령으로 푸시하세요:")
    print(f"  cd \"{bundle_dir}\"")
    print(f"  git push -u origin main")
    print()
    print("  (자동 푸시를 원하면: python workflows/사내깃-올리기.py --push)")

    return 0


def mode_push(root: Path) -> int:
    """push-prep 절차 + git push -u origin main 까지 자동 수행."""
    agent_path = root / "agent.md"
    if not agent_path.is_file():
        print(f"[사내깃] agent.md 를 찾을 수 없음: {root}", file=sys.stderr)
        return 2

    agent_text = agent_path.read_text(encoding="utf-8", errors="replace")
    agent_name = parse_h1(agent_text, root.name)
    main_repo = parse_field(agent_text, "main_repo")

    if not main_repo:
        print("[사내깃] main_repo 미설정. 먼저 `--init` 을 실행하세요.", file=sys.stderr)
        return 1

    level, xp = compute_level(root)

    # push-prep 과 동일한 절차 (내부 호출)
    rc = mode_push_prep(root)
    if rc not in (0, 1):
        return rc

    today = _dt.date.today().isoformat()
    bundle_name = f"{agent_name}-브랜치-{today}"
    bundle_dir = root.parent / bundle_name

    if not bundle_dir.is_dir():
        print(f"[사내깃] 브랜치 폴더를 찾을 수 없음: {bundle_dir}", file=sys.stderr)
        return 2

    print(f"\n[사내깃] git push 시도: {main_repo}")
    push_rc, push_out = run_git(
        ["git", "push", "-u", "origin", "main"], cwd=bundle_dir
    )

    if push_rc != 0:
        print(f"[사내깃] push 실패 (종료 코드 {push_rc}):", file=sys.stderr)
        print(push_out, file=sys.stderr)
        print()
        print("[사내깃] 트러블슈팅:")
        print("  · 인증 오류 → 사내 깃 토큰/SSH 키 확인 (`git config` / OS 인증서)")
        print("  · 권한 오류 → 관리자에게 레포 접근 권한 요청")
        print("  · 네트워크 오류 → VPN/프록시 연결 확인")
        return push_rc

    # SHA 추출
    sha_rc, sha_out = run_git(
        ["git", "rev-parse", "--short", "HEAD"], cwd=bundle_dir
    )
    sha = sha_out.strip() if sha_rc == 0 else "unknown"

    # .last-push 기록
    write_last_push(root, sha)
    print(f"[사내깃] .last-push 기록 완료 (SHA: {sha})")

    # memory/log.md 에 로그 추가
    append_log(root, agent_name, level, main_repo)
    print(f"[사내깃] memory/log.md 에 push 로그 추가 완료")

    print(f"\n[사내깃] 푸시 완료! {agent_name} Level {level} → {main_repo}")
    return 0


def mode_auto(root: Path) -> int:
    """Level 5 첫 도달 감지 + .first-eligible 마커 생성. cron/hook 용도."""
    agent_path = root / "agent.md"
    if not agent_path.is_file():
        return 0  # 에이전트 없으면 조용히 종료

    agent_text = agent_path.read_text(encoding="utf-8", errors="replace")
    agent_name = parse_h1(agent_text, root.name)

    level, xp = compute_level(root)

    if level < LEVEL_THRESHOLD:
        # 레벨 미달 — 아무것도 하지 않음 (cron 용도이므로 조용히)
        return 0

    first_eligible_path = root / FIRST_ELIGIBLE_FILE
    if first_eligible_path.is_file():
        # 이미 안내했음 — 재알림 방지
        return 0

    # 첫 도달 — 안내 + 마커 생성
    print("=" * 60)
    print(f"  에이전트 {agent_name} 이(가) Level {LEVEL_THRESHOLD} 에 도달했어요!")
    print(f"  동료와 공유할 수 있는 수준입니다.")
    print()
    print(f"  사내 깃에 올리려면:")
    print(f"  python workflows/사내깃-올리기.py --init")
    print("=" * 60)

    first_eligible_path.write_text(
        _dt.datetime.now().isoformat(timespec="seconds") + "\n",
        encoding="utf-8",
    )

    return 0


# ── 진입점 ────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    here = Path(__file__).resolve().parent  # agentis/workflows/
    ap = argparse.ArgumentParser(
        description="사내 깃 레포로 에이전트를 올리는 워크플로우 (main_repo 필드가 있을 때만 활성)"
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=here.parent,
        help="agentis 디렉토리 (기본: 스크립트 기준 ../)",
    )
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="진단만 (변경 없음)")
    group.add_argument(
        "--init",
        action="store_true",
        help="첫 푸시 준비: main_repo URL 입력 + agent.md 기록",
    )
    group.add_argument(
        "--push-prep",
        action="store_true",
        help="브랜치 폴더 생성 + git 준비 + push 명령 안내 (자동 push 없음)",
    )
    group.add_argument(
        "--push",
        action="store_true",
        help="push-prep + git push 자동 수행",
    )
    group.add_argument(
        "--auto",
        action="store_true",
        help="Level 5 첫 도달 감지 및 안내 (cron/hook 용도)",
    )
    args = ap.parse_args(argv)

    root = find_root(args.root)

    if args.check:
        return mode_check(root)
    if args.init:
        return mode_init(root)
    if args.push_prep:
        return mode_push_prep(root)
    if args.push:
        return mode_push(root)
    if args.auto:
        return mode_auto(root)

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
