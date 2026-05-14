#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.3 / 메인-동기화
"""
메인-동기화 — agent.md 의 main_repo URL 을 통해 내 에이전트를 사내 메인과 동기화한다.

활성 조건: agent.md 에 'main_repo: <URL>' 가 들어있고 비어있지 않음. 없으면 graceful exit.

모드:
  --check       : 메인 클론 → 디프 요약 (브랜치-비교 호출)
  --pull        : 메인 클론 → 팩처럼 취급 → 팩-병합 호출 (기본 plan-only)
  --push-prep   : 브랜치-내보내기 호출 후 메인 레포 클론 폴더 + git 명령 가이드 출력
  --repo-subpath: 메인 레포 안에서 agent.md 가 있는 서브경로 (기본: 루트)

git 이 설치돼 있어야 함. 사내 인증은 사용자 환경 그대로 사용 (스크립트가 자격 증명 다루지 않음).
"""
from __future__ import annotations
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def find_root(start: Path) -> Path:
    p = (start if start.is_dir() else start.parent).resolve()
    for c in [p, *p.parents]:
        if (c / "agent.md").exists():
            return c
    return p


def parse_main_repo(agent_md_path: Path) -> str:
    if not agent_md_path.is_file():
        return ""
    text = agent_md_path.read_text(encoding="utf-8", errors="replace")
    # '- **main_repo**: <url>' 또는 'main_repo: <url>' 둘 다
    for pat in (
        r"^[\-\*\s]*\*\*main_repo\*\*\s*[:：]\s*(\S+)",
        r"^main_repo\s*[:：]\s*(\S+)",
    ):
        m = re.search(pat, text, re.MULTILINE)
        if m:
            v = m.group(1).strip()
            # frontmatter 가 아닌 본문 placeholder({{...}}) 면 비어있다고 간주
            if v.startswith("{{") or v.startswith("<!--") or v == "":
                return ""
            return v
    return ""


def have_git() -> bool:
    return shutil.which("git") is not None


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 999, f"실행 실패: {e}"


def clone_main(url: str, dest: Path) -> tuple[bool, str]:
    code, out = run(["git", "clone", "--depth", "1", url, str(dest)])
    if code != 0:
        return False, out
    return True, out


def locate_main_root(clone_dir: Path, subpath: str) -> Path | None:
    """클론된 메인 안에서 agent.md 위치 찾기.
       1) --repo-subpath 지정되면 거기
       2) 클론 루트
       3) 클론 루트/agentis
       4) 클론 루트의 최근 *-브랜치-*/fork/
    """
    candidates: list[Path] = []
    if subpath:
        candidates.append(clone_dir / subpath)
    candidates += [clone_dir, clone_dir / "agentis"]
    branches = sorted([p for p in clone_dir.glob("*-브랜치-*") if p.is_dir()], reverse=True)
    for b in branches:
        candidates.append(b / "fork")
    for c in candidates:
        if (c / "agent.md").is_file() or (c / "memory").is_dir() or (c / "skills").is_dir():
            return c
    return None


