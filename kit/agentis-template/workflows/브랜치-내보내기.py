#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.3 / 브랜치-내보내기
"""
브랜치-내보내기 — 이 에이전트의 agentis/ 를 다른 사용자에게 넘길 '브랜치' 폴더로 묶는다.

자동 제외:
  1) agent.md 의 '만든 사람 / 사용자' 값을 [REDACTED] 로 치환
  2) 본인의 사용자 엔티티 페이지 (memory/entities/ 에서 사용자 이름과 매칭되는 .md)
  3) frontmatter 에 `share: private` 가 있는 페이지
  4) --extra-exclude 로 지정한 경로 (agentis/ 기준 상대경로, 콤마 구분 또는 반복 사용)

출력:
  <에이전트이름>-브랜치-YYYY-MM-DD/
    BRANCH.md              ← 자동 보고서
    _seed/agentis.md       ← 씨드 사본 (작업 폴더 .clinerules 에서 찾으면 복사)
    fork/                  ← 통째로 받기용
    pack/                  ← 역량만 받기용
    pack/pack.meta.md      ← 팩 설명서

결정론적, 표준 라이브러리만, 사내망/오프라인 OK.

사용:
    python 브랜치-내보내기.py
    python 브랜치-내보내기.py --extra-exclude "memory/hot.md,memory/sources/2026-05-08-시험성적서-모델X.md"
    python 브랜치-내보내기.py --root <agentis 경로> --out <상위 출력 경로> --date 2026-05-13
"""
from __future__ import annotations
import argparse
import datetime as _dt
import re
import shutil
import sys
import unicodedata
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|[^\[\]]*)?\]\]")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}


# ─── 보조 ────────────────────────────────────────────────────────────────────

def find_root(start: Path) -> Path:
    p = (start if start.is_dir() else start.parent).resolve()
    for c in [p, *p.parents]:
        if (c / "agent.md").exists() or (c / "memory").is_dir():
            return c
    return p


def parse_h1(text: str, fallback: str) -> str:
    m = H1_RE.search(text)
    return m.group(1).strip() if m else fallback


def parse_field(text: str, label: str) -> str:
    """- **{label}**: {value} 형태의 첫 줄에서 value 추출. 없으면 ''."""
    pat = re.compile(r"^[\-\*\s]*\*\*" + re.escape(label) + r"\*\*\s*[:：]\s*(.+?)\s*$", re.MULTILINE)
    m = pat.search(text)
    return m.group(1).strip() if m else ""


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip().lower()] = v.strip()
    return fm


def normalize_name(s: str) -> str:
    """사람 이름·소속 등을 슬러그처럼 — 비교용. 괄호와 공백/구두점 제거."""
    s = unicodedata.normalize("NFKC", s)
    # 괄호 안 제거(소속 등)
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"[\s()\[\]{}<>·.,;:/\\\-_~'\"`!?]+", "", s)
    return s.strip().lower()


def safe_rel(path: Path, base: Path) -> Path:
    return path.resolve().relative_to(base.resolve())


def is_skip_path(p: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in p.parts) or p.name in EXCLUDE_FILES


