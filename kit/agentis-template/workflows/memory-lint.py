#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.5 / memory-lint
"""
memory-lint.py — 메모리 위키 점검 + 안전한 자동 수정.

검사:
  1) 깨진 [[링크]]    — 대상 페이지 없음.
  2) 고아 페이지      — 어디서도 링크 안 됨 (코어·index 제외).
  3) 중복/유사 페이지 — 제목·H1·본문 시작이 80%+ 유사한 후보.

자동 수정 (--fix):
  - 깨진 링크는 `<!-- TODO: 깨진 링크 [[X]] -->` 로 주석 처리 (텍스트는 보존).
  - 고아 페이지는 보고만 (자동 삭제 X — 사용자가 결정).
  - 중복 후보는 보고만.

사용:
  python memory-lint.py                  # 보고서만
  python memory-lint.py --fix            # 안전한 수정 적용 (깨진 링크 주석화)
  python memory-lint.py --report out.md  # 보고서를 파일로
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|[^\[\]]*)?\]\]")
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def strip_code(text: str) -> str:
    """링크 검사에서 제외할 영역(코드 펜스/인라인 코드/HTML 주석)을 빈 공간으로 치환.
    오프셋 변화를 최소화하려고 같은 길이의 공백으로 치환.
    """
    def _blank(m: re.Match) -> str:
        return " " * (m.end() - m.start())
    out = CODE_FENCE_RE.sub(_blank, text)
    out = INLINE_CODE_RE.sub(_blank, out)
    out = HTML_COMMENT_RE.sub(_blank, out)
    return out

CORE_STEMS = {"agent", "_index", "overview", "log", "hot", "stats"}
EXCLUDE_NAMES = {"README.md", ".gitkeep"}


def find_root(start: Path) -> Path:
    p = (start if start.is_dir() else start.parent).resolve()
    for c in [p, *p.parents]:
        if (c / "agent.md").exists() or (c / "memory").is_dir():
            return c
    return p


def collect_pages(root: Path) -> list[tuple[str, Path]]:
    """(node_id, path) — build_graph.py 와 같은 ID 규칙.
    agent.md + memory/**/*.md + skills/<name>/SKILL.md + workflows/*.workflow.md
    """
    out: list[tuple[str, Path]] = []
    if (root / "agent.md").is_file():
        out.append(("agent", root / "agent.md"))
    mem = root / "memory"
    if mem.is_dir():
        for f in sorted(mem.rglob("*.md")):
            if f.name in EXCLUDE_NAMES or f.name.startswith("_template") or f.name.endswith(".template.md"):
                continue
            if "_brain" in f.relative_to(mem).parts:
                continue
            rel = f.relative_to(mem).with_suffix("").as_posix()
            out.append((f"memory/{rel}", f))
    sk = root / "skills"
    if sk.is_dir():
        for d in sorted(p for p in sk.iterdir() if p.is_dir()):
            if d.name.startswith("_"):
                continue
            sf = d / "SKILL.md"
            if sf.is_file():
                out.append((f"skills/{d.name}", sf))
            for f in sorted(d.glob("*.md")):
                if f.name == "SKILL.md" or f.name in EXCLUDE_NAMES:
                    continue
                out.append((f"skills/{d.name}/{f.stem}", f))
    wf = root / "workflows"
    if wf.is_dir():
        for f in sorted(wf.glob("*.workflow.md")):
            if f.name in EXCLUDE_NAMES or f.name.startswith("_template"):
                continue
            stem = f.name[: -len(".workflow.md")]
            out.append((f"workflows/{stem}", f))
    # dedupe by id
    seen: set[str] = set()
    uniq: list[tuple[str, Path]] = []
    for nid, fp in out:
        if nid in seen:
            continue
        seen.add(nid)
        uniq.append((nid, fp))
    return uniq


def index_pages(pages: list[tuple[str, Path]]) -> tuple[set, dict]:
    by_id = {nid for nid, _ in pages}
    by_basename: dict[str, list[str]] = {}
    for nid, _ in pages:
        base = Path(nid).name.lower()
        by_basename.setdefault(base, []).append(nid)
    return by_id, by_basename


def resolve_link(target: str, by_id: set, by_basename: dict) -> str | None:
    t = target.strip().strip("/")
    if not t:
        return None
    t = re.sub(r"\.md$", "", t, flags=re.IGNORECASE)
    if t in by_id:
        return t
    if ("memory/" + t) in by_id:
        return "memory/" + t
    if t.startswith("memory/") and t[len("memory/"):] in by_id:
        return t[len("memory/"):]
    base = Path(t).name.lower()
    cands = by_basename.get(base)
    if cands:
        return sorted(cands)[0]
    return None


def collect_links(pages: list[tuple[str, Path]], by_id: set, by_basename: dict):
    """반환: (links[src->set(dst)], broken[(src, target_str)])."""
    links: dict[str, set] = {nid: set() for nid, _ in pages}
    broken: list[tuple[str, str, Path]] = []
    for nid, fp in pages:
        text = fp.read_text(encoding="utf-8", errors="replace")
        scan = strip_code(text)
        for m in WIKILINK_RE.finditer(scan):
            tgt_raw = m.group(1)
            resolved = resolve_link(tgt_raw, by_id, by_basename)
            if resolved is None:
                broken.append((nid, tgt_raw, fp))
            else:
                links[nid].add(resolved)
    return links, broken


def find_orphans(pages: list[tuple[str, Path]], links: dict) -> list[str]:
    """어디서도 들어오는 링크가 없는 페이지. 코어·index 는 제외."""
    incoming: dict[str, int] = {nid: 0 for nid, _ in pages}
    for src, dsts in links.items():
        for d in dsts:
            if d in incoming:
                incoming[d] += 1
    orphans = []
    for nid, _ in pages:
        if Path(nid).stem in CORE_STEMS:
            continue
        if nid.endswith("_index"):
            continue
        if incoming[nid] == 0:
            orphans.append(nid)
    return orphans


def _tokens(text: str) -> set:
    body = FRONTMATTER_RE.sub("", text, count=1).lower()
    return set(re.findall(r"[가-힣A-Za-z0-9]{2,}", body))


def find_duplicates(pages: list[tuple[str, Path]], threshold: float = 0.80) -> list[tuple[str, str, float]]:
    """Jaccard 유사도 80%+ 페어. O(N^2) — 메모리 위키 규모에선 OK."""
    docs: list[tuple[str, set, str]] = []
    for nid, fp in pages:
        text = fp.read_text(encoding="utf-8", errors="replace")
        title_match = H1_RE.search(text)
        title = title_match.group(1).strip() if title_match else Path(nid).stem
        toks = _tokens(text)
        if len(toks) < 5:
            continue
        docs.append((nid, toks, title))
    out: list[tuple[str, str, float]] = []
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            a_id, a_t, _ = docs[i]
            b_id, b_t, _ = docs[j]
            inter = len(a_t & b_t)
            union = len(a_t | b_t)
            if union == 0:
                continue
            sim = inter / union
            if sim >= threshold:
                out.append((a_id, b_id, round(sim, 3)))
    return sorted(out, key=lambda x: -x[2])


def fix_broken_links(broken: list[tuple[str, str, Path]]) -> int:
    """깨진 [[X]] 를 <!-- TODO: 깨진 링크 [[X]] --> 로 주석 처리. 결정론.
    코드 펜스/인라인 코드/HTML 주석 안의 [[X]] 는 건드리지 않는다 (예시 보호).
    """
    by_file: dict[Path, list[str]] = {}
    for _, tgt, fp in broken:
        by_file.setdefault(fp, []).append(tgt)
    fixed = 0
    for fp, tgts in by_file.items():
        text = fp.read_text(encoding="utf-8", errors="replace")
        # 코드 영역을 자리표시자로 잠시 빼두고, 본문에서만 치환한 뒤 복원
        placeholders: list[str] = []
        def _stash(m: re.Match) -> str:
            placeholders.append(m.group(0))
            return f"\x00CODE{len(placeholders) - 1}\x00"
        protected = CODE_FENCE_RE.sub(_stash, text)
        protected = INLINE_CODE_RE.sub(_stash, protected)
        protected = HTML_COMMENT_RE.sub(_stash, protected)
        for tgt in set(tgts):
            esc = re.escape(tgt)
            pattern = re.compile(r"\[\[" + esc + r"(\|[^\[\]]*)?\]\]")
            def _sub(m):
                return f"<!-- TODO: 깨진 링크 [[{tgt}]] -->"
            new_text, n = pattern.subn(_sub, protected)
            if n > 0:
                protected = new_text
                fixed += n
        # 자리표시자 복원
        def _unstash(m: re.Match) -> str:
            i = int(m.group(1))
            return placeholders[i] if 0 <= i < len(placeholders) else m.group(0)
        restored = re.sub(r"\x00CODE(\d+)\x00", _unstash, protected)
        fp.write_text(restored, encoding="utf-8")
    return fixed


def build_report(root: Path, broken, orphans, dups) -> str:
    lines = []
    lines.append(f"# memory-lint 보고서")
    lines.append("")
    lines.append(f"- root: `{root}`")
    lines.append(f"- 깨진 링크: {len(broken)}")
    lines.append(f"- 고아 페이지: {len(orphans)}")
    lines.append(f"- 중복/유사 후보: {len(dups)}")
    lines.append("")

    lines.append("## 깨진 링크")
    if not broken:
        lines.append("- (없음)")
    else:
        by_src: dict[str, list[str]] = {}
        for src, tgt, _ in broken:
            by_src.setdefault(src, []).append(tgt)
        for src, tgts in sorted(by_src.items()):
            lines.append(f"- **{src}** → 깨진 대상 {len(tgts)}개")
            for t in tgts[:10]:
                lines.append(f"  - `[[{t}]]`")
            if len(tgts) > 10:
                lines.append(f"  - … +{len(tgts) - 10}")
    lines.append("")

    lines.append("## 고아 페이지 (들어오는 링크 없음)")
    if not orphans:
        lines.append("- (없음)")
    else:
        for nid in sorted(orphans):
            lines.append(f"- {nid}")
    lines.append("")

    lines.append("## 중복/유사 후보 (Jaccard ≥ 0.80)")
    if not dups:
        lines.append("- (없음)")
    else:
        for a, b, s in dups[:20]:
            lines.append(f"- {a}  ↔  {b}  (sim={s})")
        if len(dups) > 20:
            lines.append(f"- … +{len(dups) - 20}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="agentis 메모리 lint")
    ap.add_argument("--root", type=Path, default=None)
    ap.add_argument("--fix", action="store_true", help="안전한 자동 수정 (깨진 링크 주석화)")
    ap.add_argument("--report", type=Path, default=None, help="보고서를 파일로 저장")
    ap.add_argument("--sim", type=float, default=0.80, help="중복 유사도 임계 (기본 0.80)")
    args = ap.parse_args(argv)

    start = args.root if args.root else Path(__file__).resolve().parent
    root = find_root(start)
    pages = collect_pages(root)
    by_id, by_basename = index_pages(pages)
    links, broken = collect_links(pages, by_id, by_basename)
    orphans = find_orphans(pages, links)
    dups = find_duplicates(pages, threshold=args.sim)

    report = build_report(root, broken, orphans, dups)
    print(report)

    if args.report:
        args.report.write_text(report, encoding="utf-8")
        print(f"\n[memory-lint] 보고서 저장: {args.report}")

    if args.fix and broken:
        n = fix_broken_links(broken)
        print(f"\n[memory-lint] 깨진 링크 {n}개를 주석 처리했습니다 (자동 수정).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