def call_inline(script_name: str, root: Path, args: list[str]) -> int:
    """같은 workflows 폴더의 다른 스크립트를 호출."""
    here = Path(__file__).resolve().parent
    target = here / script_name
    if not target.is_file():
        print(f"[메인] 같은 폴더에 {script_name} 가 없음. 키트에서 받아 두세요.", file=sys.stderr)
        return 2
    code, out = run([sys.executable, str(target), *args])
    if out:
        print(out, end="" if out.endswith("\n") else "\n")
    return code


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="메인 에이전트 레포와 동기화")
    ap.add_argument("--root", type=Path, default=here.parent, help="내 agentis 경로 (기본: 스크립트 기준 ../)")
    ap.add_argument("--mode", choices=["check", "pull", "push-prep"], required=False)
    ap.add_argument("--check", dest="mode", action="store_const", const="check")
    ap.add_argument("--pull", dest="mode", action="store_const", const="pull")
    ap.add_argument("--push-prep", dest="mode", action="store_const", const="push-prep")
    ap.add_argument("--repo-subpath", default="", help="메인 레포 안에서 agent.md 가 있는 서브경로")
    ap.add_argument("--strategy", default="plan-only", choices=["plan-only", "overwrite", "keep-mine", "rename-incoming"])
    args = ap.parse_args(argv)
    if not args.mode:
        ap.error("--check / --pull / --push-prep 중 하나를 지정하세요")

    root = find_root(args.root)
    main_repo = parse_main_repo(root / "agent.md")
    if not main_repo:
        print("[메인] agent.md 에 main_repo 가 설정돼 있지 않아요. 메인 기능은 비활성 상태입니다.")
        print("       활성화하려면 agent.md 의 'main_repo' 값에 사내 메인 레포 URL 을 넣으세요. (예: https://github.com/사내/agentis-main-...) ")
        return 0
    if not have_git():
        print("[메인] 'git' 이 설치돼 있어야 합니다. (Path 에 잡혀있어야 함)", file=sys.stderr)
        return 2

    print(f"[메인] 내 agentis: {root}")
    print(f"[메인] main_repo : {main_repo}")
    print(f"[메인] 모드: {args.mode}")

    if args.mode == "push-prep":
        # 브랜치-내보내기 호출 — 내 작업폴더 부모에 만들어짐
        rc = call_inline("브랜치-내보내기.py", root, ["--root", str(root)])
        print()
        print("[메인] 푸시 가이드:")
        print(f"  1) 메인 레포를 자기 권한으로 클론:  git clone {main_repo} <어디>")
        print(f"  2) 방금 만들어진 브랜치 폴더(`<이름>-브랜치-YYYY-MM-DD/fork/`) 안에서 채택할 변경만")
        print(f"     클론한 메인 레포에 복사하거나 reset 처리.")
        print(f"  3) cd <클론한 메인 레포>;  git add . ;  git commit -m '<설명>' ;  git push")
        print(f"     (실제 push 는 자기 권한으로 수행 — 스크립트가 자동으로 하지 않음)")
        return rc

    # check / pull 은 클론이 필요함
    with tempfile.TemporaryDirectory(prefix="agentis-main-") as tmp:
        clone_dir = Path(tmp) / "main"
        ok, out = clone_main(main_repo, clone_dir)
        if not ok:
            print(f"[메인] 클론 실패:\n{out}", file=sys.stderr)
            print(f"[메인] 가이드: ① 네트워크/프록시 확인 ② 사내 인증서/토큰 확인 (`git config --global` / OS 인증서 저장소)")
            return 2
        main_root = locate_main_root(clone_dir, args.repo_subpath)
        if main_root is None:
            print(f"[메인] 클론한 레포에서 agent.md 또는 skills/memory 폴더를 찾지 못함. --repo-subpath 로 위치 지정 필요.", file=sys.stderr)
            return 2
        print(f"[메인] 클론 OK → 메인 루트: {main_root}")

        if args.mode == "check":
            return call_inline("브랜치-비교.py", root, [str(root), str(main_root)])

        if args.mode == "pull":
            # 메인 루트를 pack 처럼 만들어 팩-병합에 전달.
            # 간단: skills/, workflows/, memory/concepts/ 를 그대로 사용 (pack 폴더 구조와 동일).
            pack_like = Path(tmp) / "pack"
            (pack_like).mkdir()
            for sub in ("skills", "workflows"):
                src = main_root / sub
                if src.is_dir():
                    shutil.copytree(src, pack_like / sub)
            cs = main_root / "memory" / "concepts"
            if cs.is_dir():
                shutil.copytree(cs, pack_like / "memory" / "concepts")
            # pack.meta.md
            (pack_like / "pack.meta.md").write_text(
                f"---\norigin: 메인({main_repo})\n---\n# 메인에서 가져온 팩\n",
                encoding="utf-8"
            )
            return call_inline("팩-병합.py", root, ["--root", str(root), "--pack", str(pack_like),
                                                    "--strategy", args.strategy])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