def file_share_tag(path: Path) -> str:
    """페이지의 share frontmatter ('domain' | 'project' | 'private'). 없으면 ''."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return parse_frontmatter(text).get("share", "")


# ─── 핵심 로직 ───────────────────────────────────────────────────────────────

def redact_agent_md(text: str, user_value: str) -> tuple[str, list[str]]:
    """agent.md 본문에서 '만든 사람' 라인을 [REDACTED] 로 치환. 본문 다른 자리에 같은 이름이 박혀있으면 경고 리스트로 모아 반환."""
    warnings: list[str] = []
    out_lines = []
    user_norm = normalize_name(user_value) if user_value else ""

    # 1) '만든 사람 / 사용자' 라인 치환
    line_pat = re.compile(r"^([\-\*\s]*\*\*만든 사람\s*/\s*사용자\*\*\s*[:：]\s*).+$", re.MULTILINE)
    text2 = line_pat.sub(r"\1[REDACTED]   <!-- 받는 사람이 자기 정보로 채워주세요 -->", text)

    # 2) 본문 다른 자리에 사용자 이름이 그대로 박혀있는지 체크 (경고만)
    if user_value and user_norm:
        # 괄호 부분 제외한 핵심 이름 토큰
        core = re.sub(r"\([^)]*\)", "", user_value).strip()
        if core and len(core) >= 2:
            for i, line in enumerate(text2.splitlines(), 1):
                if "[REDACTED]" in line:
                    continue
                if core in line:
                    warnings.append(f"agent.md {i}행에 '{core}' 가 본문에 박혀있어요. 수동 검토 권장.")
                    break  # 한 번만 경고

    return text2, warnings


def collect_memory_files(memory_dir: Path) -> list[Path]:
    files = []
    if not memory_dir.is_dir():
        return files
    for f in sorted(memory_dir.rglob("*.md")):
        if not f.is_file() or is_skip_path(f):
            continue
        files.append(f)
    return files


def user_entity_match(filename: str, user_value: str) -> bool:
    """memory/entities/<파일>.md 가 사용자 본인 페이지인지. 사용자 값의 핵심 토큰이 파일명 슬러그에 들어있으면 참."""
    if not user_value:
        return False
    name_norm = normalize_name(filename)
    user_norm = normalize_name(re.sub(r"\([^)]*\)", "", user_value))
    if not user_norm or len(user_norm) < 2:
        return False
    return user_norm in name_norm


def copy_tree_filtered(src: Path, dst: Path, skip_paths: set[Path]) -> tuple[int, int]:
    """src 의 내용을 dst 로 복사 (필터링). 스킵 디렉토리/파일 제외. (copied_files, skipped_files)."""
    copied = 0
    skipped = 0
    if not src.is_dir():
        return 0, 0
    dst.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.rglob("*")):
        if f.is_dir():
            continue
        if is_skip_path(f):
            skipped += 1
            continue
        if f.resolve() in skip_paths:
            skipped += 1
            continue
        rel = f.relative_to(src)
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
        copied += 1
    return copied, skipped


def find_seed(root: Path) -> Path | None:
    """작업 폴더의 .clinerules 또는 .clinerules/agentis.md 를 찾는다."""
    ws = root.parent  # agentis/ 의 부모 = 작업 폴더 추정
    for cand in (ws / ".clinerules" / "agentis.md", ws / ".clinerules"):
        if cand.is_file():
            return cand
    return None


def suspect_leaks_scan(fork_dir: Path, user_value: str) -> list[str]:
    """fork 본문에서 의심스러운 누출 단서를 찾는다 (경고만)."""
    warns = []
    user_core = re.sub(r"\([^)]*\)", "", user_value).strip() if user_value else ""
    if user_core and len(user_core) >= 2:
        for f in sorted(fork_dir.rglob("*.md")):
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if user_core in txt:
                rel = f.relative_to(fork_dir)
                warns.append(f"fork/{rel} 에 사용자 이름('{user_core}') 흔적이 있어요.")
    # sources/ 링크가 concepts/entities/ 페이지에 남아있는지
    for sub in ("concepts", "entities"):
        d = fork_dir / "memory" / sub
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*.md")):
            try:
                txt = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for m in WIKILINK_RE.finditer(txt):
                tgt = m.group(1).strip()
                if tgt.startswith("sources/") or tgt.startswith("memory/sources/"):
                    rel = f.relative_to(fork_dir)
                    warns.append(f"fork/{rel} 가 소스 페이지 [[{tgt}]] 를 가리켜요 (소스가 같이 포함됐다면 OK, 아니면 깨진 링크).")
                    break
    return warns


# ─── 빌드 ────────────────────────────────────────────────────────────────────

def build_fork(root: Path, fork_dir: Path, user_value: str,
               extra_excludes: set[Path]) -> dict:
    """fork/ 를 만든다. 통계 dict 반환."""
    fork_dir.mkdir(parents=True, exist_ok=True)
    stats = {"included": 0, "excluded_private": 0, "excluded_user_entity": 0, "excluded_extra": 0, "redact_warnings": []}

    # 1) agent.md (REDACT)
    agent_text = (root / "agent.md").read_text(encoding="utf-8", errors="replace")
    redacted, redact_warns = redact_agent_md(agent_text, user_value)
    (fork_dir / "agent.md").write_text(redacted, encoding="utf-8")
    stats["included"] += 1
    stats["redact_warnings"] = redact_warns

    # 2) memory/ — 필터링하며 복사
    mem_src = root / "memory"
    mem_dst = fork_dir / "memory"
    if mem_src.is_dir():
        mem_dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(mem_src.rglob("*")):
            if f.is_dir() or is_skip_path(f):
                continue
            rel = f.relative_to(mem_src)
            full = (mem_src / rel).resolve()
            # 제외 규칙
            if full in extra_excludes:
                stats["excluded_extra"] += 1
                continue
            if f.suffix.lower() == ".md":
                tag = file_share_tag(f)
                if tag == "private":
                    stats["excluded_private"] += 1
                    continue
                # 사용자 엔티티 페이지인지
                if rel.parts and rel.parts[0] == "entities" and user_entity_match(rel.stem, user_value):
                    stats["excluded_user_entity"] += 1
                    continue
            out = mem_dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
            stats["included"] += 1

    # 3) skills/, workflows/ 통째로
    for sub in ("skills", "workflows"):
        src = root / sub
        if src.is_dir():
            n, _ = copy_tree_filtered(src, fork_dir / sub, extra_excludes)
            stats["included"] += n

    # 4) graph/build_graph.py 만
    src_bg = root / "graph" / "build_graph.py"
    if src_bg.is_file():
        (fork_dir / "graph").mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_bg, fork_dir / "graph" / "build_graph.py")
        stats["included"] += 1

    return stats


def build_pack(root: Path, pack_dir: Path, extra_excludes: set[Path],
               agent_name: str, branch_date: str) -> dict:
    pack_dir.mkdir(parents=True, exist_ok=True)
    stats = {"skills": 0, "workflows": 0, "concepts": 0}

    # skills, workflows 통째
    for sub, key in (("skills", "skills"), ("workflows", "workflows")):
        src = root / sub
        if src.is_dir():
            n, _ = copy_tree_filtered(src, pack_dir / sub, extra_excludes)
            stats[key] = n

    # concepts (share≠private 만)
    concepts_src = root / "memory" / "concepts"
    concepts_dst = pack_dir / "memory" / "concepts"
    if concepts_src.is_dir():
        for f in sorted(concepts_src.rglob("*.md")):
            if is_skip_path(f) or f.resolve() in extra_excludes:
                continue
            if file_share_tag(f) == "private":
                continue
            rel = f.relative_to(concepts_src)
            out = concepts_dst / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
            stats["concepts"] += 1

    # pack.meta.md
    meta = f"""---
