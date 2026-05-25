#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.5 / build_brain_index
"""
build_brain_index.py — agentis/memory/ 의 마크다운들을 SQLite 인덱스로 컴파일.

발상:
  graph.json 은 "노드/엣지" 만 본다. 두뇌 인덱스(brain.sqlite)는 그 위에
  *내용 검색*(BM25) + *메타데이터*(tags/domains/entities) + *링크 그래프*
  를 한꺼번에 얹어 query_brain.py 가 한 번에 풀 수 있게 한다.

훑는 대상: agentis/agent.md  +  agentis/memory/**/*.md
          (_brain/, README, *.template, _template* 는 제외)

스키마 (sqlite3, stdlib only):
  pages(id INTEGER PK, path TEXT UNIQUE, title TEXT, category TEXT,
        tokens INTEGER, created_at TEXT, updated_at TEXT, content_hash TEXT)
  tags(page_id INTEGER, tag TEXT)           — FM 헤더 tags: 에서
  links(src_id INTEGER, dst_path TEXT, anchor TEXT)  — [[..]] 파싱
  domains(page_id INTEGER, domain TEXT)     — agent.md 도메인 사전 + 태그 매칭
  entities(page_id INTEGER, entity_name TEXT, entity_type TEXT)  — entities/ + 본문 정규식
  pages_fts(content) — FTS5 가상 테이블 (BM25).

사용:
  python build_brain_index.py                    # 스크립트 위치 기준 ../ (= memory/) 부모 = agentis/
  python build_brain_index.py --root <agentis>   # agentis/ 디렉토리 지정
  python build_brain_index.py --out  <path>      # 출력 sqlite 경로 (기본: <agentis>/memory/_brain/brain.sqlite)
  python build_brain_index.py --quiet            # 요약 한 줄만
"""
from __future__ import annotations
import argparse
import hashlib
import re
import sqlite3
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# ─── 정규식 ──────────────────────────────────────────────────────────────────
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|([^\[\]]*))?\]\]")
TAG_LIST_RE = re.compile(r"^\s*tags\s*:\s*\[?([^\]\n]*)\]?\s*$", re.IGNORECASE | re.MULTILINE)
CREATED_RE = re.compile(r"^\s*created\s*:\s*(\S+)\s*$", re.IGNORECASE | re.MULTILINE)
UPDATED_RE = re.compile(r"^\s*updated\s*:\s*(\S+)\s*$", re.IGNORECASE | re.MULTILINE)
# 영문 약어 (2-6 대문자) 또는 대문자로 시작하는 1-3 단어 묶음
ENTITY_CAPS_RE = re.compile(r"\b([A-Z]{2,6})\b")
ENTITY_PHRASE_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,2})\b")
# 도메인 사전 — agent.md 의 H2 헤더(예: "## 다루는 업무") 본문에서 키워드 후보 뽑기.
# 폴백 사전 (한국어 사내 업무): 결정론·정확성을 잃지 않는 일반어만.
FALLBACK_DOMAIN_TERMS = [
    "규격", "인증", "안전", "RoHS", "KC", "시험성적서", "체크리스트",
    "대조", "추출", "OCR", "PDF", "BOM", "품질", "검증",
]

CORE_STEMS = {"agent", "_index", "overview", "log", "hot", "stats"}


def is_excluded(name: str, parts: tuple[str, ...]) -> bool:
    n = name.lower()
    if n == "readme.md" or n == ".gitkeep":
        return True
    if n.endswith(".template.md") or n.startswith("_template"):
        return True
    # _brain/ 자체는 제외 (인덱스가 자기 자신을 먹지 않게)
    if "_brain" in parts:
        return True
    return False


def find_root(start: Path) -> Path:
    """agentis/ 루트를 찾는다 — agent.md 또는 memory/ 가 있는 첫 디렉토리."""
    p = (start if start.is_dir() else start.parent).resolve()
    for c in [p, *p.parents]:
        if (c / "agent.md").exists() or (c / "memory").is_dir():
            return c
    return p


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict = {}
    body = m.group(1)
    for line in body.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip().lower()] = v.strip()
    return out


