#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agentis-installer v1.10 — Agentis 결정론 설치기

사내 동료 설치 안내:
  python install.py --target <내 작업 폴더 절대 경로>
  또는
  더블클릭: install.bat (Windows) / ./install.sh (Mac/Linux)

이 스크립트는 정확히 다음만 합니다:
  1) <target>/.clinerules/agentis.md 복사
  2) <target>/.clinerules/10-agent-routing.md 에 자연어→workflow 라우팅 룰 복사
  3) <target>/.clinerules/workflows/ 에 Cline 하네스가 직접 읽는 표준 워크플로우 룰 복사
  4) (--kit, 기본 ON) <target>/agentis/ 에 키트 복사

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
ROUTING_SOURCE_RELATIVE = Path("seed") / "10-agent-routing.md"
ROUTING_RULE_RELATIVE = Path(".clinerules") / "10-agent-routing.md"
RULE_WORKFLOWS_RELATIVE = Path(".clinerules") / "workflows"
KIT_RELATIVE = Path("kit") / "agentis-template"
TARGET_KIT_DIRNAME = "agentis"

# 업그레이드 안전장치: 사용자가 키운 지식/상태/시각화 산출물은 표준 키트로 덮지 않는다.
# 경로는 agentis/ 기준 상대 POSIX 문자열로 비교한다.
PROTECTED_KIT_PREFIXES = (
    "memory/",
    "skills/",
)
PROTECTED_KIT_FILES = {
    "agent.md",
    ".bootstrapped",
    "graph/flow.html",
    "graph/graph.html",
    "graph/graph.json",
    "workflows.html",
    "holonomic-brain.html",
    "holonomic-brain.json",
    "memory/log.md",
    "memory/hot.md",
    "memory/overview.md",
    "memory/_index.md",
    "memory/stats.md",
}
KIT_OWNED_MARKER = "agentis-kit:"

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
    return sum(
        1
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".pyo"}
    )


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
        "--upgrade-kit",
        action="store_true",
        help="기존 agentis/ 가 있으면 표준 키트를 안전 병합합니다. memory/·graph.html·flow.html 은 보존하고, kit-owned 스크립트만 백업 후 갱신합니다.",
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


def check_source(installer_dir: Path, want_kit: bool) -> tuple[Path, Path | None, Path | None, Path | None]:
    seed_src = installer_dir / SEED_RELATIVE
    routing_src = installer_dir / ROUTING_SOURCE_RELATIVE
    kit_src = installer_dir / KIT_RELATIVE
    rule_workflows_src = kit_src / "workflows"
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
    return seed_src, (routing_src if routing_src.is_file() else None), (kit_src if want_kit else None), (rule_workflows_src if rule_workflows_src.is_dir() else None)


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


def install_routing_rule(routing_src: Path | None, target: Path, dry_run: bool, force: bool = False) -> tuple[Path, str]:
    """Cline Rules용 자연어→workflow 라우터를 설치한다."""
    target_rule = target / ROUTING_RULE_RELATIVE
    if routing_src is None:
        return target_rule, "missing_source"
    existed = target_rule.exists()
    if existed:
        if _sha256(routing_src) == _sha256(target_rule):
            return target_rule, "same"
        if not force:
            return target_rule, "kept"
        if not dry_run:
            backup = target_rule.with_name(f"{target_rule.name}.backup-{_timestamp()}")
            target_rule.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target_rule, backup)
    if not dry_run:
        target_rule.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(routing_src, target_rule)
    return target_rule, "updated" if existed else "added"


def _rule_workflow_target_name(src: Path) -> str:
    """Cline workflows 탭에 보일 룰 파일명."""
    name = src.name
    if name.endswith(".workflow.md"):
        return name.replace(".workflow.md", ".md")
    return name


def install_rule_workflows(
    workflows_src: Path | None,
    target: Path,
    dry_run: bool,
    force: bool = False,
) -> tuple[Path, dict]:
    """표준 절차서를 Cline-visible `.clinerules/workflows/` 로 복사한다.

    `agentis/workflows/` 는 실행 스크립트와 에이전트 내부 지식의 정본이고,
    `.clinerules/workflows/` 는 Cline 하네스가 직접 읽을 가능성이 높은 실행 규칙의 정본이다.
    사용자가 이미 수정한 워크플로우 룰은 기본 보존하고, `--force` 일 때만 백업 후 갱신한다.
    """
    target_dir = target / RULE_WORKFLOWS_RELATIVE
    stats = {"added": 0, "updated": 0, "kept": 0, "backed_up": 0, "missing_source": 0}
    if workflows_src is None or not workflows_src.is_dir():
        stats["missing_source"] = 1
        return target_dir, stats

    for src in sorted(workflows_src.glob("*.workflow.md")):
        dst = target_dir / _rule_workflow_target_name(src)
        if dst.exists():
            if _sha256(src) == _sha256(dst):
                stats["kept"] += 1
                continue
            if not force:
                stats["kept"] += 1
                continue
            if not dry_run:
                backup = target_dir / f"{dst.name}.backup-{_timestamp()}"
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, backup)
            stats["backed_up"] += 1
            _copy_file(src, dst, dry_run)
            stats["updated"] += 1
            continue
        _copy_file(src, dst, dry_run)
        stats["added"] += 1
    return target_dir, stats