type: pack-meta
origin: {agent_name}
branch_date: {branch_date}
created: {branch_date}
---

# {agent_name} 팩 (역량만)

`{agent_name}` 에서 추출한 **역량 슬라이스**입니다. 받는 사람의 기존 에이전트에 합치는 용도(§5-3 팩 모드).

## 포함
- skills/         — {stats['skills']} 파일 (스킬 폴더들)
- workflows/      — {stats['workflows']} 파일 (워크플로우 + 결정론 .py)
- memory/concepts/ — {stats['concepts']} 파일 (도메인 일반 개념. share=private 인 것은 제외)

## 포함되지 않은 것 (의도)
- `agent.md` — 정체성은 받는 쪽 것을 유지
- `memory/sources/`, `memory/entities/`, `memory/log.md`, `memory/hot.md`, `memory/overview.md`, `memory/_index.md` — 받는 쪽 데이터 그대로 둠
- `graph/` — 받는 쪽 빌더가 새 메모리에 맞춰 다시 그림

## 합치는 법
받는 사람 작업 폴더에서:
```
python agentis/workflows/팩-병합.py --pack <이 팩 폴더 경로> --strategy plan-only   # 충돌 미리보기
python agentis/workflows/팩-병합.py --pack <이 팩 폴더 경로> --strategy <결정>      # 결정 반영해 실제 머지
```
"""
    (pack_dir / "pack.meta.md").write_text(meta, encoding="utf-8")
    return stats


def write_branch_md(out_dir: Path, agent_name: str, user_value: str, branch_date: str,
                    fork_stats: dict, pack_stats: dict, extra_excludes_rel: list[str],
                    suspect_warns: list[str], seed_status: str) -> Path:
    body = []
    body.append(f"# {agent_name} 브랜치 — {branch_date}\n")
    body.append(f"이 폴더는 `{agent_name}` 에이전트의 **브랜치 스냅샷**입니다. (Agentis: 씨드 → 브랜치 → 메인)\n")
    body.append("## 출처\n")
    body.append(f"- 원본 에이전트: **{agent_name}**")
    body.append(f"- 원본 사용자: `{user_value}` → 브랜치에서는 `[REDACTED]` 로 치환됨")
    body.append(f"- 브랜치 생성일: {branch_date}\n")
    body.append("## 포함 / 제외 통계\n")
    body.append("**fork/** (통째로 받기용 — 정체성 + 두뇌 + 역량)")
    body.append(f"- 포함 파일: {fork_stats['included']}")
    body.append(f"- 자동 제외: `share: private` {fork_stats['excluded_private']} / 사용자 본인 엔티티 {fork_stats['excluded_user_entity']}")
    body.append(f"- 사용자 지정 제외: {fork_stats['excluded_extra']}\n")
    body.append("**pack/** (역량만 받기용)")
    body.append(f"- skills: {pack_stats['skills']} / workflows: {pack_stats['workflows']} / concepts: {pack_stats['concepts']}\n")
    if extra_excludes_rel:
        body.append("## 사용자가 지정한 추가 제외")
        for e in extra_excludes_rel:
            body.append(f"- `{e}`")
        body.append("")
    body.append("## 씨드(seed)")
    body.append(f"- {seed_status}\n")
    body.append("## ⚠ 의심 누출 경고 (사람 검토 권장)")
    if suspect_warns or fork_stats.get("redact_warnings"):
        for w in (fork_stats.get("redact_warnings") or []):
            body.append(f"- {w}")
        for w in suspect_warns:
            body.append(f"- {w}")
        body.append("")
        body.append("> 위 경고는 자동 스크럽이 완전하지 않을 수 있다는 신호입니다. fork/agent.md 와 fork/memory/concepts·entities 의 해당 파일을 한 번 훑어보고 필요하면 손으로 수정하세요.")
    else:
        body.append("- 자동 검출된 의심 누출 없음. (그래도 한번 훑어보시는 것을 권장)")
    body.append("\n## 받는 사람 안내")
    body.append("이 폴더를 작업 폴더에 두고 Cline 에 **`안녕`** 한 마디만 하면 됩니다. 씨드(`.clinerules`)가:")
    body.append("- 받는 분 작업 폴더에 **`agentis/` 가 없다면** → `fork/` 를 새 `agentis/` 로 복사하고 **리브랜드 미니 인터뷰** 진행")
    body.append("- 받는 분 작업 폴더에 **이미 `agentis/` 가 있다면** → `pack/` 만 합치는 **팩 모드** 진행")
    body.append("\n씨드가 작업 폴더에 아직 없다면 `_seed/agentis.md` 를 `.clinerules` 로 넣으세요. (또는 https://github.com/imejaim/agentis 에서 받기)")
    out = out_dir / "BRANCH.md"
    out.write_text("\n".join(body), encoding="utf-8")
    return out


def parse_extra_exclude(arg: str | None, root: Path) -> tuple[set[Path], list[str]]:
    if not arg:
        return set(), []
    items: list[str] = []
    for chunk in arg.split(","):
        c = chunk.strip()
        if c:
            items.append(c)
    resolved: set[Path] = set()
    rel_list: list[str] = []
    for item in items:
        p = (root / item).resolve()
        if p.exists():
            resolved.add(p)
            rel_list.append(item)
        else:
            rel_list.append(item + "  (경고: 경로 없음)")
    return resolved, rel_list


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent          # agentis/workflows/
    ap = argparse.ArgumentParser(description="이 에이전트를 다른 사용자에게 넘길 브랜치 폴더로 묶기")
    ap.add_argument("--root", type=Path, default=here.parent, help="agentis 디렉토리 (기본: 스크립트 기준 ../)")
    ap.add_argument("--out", type=Path, default=None, help="상위 출력 디렉토리 (기본: agentis/ 의 부모 = 작업 폴더)")
    ap.add_argument("--extra-exclude", type=str, default="", help="추가 제외 경로 (agentis 기준 상대, 콤마 구분)")
    ap.add_argument("--date", type=str, default=None, help="브랜치 날짜 (기본: 오늘 YYYY-MM-DD)")
    args = ap.parse_args(argv)

    root = find_root(args.root)
    if not (root / "agent.md").exists():
        print(f"[브랜치] agent.md 를 찾을 수 없음: {root}", file=sys.stderr)
        return 2

    agent_text = (root / "agent.md").read_text(encoding="utf-8", errors="replace")
    agent_name = parse_h1(agent_text, root.name)
    user_value = parse_field(agent_text, "만든 사람 / 사용자") or parse_field(agent_text, "만든 사람")
    branch_date = args.date or _dt.date.today().isoformat()

    extra_excludes, extra_rel = parse_extra_exclude(args.extra_exclude, root)

    out_parent = (args.out or root.parent).resolve()
    bundle = out_parent / f"{agent_name}-브랜치-{branch_date}"
    if bundle.exists():
        print(f"[브랜치] 출력 폴더가 이미 있음 → 덮어쓰지 않습니다: {bundle}", file=sys.stderr)
        return 2
    bundle.mkdir(parents=True)

    print(f"[브랜치] 출처: {agent_name}  (사용자: {user_value or '미상'})")
    print(f"[브랜치] 출력: {bundle}")
    print(f"[브랜치] 자동 제외 — 사용자 본인 정보(agent.md REDACT) + 본인 엔티티 페이지 + share=private 페이지")
    if extra_rel:
        print(f"[브랜치] 사용자 지정 제외: " + ", ".join(extra_rel))

    # fork/
    fork_stats = build_fork(root, bundle / "fork", user_value, extra_excludes)
    # pack/
    pack_stats = build_pack(root, bundle / "pack", extra_excludes, agent_name, branch_date)

    # 씨드 동봉
    seed_src = find_seed(root)
    seed_dir = bundle / "_seed"
    seed_dir.mkdir(parents=True, exist_ok=True)
    if seed_src is not None:
        shutil.copy2(seed_src, seed_dir / "agentis.md")
        seed_status = f"씨드 사본 동봉됨 (`_seed/agentis.md` — 원본: `{seed_src.name}`). 받는 분이 그대로 `.clinerules` 로 쓰면 됨."
    else:
        (seed_dir / "README.md").write_text(
            "이 브랜치를 만든 작업 폴더에서 `.clinerules` (또는 `.clinerules/agentis.md`) 를 찾지 못해 씨드를 자동 동봉하지 못했습니다.\n"
            "받는 분은 https://github.com/imejaim/agentis 의 `seed/agentis.md` 를 받아 자기 `.clinerules` 로 쓰세요.\n",
            encoding="utf-8"
        )
        seed_status = "⚠ 씨드 자동 동봉 실패 (작업 폴더 .clinerules 못 찾음). 받는 분이 agentis 레포에서 직접 받아야 함. `_seed/README.md` 참고."

    # 의심 누출 스캔
    suspect = suspect_leaks_scan(bundle / "fork", user_value)

    # BRANCH.md
    branch_md = write_branch_md(bundle, agent_name, user_value, branch_date,
                                fork_stats, pack_stats, extra_rel, suspect, seed_status)

    # 콘솔 요약
    print(f"[브랜치] fork  포함 {fork_stats['included']} / 제외 private {fork_stats['excluded_private']} / 본인엔티티 {fork_stats['excluded_user_entity']} / 사용자지정 {fork_stats['excluded_extra']}")
    print(f"[브랜치] pack  skills {pack_stats['skills']} / workflows {pack_stats['workflows']} / concepts {pack_stats['concepts']}")
    if fork_stats.get("redact_warnings"):
        for w in fork_stats["redact_warnings"]:
            print(f"[브랜치] [경고] {w}")
    if suspect:
        print(f"[브랜치] [경고] 의심 누출 단서 {len(suspect)} 건 — BRANCH.md 검토 권장")
        for w in suspect[:5]:
            print(f"   - {w}")
        if len(suspect) > 5:
            print(f"   ... 외 {len(suspect)-5} 건")
    print(f"[브랜치] -> {branch_md}")
    print(f"[브랜치] 검토 완료 후 zip 하거나 사내 깃에 push 해서 송신")
    return 1 if (fork_stats.get("redact_warnings") or suspect) else 0


if __name__ == "__main__":
    raise SystemExit(main())