def parse_tags(text: str) -> list[str]:
    """FM 의 'tags: [a, b]' 또는 'tags: a, b' 형태 모두 받음."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return []
    body = m.group(1)
    tm = TAG_LIST_RE.search(body)
    if not tm:
        return []
    raw = tm.group(1).strip()
    if not raw:
        return []
    parts = [p.strip().strip("\"'") for p in raw.split(",")]
    return [p for p in parts if p]


def title_of(text: str, fallback: str) -> str:
    m = H1_RE.search(text)
    if m:
        return re.sub(r"^[#\s]*", "", m.group(1)).strip() or fallback
    return fallback


def category_of(rel_parts: tuple[str, ...], stem: str) -> str:
    if len(rel_parts) == 1:
        return "core" if stem in CORE_STEMS else "_other"
    top = rel_parts[0]
    if top in ("concepts", "entities", "sources"):
        return top
    return "_other"


def approx_tokens(text: str) -> int:
    """대충 토큰 수 — 단어/한글 글자 단위. 결정론."""
    # 한글 1글자 ≈ 1.2 토큰, 영문 1단어 ≈ 1 토큰 라는 거친 근사
    hangul = sum(1 for ch in text if "가" <= ch <= "힣")
    words = len(re.findall(r"[A-Za-z0-9]+", text))
    return int(hangul * 1.2 + words)


def collect_md(root: Path) -> list[tuple[str, Path, str]]:
    """루트(agentis/) 에서 인덱스 대상 .md 들. (relpath, fullpath, category)."""
    out: list[tuple[str, Path, str]] = []
    agent_md = root / "agent.md"
    if agent_md.is_file():
        out.append(("agent.md", agent_md, "core"))
    mem = root / "memory"
    if mem.is_dir():
        for f in sorted(mem.rglob("*.md")):
            if not f.is_file():
                continue
            rel = f.relative_to(root)
            if is_excluded(f.name, rel.parts):
                continue
            mem_rel = f.relative_to(mem)
            cat = category_of(mem_rel.parts, mem_rel.stem)
            out.append((rel.as_posix(), f, cat))
    return out


def extract_domains(text: str, tags: list[str], category: str,
                    domain_vocab: list[str]) -> list[str]:
    """도메인 = 태그 ∪ (도메인 사전 중 본문에 나타난 것) — 결정론, 빈도 정렬."""
    found: dict[str, int] = {}
    for t in tags:
        found[t.lower()] = found.get(t.lower(), 0) + 5  # 태그는 가중치 큼
    body = text.lower()
    for term in domain_vocab:
        cnt = body.count(term.lower())
        if cnt > 0:
            found[term.lower()] = found.get(term.lower(), 0) + cnt
    # 카테고리도 도메인 후보로
    if category in ("concepts", "entities", "sources"):
        found.setdefault(category, 0)
    return sorted(found.keys(), key=lambda k: (-found[k], k))


def extract_entities(text: str, rel: str, category: str) -> list[tuple[str, str]]:
    """엔티티 후보 — entities/ 폴더 페이지는 자기 제목이 곧 엔티티.
    본문에서는 정규식으로 (영문 약어 + 대문자-시작 1-3단어 묶음) 후보를 모은다.
    """
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    # 1) entities/ 페이지면 제목을 1급 엔티티로
    if category == "entities":
        t = title_of(text, Path(rel).stem)
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append((t, "entity-page"))
    # 2) 본문 정규식 — 빈도 2회 이상만 (잡음 컷)
    counts: dict[str, int] = {}
    for m in ENTITY_CAPS_RE.finditer(text):
        s = m.group(1)
        counts[s] = counts.get(s, 0) + 1
    for m in ENTITY_PHRASE_RE.finditer(text):
        s = m.group(1).strip()
        if len(s) <= 2:
            continue
        counts[s] = counts.get(s, 0) + 1
    for s, c in counts.items():
        if c < 2:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((s, "regex-caps" if s.isupper() else "regex-phrase"))
    return out


def load_domain_vocab(root: Path) -> list[str]:
    """agent.md 의 본문에서 도메인 후보 키워드 추출 — H2 헤더 다음의 짧은 키워드.
    실패 시 폴백 사전.
    """
    agent_md = root / "agent.md"
    vocab: set[str] = set(FALLBACK_DOMAIN_TERMS)
    if not agent_md.is_file():
        return sorted(vocab)
    try:
        text = agent_md.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return sorted(vocab)
    # `## 다루는 업무` 이하의 불릿에서 명사스러운 키워드 (한글 2-6자) 모음
    m = re.search(r"##\s*다루는\s*업무\s*\n(.*?)(?:\n##|\Z)", text, re.DOTALL)
    if m:
        body = m.group(1)
        for tok in re.findall(r"[가-힣]{2,8}", body):
            vocab.add(tok)
        for tok in re.findall(r"[A-Z]{2,6}", body):
            vocab.add(tok)
    return sorted(vocab)


# ─── DB 구축 ──────────────────────────────────────────────────────────────
def init_schema(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.executescript("""
    DROP TABLE IF EXISTS pages;
    DROP TABLE IF EXISTS tags;
    DROP TABLE IF EXISTS links;
    DROP TABLE IF EXISTS domains;
    DROP TABLE IF EXISTS entities;
    DROP TABLE IF EXISTS pages_fts;

    CREATE TABLE pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        tokens INTEGER NOT NULL DEFAULT 0,
        created_at TEXT,
        updated_at TEXT,
        content_hash TEXT NOT NULL
    );
    CREATE TABLE tags (
        page_id INTEGER NOT NULL,
        tag TEXT NOT NULL,
        PRIMARY KEY (page_id, tag)
    );
    CREATE TABLE links (
        src_id INTEGER NOT NULL,
        dst_path TEXT NOT NULL,
        anchor TEXT
    );
    CREATE TABLE domains (
        page_id INTEGER NOT NULL,
        domain TEXT NOT NULL,
        PRIMARY KEY (page_id, domain)
    );
    CREATE TABLE entities (
        page_id INTEGER NOT NULL,
        entity_name TEXT NOT NULL,
        entity_type TEXT NOT NULL
    );
    CREATE INDEX idx_tags_tag ON tags(tag);
    CREATE INDEX idx_links_src ON links(src_id);
    CREATE INDEX idx_links_dst ON links(dst_path);
    CREATE INDEX idx_domains_d ON domains(domain);
    CREATE INDEX idx_entities_n ON entities(entity_name);
    """)
    # FTS5 — 가용 시. 없으면 FTS4 폴백.
    try:
        cur.execute("CREATE VIRTUAL TABLE pages_fts USING fts5(path, title, body, tokenize='unicode61')")
    except sqlite3.OperationalError:
        try:
            cur.execute("CREATE VIRTUAL TABLE pages_fts USING fts4(path, title, body)")
        except sqlite3.OperationalError:
            cur.execute("CREATE TABLE pages_fts (path TEXT, title TEXT, body TEXT)")
    con.commit()


def build(root: Path, out: Path, quiet: bool = False) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(out)
    init_schema(con)
    cur = con.cursor()

    vocab = load_domain_vocab(root)
    files = collect_md(root)
    if not quiet:
        print(f"[build_brain_index] root={root}  files={len(files)}  domain_vocab={len(vocab)}")

    n_tags = n_links = n_domains = n_entities = 0
    for rel, fp, cat in files:
        text = fp.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        tags = parse_tags(text)
        title = title_of(text, Path(rel).stem)
        created = fm.get("created", "")
        updated = fm.get("updated", "")
        h = hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()
        tok = approx_tokens(text)
        cur.execute(
            "INSERT INTO pages(path,title,category,tokens,created_at,updated_at,content_hash) VALUES(?,?,?,?,?,?,?)",
            (rel, title, cat, tok, created, updated, h),
        )
        pid = cur.lastrowid

        for t in tags:
            cur.execute("INSERT OR IGNORE INTO tags(page_id, tag) VALUES(?,?)", (pid, t))
            n_tags += 1

        for m in WIKILINK_RE.finditer(text):
            dst = m.group(1).strip().strip("/")
            anchor = (m.group(2) or "").strip() or None
            cur.execute("INSERT INTO links(src_id, dst_path, anchor) VALUES(?,?,?)", (pid, dst, anchor))
            n_links += 1

        for d in extract_domains(text, tags, cat, vocab):
            cur.execute("INSERT OR IGNORE INTO domains(page_id, domain) VALUES(?,?)", (pid, d))
            n_domains += 1

        for ename, etype in extract_entities(text, rel, cat):
            cur.execute("INSERT INTO entities(page_id, entity_name, entity_type) VALUES(?,?,?)", (pid, ename, etype))
            n_entities += 1

        # FTS — frontmatter 빼고 본문만 (헤더 잡음 줄임)
        body_only = FRONTMATTER_RE.sub("", text, count=1)
        cur.execute("INSERT INTO pages_fts(path, title, body) VALUES(?,?,?)", (rel, title, body_only))

    con.commit()
    cur.execute("SELECT COUNT(*) FROM pages")
    n_pages = cur.fetchone()[0]
    con.close()
    summary = {
        "pages": n_pages, "tags": n_tags, "links": n_links,
        "domains": n_domains, "entities": n_entities,
        "out": str(out),
    }
    if not quiet:
        print(f"[build_brain_index] OK  pages={n_pages}  tags={n_tags}  links={n_links}  domains={n_domains}  entities={n_entities}")
        print(f"[build_brain_index] wrote {out}")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="agentis 두뇌 인덱스 빌더 (SQLite)")
    ap.add_argument("--root", type=Path, default=None,
                    help="agentis/ 디렉토리 (기본: 스크립트 위치에서 자동 탐색)")
    ap.add_argument("--out", type=Path, default=None,
                    help="출력 sqlite 경로 (기본: <root>/memory/_brain/brain.sqlite)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    start = args.root if args.root else Path(__file__).resolve().parent
    root = find_root(start)
    out = args.out if args.out else (root / "memory" / "_brain" / "brain.sqlite")
    build(root, out, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
