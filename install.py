#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agentis-installer v1.6 — Agentis 결정론 설치기

사내 동료 설치 안내:
  python install.py --target <내 작업 폴더 절대 경로>
  또는
  더블클릭: install.bat (Windows) / ./install.sh (Mac/Linux)

이 스크립트는 정확히 다음만 합니다:
  1) <target>/.clinerules/agentis.md 복사
  2) (--kit, 기본 ON) <target>/agentis/ 에 키트 복사

추가 작업(git push, 네트워크 요청, agentis/ 내부 파일 자동 편집 등) 은 하지 않습니다.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import shutil
import sys
from pathlib import Path

# Windows 콘솔(cp949) 에서도 한글·이모지가 깨지지 않도록 stdout/stderr 를 UTF-8 로.
# Python 3.7+ 의 TextIOWrapper.reconfigure 를 사용. 실패해도 무시 (출력만 안 깨지면 됨).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

SEED_RELATIVE = Path(".clinerules") / "agentis.md"
KIT_RELATIVE = Path("kit") / "agentis-template"
TARGET_KIT_DIRNAME = "agentis"

EXIT_OK = 0
EXIT_BAD_ARGS = 2
EXIT_BAD_SOURCE = 3
EXIT_BAD_TARGET = 4
EXIT_ALREADY_INSTALLED = 5
EXIT_VERIFY_FAILED = 6


# ---------------------------------------------------------------------------
# 보조 함수
# ---------------------------------------------------------------------------

def _is_quiet(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "quiet", False))


def _print(msg: str, *, args: argparse.Namespace, force: bool = False) -> None:
    if force or not _is_quiet(args):
        print(msg)


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _human_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.2f} MB"


def _count_files(root: Path) -> int:
    return sum(1 for p in root.rglob("*") if p.is_file())


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%dT%H%M%S")


# ---------------------------------------------------------------------------
# 인자 파싱
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="install.py",
        description="Agentis 결정론 설치기 (씨드 + 키트 복사 전용).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "예시:\n"
            "  python install.py --target \"C:\\내작업\\프로젝트A\"\n"
            "  python install.py --here\n"
            "  python install.py --target /Users/me/work --no-kit\n"
            "  python install.py --target ./work --dry-run\n"
        ),
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--target",
        type=str,
        default=None,
        help="설치 대상 작업 폴더 (절대 경로 권장).",
    )
    group.add_argument(
        "--here",
        action="store_true",
        help="현재 디렉토리에 설치합니다 (--target 와 상호배타).",
    )
    kit_group = p.add_mutually_exclusive_group()
    kit_group.add_argument(
        "--kit",
        dest="kit",
        action="store_true",
        help="키트도 함께 설치합니다 (기본 ON).",
    )
    kit_group.add_argument(
        "--no-kit",
        dest="kit",
        action="store_false",
        help="키트 설치를 끄고 룰만 설치합니다.",
    )
    p.set_defaults(kit=True)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="변경 없이 무엇이 만들어질지 보고만 합니다.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="기존 .clinerules/agentis.md 가 있으면 백업 후 덮어씁니다.",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="출력 최소화.",
    )
    return p


# ---------------------------------------------------------------------------
# 검증 단계
# ---------------------------------------------------------------------------

def resolve_target(args: argparse.Namespace) -> Path:
    if args.here:
        return Path(os.getcwd()).resolve()
    raw = args.target
    if raw is None or not raw.strip():
        _err("❌ --target 또는 --here 중 하나가 필요합니다.")
        sys.exit(EXIT_BAD_ARGS)
    return Path(raw).expanduser().resolve()