def _is_protected_kit_path(rel: Path) -> bool:
    rel_s = rel.as_posix()
    return rel_s in PROTECTED_KIT_FILES or any(rel_s.startswith(prefix) for prefix in PROTECTED_KIT_PREFIXES)


def _is_kit_owned(path: Path) -> bool:
    if path.suffix not in {".py", ".md", ".html", ".json"}:
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:800]
    except Exception:
        return False
    return KIT_OWNED_MARKER in head


def _backup_existing_file(kit_dst: Path, rel: Path, timestamp: str) -> Path:
    backup = kit_dst / ".upgrade-backups" / timestamp / rel
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(kit_dst / rel, backup)
    return backup


def _copy_file(src: Path, dst: Path, dry_run: bool) -> None:
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def safe_upgrade_kit(kit_src: Path, kit_dst: Path, dry_run: bool = False) -> dict:
    """표준 키트를 기존 agentis/ 에 안전 병합한다.

    원칙:
    - 사용자가 키운 지식/상태/생성물(memory/, skills/, agent.md, graph/flow.html,
      graph/graph.html 등)은 절대 덮지 않는다.
    - `# agentis-kit:` 마커가 있는 표준 스크립트/문서는 kit-owned 로 보고 백업 후 갱신한다.
    - 그 외 충돌은 내 파일을 유지하고 incoming 사본을 `.kit-incoming/` 에 둔다.
    """
    stats = {"added": 0, "updated": 0, "same": 0, "protected_kept": 0, "incoming_saved": 0}
    timestamp = _timestamp()
    if not kit_src.is_dir():
        return stats
    if not dry_run:
        kit_dst.mkdir(parents=True, exist_ok=True)

    for src in sorted(p for p in kit_src.rglob("*") if p.is_file()):
        rel = src.relative_to(kit_src)
        if "__pycache__" in rel.parts or src.suffix in {".pyc", ".pyo"}:
            continue
        dst = kit_dst / rel
        if not dst.exists():
            _copy_file(src, dst, dry_run)
            stats["added"] += 1
            continue

        if _sha256(src) == _sha256(dst):
            stats["same"] += 1
            continue

        if _is_protected_kit_path(rel):
            stats["protected_kept"] += 1
            continue

        if _is_kit_owned(dst) or _is_kit_owned(src):
            if not dry_run:
                _backup_existing_file(kit_dst, rel, timestamp)
            _copy_file(src, dst, dry_run)
            stats["updated"] += 1
            continue

        incoming = kit_dst / ".kit-incoming" / timestamp / rel
        _copy_file(src, incoming, dry_run)
        stats["incoming_saved"] += 1

    return stats


def install_kit(kit_src: Path, target: Path, dry_run: bool, upgrade: bool = False) -> tuple[Path, bool, dict | None]:
    """returns (kit_dst, skipped, upgrade_stats)"""
    kit_dst = target / TARGET_KIT_DIRNAME
    if kit_dst.exists():
        if upgrade:
            return kit_dst, False, safe_upgrade_kit(kit_src, kit_dst, dry_run=dry_run)
        return kit_dst, True, None
    if dry_run:
        return kit_dst, False, None
    shutil.copytree(kit_src, kit_dst)
    return kit_dst, False, None


# ---------------------------------------------------------------------------
# 검증 (실행 후)
# ---------------------------------------------------------------------------