def check_source(installer_dir: Path, want_kit: bool) -> tuple[Path, Path | None]:
    seed_src = installer_dir / SEED_RELATIVE
    kit_src = installer_dir / KIT_RELATIVE
    if not seed_src.is_file():
        _err(
            "❌ 인스톨러가 잘못된 위치에 있는 것 같습니다.\n"
            f"   기대 경로: {seed_src}\n"
            "   agent_seed 레포 루트에서 실행해주세요."
        )
        sys.exit(EXIT_BAD_SOURCE)
    if want_kit and not kit_src.is_dir():
        _err(
            "❌ 인스톨러가 잘못된 위치에 있는 것 같습니다.\n"
            f"   기대 경로: {kit_src}\n"
            "   agent_seed 레포 루트에서 실행해주세요. (또는 --no-kit 로 룰만 설치)"
        )
        sys.exit(EXIT_BAD_SOURCE)
    return seed_src, (kit_src if want_kit else None)


def check_target(target: Path) -> None:
    if not target.exists():
        _err(
            f"❌ 대상 폴더 '{target}' 가 존재하지 않습니다.\n"
            "   먼저 해당 폴더를 만들거나, 다른 폴더를 --target 으로 지정해주세요.\n"
            "   예: python install.py --target \"C:\\내작업\\프로젝트A\""
        )
        sys.exit(EXIT_BAD_TARGET)
    if not target.is_dir():
        _err(f"❌ 대상 경로 '{target}' 가 폴더가 아닙니다.")
        sys.exit(EXIT_BAD_TARGET)


def check_existing_seed(target: Path, force: bool, dry_run: bool) -> Path | None:
    """이미 설치된 씨드를 발견하면 백업 경로(또는 None)를 돌려준다."""
    target_seed = target / SEED_RELATIVE
    if not target_seed.exists():
        return None
    if not force:
        _err(
            "❌ 이미 설치되어 있어요.\n"
            f"   발견: {target_seed}\n"
            "   업그레이드라면 `python agentis/workflows/씨드-업그레이드.py --check` 를 쓰세요.\n"
            "   덮어쓰려면 --force 를 추가하세요 (백업 후 덮어씁니다)."
        )
        sys.exit(EXIT_ALREADY_INSTALLED)
    backup = target_seed.with_name(f"agentis.md.backup-{_timestamp()}")
    if dry_run:
        return backup
    shutil.copy2(target_seed, backup)
    return backup


# ---------------------------------------------------------------------------
# 설치 단계
# ---------------------------------------------------------------------------

def install_seed(seed_src: Path, target: Path, dry_run: bool) -> Path:
    target_seed = target / SEED_RELATIVE
    if dry_run:
        return target_seed
    target_seed.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(seed_src, target_seed)
    return target_seed


def install_kit(kit_src: Path, target: Path, dry_run: bool) -> tuple[Path, bool]:
    """returns (kit_dst, skipped)"""
    kit_dst = target / TARGET_KIT_DIRNAME
    if kit_dst.exists():
        return kit_dst, True
    if dry_run:
        return kit_dst, False
    shutil.copytree(kit_src, kit_dst)
    return kit_dst, False


# ---------------------------------------------------------------------------
# 검증 (실행 후)
# ---------------------------------------------------------------------------

def verify_installation(
    seed_src: Path,
    target_seed: Path,
    kit_src: Path | None,
    kit_dst: Path | None,
    kit_skipped: bool,
) -> None:
    if not target_seed.is_file():
        _err(f"❌ 검증 실패: {target_seed} 가 만들어지지 않았습니다.")
        sys.exit(EXIT_VERIFY_FAILED)
    src_hash = _sha256(seed_src)
    dst_hash = _sha256(target_seed)
    if src_hash != dst_hash:
        _err(
            "❌ 검증 실패: 복사된 씨드의 sha256 이 원본과 다릅니다.\n"
            f"   원본: {src_hash}\n"
            f"   복사: {dst_hash}"
        )
        sys.exit(EXIT_VERIFY_FAILED)
    if kit_src is not None and kit_dst is not None and not kit_skipped:
        if not kit_dst.is_dir():
            _err(f"❌ 검증 실패: 키트 폴더 {kit_dst} 가 만들어지지 않았습니다.")
            sys.exit(EXIT_VERIFY_FAILED)
        src_count = _count_files(kit_src)
        dst_count = _count_files(kit_dst)
        if dst_count < src_count:
            _err(
                "❌ 검증 실패: 키트 파일 수가 원본보다 적습니다.\n"
                f"   원본 {src_count} 파일 vs 복사 {dst_count} 파일"
            )
            sys.exit(EXIT_VERIFY_FAILED)


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------

def print_success(
    args: argparse.Namespace,
    target: Path,
    target_seed: Path,
    seed_src: Path,
    kit_dst: Path | None,
    kit_src: Path | None,
    kit_skipped: bool,
    backup: Path | None,
    dry_run: bool,
) -> None:
    title = "🔎 Dry-run 결과 (실제로는 아무것도 만들어지지 않았습니다)" if dry_run else "✅ Agentis 설치 완료"
    seed_size = seed_src.stat().st_size
    seed_line = f"   ├── .clinerules/agentis.md ({_human_size(seed_size)})"
    kit_line = ""
    if kit_src is not None:
        kit_file_count = _count_files(kit_src)
        if kit_skipped and not dry_run:
            kit_line = (
                f"   └── agentis/ (이미 존재 → 건너뜀, {kit_file_count} 파일)"
            )
        else:
            kit_line = f"   └── agentis/ ({kit_file_count} 파일)"
    else:
        seed_line = f"   └── .clinerules/agentis.md ({_human_size(seed_size)})"

    lines = [
        "",
        title,
        "",
        f"📂 설치 위치: {target}",
        seed_line,
    ]
    if kit_line:
        lines.append(kit_line)
    if backup is not None:
        lines += ["", f"💾 기존 씨드를 백업했습니다: {backup.name}"]
    if kit_src is not None and kit_skipped and not dry_run:
        lines += [
            "",
            "ℹ️  agentis/ 폴더가 이미 있어요.",
            "   키트 업데이트는 `python agentis/workflows/씨드-업그레이드.py --check`",
            "   또는 키트 폴더 통째 백업 후 다시 install.py 를 쓰세요.",
        ]
    lines += [
        "",
        "🎯 다음 단계:",
        f"   1. VS Code 에서 이 폴더({target})를 엽니다.",
        "   2. Cline (또는 사내 cline SR) 대화창에 「안녕」 이라고만 입력합니다.",
        "   3. 에이전트가 자기 이름·주요 업무를 함께 정하자고 인터뷰를 시작합니다.",
        "",
        "💡 Tip: cline 대화창에 \"agentis/README.md 한 번 읽어줘\" 라고 하면 사용법 안내를 자세히 받을 수 있어요.",
        "",
    ]
    _print("\n".join(lines), args=args, force=True)


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    installer_dir = Path(__file__).resolve().parent
    target = resolve_target(args)
    seed_src, kit_src = check_source(installer_dir, want_kit=args.kit)
    check_target(target)
    backup = check_existing_seed(target, force=args.force, dry_run=args.dry_run)

    _print(
        f"📦 인스톨러 위치: {installer_dir}\n📁 대상 폴더: {target}",
        args=args,
    )
    if args.dry_run:
        _print("⚙️  --dry-run: 실제 파일은 만들어지지 않습니다.", args=args)

    target_seed = install_seed(seed_src, target, dry_run=args.dry_run)
    kit_dst: Path | None = None
    kit_skipped = False
    if kit_src is not None:
        kit_dst, kit_skipped = install_kit(kit_src, target, dry_run=args.dry_run)

    if not args.dry_run:
        verify_installation(
            seed_src=seed_src,
            target_seed=target_seed,
            kit_src=kit_src,
            kit_dst=kit_dst,
            kit_skipped=kit_skipped,
        )

    print_success(
        args=args,
        target=target,
        target_seed=target_seed,
        seed_src=seed_src,
        kit_dst=kit_dst,
        kit_src=kit_src,
        kit_skipped=kit_skipped,
        backup=backup,
        dry_run=args.dry_run,
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