def verify_installation(
    seed_src: Path,
    target_seed: Path,
    kit_src: Path | None,
    kit_dst: Path | None,
    kit_skipped: bool,
    seed_skipped: bool = False,
) -> None:
    if not target_seed.is_file():
        _err(f"❌ 검증 실패: {target_seed} 가 만들어지지 않았습니다.")
        sys.exit(EXIT_VERIFY_FAILED)
    if not seed_skipped:
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
    kit_upgrade_stats: dict | None,
    routing_rule_status: str | None,
    rule_workflow_stats: dict | None,
    backup: Path | None,
    dry_run: bool,
    seed_skipped: bool = False,
) -> None:
    title = "🔎 Dry-run 결과 (실제로는 아무것도 만들어지지 않았습니다)" if dry_run else "✅ Agentis 설치 완료"
    seed_size = target_seed.stat().st_size if target_seed.exists() else seed_src.stat().st_size
    seed_suffix = "보존" if seed_skipped else _human_size(seed_size)
    seed_line = f"   ├── .clinerules/agentis.md ({seed_suffix})"
    routing_line = "   ├── .clinerules/10-agent-routing.md (natural language → workflow router)"
    workflow_line = "   ├── .clinerules/workflows/ (Cline-visible workflow rules)"
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
        seed_suffix = "보존" if seed_skipped else _human_size(seed_size)
        seed_line = f"   ├── .clinerules/agentis.md ({seed_suffix})"

    lines = [
        "",
        title,
        "",
        f"📂 설치 위치: {target}",
        seed_line,
        routing_line,
        workflow_line,
    ]
    if kit_line:
        lines.append(kit_line)
    if backup is not None:
        lines += ["", f"💾 기존 씨드를 백업했습니다: {backup.name}"]
    if kit_src is not None and kit_skipped and not dry_run:
        lines += [
            "",
            "ℹ️  agentis/ 폴더가 이미 있어요.",
            "   기존 지식/그래프를 보호하기 위해 키트는 건너뛰었습니다.",
            "   새 키트 기능을 안전 병합하려면 `python install.py --target <작업폴더> --upgrade-kit` 을 사용하세요.",
        ]
    if kit_upgrade_stats is not None:
        s = kit_upgrade_stats
        lines += [
            "",
            "🛡️  키트 안전 병합 결과:",
            f"   추가 {s.get('added', 0)} / kit-owned 갱신 {s.get('updated', 0)} / 동일 {s.get('same', 0)} / 보호보존 {s.get('protected_kept', 0)} / incoming 보관 {s.get('incoming_saved', 0)}",
            "   보호 대상: agent.md, memory/, skills/, graph/flow.html, graph/graph.html, graph/graph.json, workflows.html, holonomic-brain.html 등",
            "   root 보기 갱신: `python agentis/graph/refresh_views.py --workspace .`",
        ]
    if rule_workflow_stats is not None:
        s = rule_workflow_stats
        lines += [
            "",
            "⚖️  Cline workflows 룰 반영:",
            f"   라우터 {routing_rule_status or 'unknown'} / workflow 추가 {s.get('added', 0)} / 갱신 {s.get('updated', 0)} / 보존 {s.get('kept', 0)} / 백업 {s.get('backed_up', 0)}",
            "   경로: .clinerules/10-agent-routing.md + .clinerules/workflows/",
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
    seed_src, routing_src, kit_src, rule_workflows_src = check_source(installer_dir, want_kit=args.kit)
    check_target(target)
    existing_seed = target / SEED_RELATIVE
    upgrade_existing = bool(args.upgrade_kit and existing_seed.exists())
    if upgrade_existing:
        backup = None
        target_seed = existing_seed
    else:
        backup = check_existing_seed(target, force=args.force, dry_run=args.dry_run)
        target_seed = install_seed(seed_src, target, dry_run=args.dry_run)

    _print(
        f"📦 인스톨러 위치: {installer_dir}\n📁 대상 폴더: {target}",
        args=args,
    )
    if args.dry_run:
        _print("⚙️  --dry-run: 실제 파일은 만들어지지 않습니다.", args=args)
    if upgrade_existing:
        _print("🛡️  --upgrade-kit: 기존 .clinerules/agentis.md 는 보존하고 kit만 안전 병합합니다.", args=args)

    rules_force = bool(args.force and not upgrade_existing)
    _routing_rule_dst, routing_rule_status = install_routing_rule(
        routing_src,
        target,
        dry_run=args.dry_run,
        force=rules_force,
    )
    _rule_workflows_dst, rule_workflow_stats = install_rule_workflows(
        rule_workflows_src,
        target,
        dry_run=args.dry_run,
        force=rules_force,
    )
    kit_dst: Path | None = None
    kit_skipped = False
    kit_upgrade_stats: dict | None = None
    if kit_src is not None:
        kit_dst, kit_skipped, kit_upgrade_stats = install_kit(
            kit_src, target, dry_run=args.dry_run, upgrade=args.upgrade_kit
        )

    if not args.dry_run:
        verify_installation(
            seed_src=seed_src,
            target_seed=target_seed,
            kit_src=kit_src,
            kit_dst=kit_dst,
            kit_skipped=kit_skipped,
            seed_skipped=upgrade_existing,
        )

    print_success(
        args=args,
        target=target,
        target_seed=target_seed,
        seed_src=seed_src,
        kit_dst=kit_dst,
        kit_src=kit_src,
        kit_skipped=kit_skipped,
        kit_upgrade_stats=kit_upgrade_stats,
        routing_rule_status=routing_rule_status,
        rule_workflow_stats=rule_workflow_stats,
        backup=backup,
        dry_run=args.dry_run,
        seed_skipped=upgrade_existing,
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
