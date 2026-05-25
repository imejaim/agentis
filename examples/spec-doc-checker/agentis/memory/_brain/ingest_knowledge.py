#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.5 / ingest_knowledge
"""
ingest_knowledge.py — 사용자 자료 → 메타데이터 자동 추출 → 두뇌 페이지 생성.

발상:
  결정론 우선. md/txt 는 직접, pdf/docx 는 패키지 있을 때만. AI API 없이도
  키워드/엔티티/도메인/날짜/제목을 정규식 + 빈도로 뽑아 sources/ 페이지 만들고
  새 엔티티/개념은 entities/, concepts/ 에 스텁으로 자동 생성.

처리 흐름:
  1) 텍스트 추출 (md/txt 직접 / pdf=pypdf / docx=python-docx / 그 외 안내).
  2) 청크 분할 (~500 토큰 근사 — 단락 단위).
  3) 메타데이터 추출:
     - 제목 (첫 H1 또는 파일명)
     - 키워드 (TF 빈도 + 불용어 컷)
     - 엔티티 (대문자 약어 2-6 + 대문자-시작 1-3단어 묶음, 빈도 ≥2)
     - 도메인 (agent.md 사전 + 카테고리)
     - 날짜 (YYYY-MM-DD / YYYY.MM.DD)
  4) memory/sources/<날짜>-<파일명>.md 페이지 생성 — frontmatter + 요약 + [[연관]]
  5) 새 엔티티 → entities/<엔티티>.md 스텁, 새 개념(키워드 상위) → concepts/<개념>.md
  6) memory/_index.md 갱신 (해당 섹션에 한 줄 추가).

LLM hook (선택):
  --llm-hook "<명령>"  : 메타 추출 단계에 외부 LLM 명령을 호출해 의미관계 보강.
                        명령은 stdin 으로 본문을 받고 stdout 으로 JSON 출력.
                        스키마: {"keywords":[..], "entities":[..], "summary":"..", "links":[..]}
                        호환 안 되면 무시하고 결정론 결과만 사용.

사용:
  python ingest_knowledge.py --file 자료.pdf
  python ingest_knowledge.py --dir  /자료들/
  python ingest_knowledge.py --file a.md --dry-run    # 무엇이 만들어질지 미리 보기
  python ingest_knowledge.py --file a.md --llm-hook "node llm-hook.js"
"""
from __future__ import annotations
import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
DATE_RE = re.compile(r"\b(20\d{2})[-./](0?[1-9]|1[0-2])[-./](0?[1-9]|[12]\d|3[01])\b")
ENTITY_CAPS_RE = re.compile(r"\b([A-Z]{2,6})\b")
ENTITY_PHRASE_RE = re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,2})\b")
HANGUL_WORD_RE = re.compile(r"[가-힣]{2,8}")

# 불용어 — 한국어/영문 흔한 잡음
STOPWORDS = {
    # 영문
    "the", "and", "for", "are", "but", "not", "you", "your", "with", "this", "that",
    "from", "have", "has", "was", "were", "will", "can", "may", "any", "all", "one",
    # 한국어 빈도형 (실용 컷)
    "그리고", "또는", "그러나", "그러면", "있다", "없다", "한다", "하는", "하지",
    "이것", "그것", "저것", "이런", "그런", "저런", "있는", "없는",
}


# ─── 텍스트 추출 ─────────────────────────────────────────────────────────
def extract_text(path: Path) -> tuple[str, list[str]]:
    """파일에서 텍스트 추출. (text, notes). 실패 시 빈 텍스트 + notes."""
    notes: list[str] = []
    suf = path.suffix.lower()
    try:
        if suf in (".md", ".txt", ".markdown", ".rst"):
            return path.read_text(encoding="utf-8", errors="replace"), notes
        if suf == ".csv":
            return path.read_text(encoding="utf-8", errors="replace"), notes
        if suf == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore
            except Exception:
                try:
                    from PyPDF2 import PdfReader  # type: ignore
                except Exception:
                    notes.append("pdf 추출에 pypdf(또는 PyPDF2) 필요 — `pip install pypdf`. 빈 텍스트로 진행.")
                    return "", notes
            try:
                reader = PdfReader(str(path))
                buf = []
                for page in reader.pages:
                    try:
                        buf.append(page.extract_text() or "")
                    except Exception:
                        continue
                return "\n\n".join(buf), notes
            except Exception as e:
                notes.append(f"pdf 읽기 실패: {e}")
                return "", notes
        if suf == ".docx":
            try:
                import docx  # type: ignore
            except Exception:
                notes.append("docx 추출에 python-docx 필요 — `pip install python-docx`. 빈 텍스트로 진행.")
                return "", notes
            try:
                d = docx.Document(str(path))
                return "\n\n".join(p.text for p in d.paragraphs), notes
            except Exception as e:
                notes.append(f"docx 읽기 실패: {e}")
                return "", notes
        # 그 외 — 바이너리 가능성, 일단 utf-8 시도
        try:
            return path.read_text(encoding="utf-8", errors="replace"), notes
        except Exception as e:
            notes.append(f"확장자 {suf} 는 직접 지원 X. utf-8 강제도 실패: {e}")
            return "", notes
    except Exception as e:
        notes.append(f"읽기 실패: {e}")
        return "", notes


# ─── 청크 분할 ────────────────────────────────────────────────────────────
def chunk_text(text: str, target_tokens: int = 500) -> list[str]:
    """단락 단위로 모아 ~target_tokens 근사. 결정론."""
    if not text.strip():
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    cur: list[str] = []
    cur_tok = 0

    def _tok(s: str) -> int:
        hangul = sum(1 for ch in s if "가" <= ch <= "힣")
        words = len(re.findall(r"[A-Za-z0-9]+", s))
        return int(hangul * 1.2 + words)

    for p in paras:
        t = _tok(p)
        if cur and cur_tok + t > target_tokens:
            chunks.append("\n\n".join(cur))
            cur = [p]
            cur_tok = t
        else:
            cur.append(p)
            cur_tok += t
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


# ─── 메타데이터 추출 ─────────────────────────────────────────────────────
def extract_title(text: str, path: Path) -> str:
    m = H1_RE.search(text)
    if m:
        return re.sub(r"^[#\s]*", "", m.group(1)).strip()
    return path.stem.replace("_", " ").replace("-", " ")


def extract_dates(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for m in DATE_RE.finditer(text):
        y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        key = f"{y}-{mo}-{d}"
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def extract_keywords(text: str, top_n: int = 12) -> list[str]:
    """TF 빈도 + 불용어 컷. 한글 2-8자 + 영문 단어."""
    counts: dict[str, int] = {}
    for w in HANGUL_WORD_RE.findall(text):
        if w in STOPWORDS:
            continue
        counts[w] = counts.get(w, 0) + 1
    for w in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text):
        wl = w.lower()
        if wl in STOPWORDS:
            continue
        counts[w] = counts.get(w, 0) + 1
    # 빈도 ≥ 2 만, 빈도 내림차순
    ranked = sorted(
        ((w, c) for w, c in counts.items() if c >= 2),
        key=lambda x: (-x[1], x[0]),
    )
    return [w for w, _ in ranked[:top_n]]


def extract_entities(text: str) -> list[str]:
    counts: dict[str, int] = {}
    for m in ENTITY_CAPS_RE.finditer(text):
        counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    for m in ENTITY_PHRASE_RE.finditer(text):
        s = m.group(1).strip()
        if len(s) < 3:
            continue
        counts[s] = counts.get(s, 0) + 1
    return [w for w, c in sorted(counts.items(), key=lambda x: (-x[1], x[0])) if c >= 2][:10]


def load_domain_vocab(agentis_root: Path) -> list[str]:
    agent_md = agentis_root / "agent.md"
    vocab: set[str] = set()
    if agent_md.is_file():
        try:
            text = agent_md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return []
        m = re.search(r"##\s*다루는\s*업무\s*\n(.*?)(?:\n##|\Z)", text, re.DOTALL)
        if m:
            for tok in HANGUL_WORD_RE.findall(m.group(1)):
                vocab.add(tok)
            for tok in re.findall(r"[A-Z]{2,6}", m.group(1)):
                vocab.add(tok)
    return sorted(vocab)


def detect_domains(text: str, vocab: list[str]) -> list[str]:
    body = text.lower()
    hits = [t for t in vocab if t.lower() in body]
    return hits[:8]


# ─── LLM hook ─────────────────────────────────────────────────────────────
def run_llm_hook(cmd: str, text: str) -> dict:
    """외부 명령을 호출. 실패하면 빈 dict — 결정론 결과만 사용."""
    try:
        proc = subprocess.run(
            cmd, input=text, shell=True, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
        if proc.returncode != 0:
            return {"_error": f"exit {proc.returncode}: {proc.stderr[:200]}"}
        return json.loads(proc.stdout)
    except Exception as e:
        return {"_error": str(e)}


# ─── 페이지 작성 ─────────────────────────────────────────────────────────
def sanitize_filename(name: str) -> str:
    s = re.sub(r"\s+", "-", name.strip())
    s = re.sub(r"[\\/:*?\"<>|]", "", s)
    s = s.strip("-.")
    return s or "untitled"


SOURCE_TEMPLATE = """---
type: source
tags: [{tags}]
created: {today}
updated: {today}
source_count: 1
---

# {title}

> 원본: `{orig_path}`  ({today} 자동 수집)

## 요약 (자동 추출 — 결정론)

- 원본 길이: {tokens} 토큰 (근사)
- 추정 도메인: {domains}
- 발견 날짜: {dates}

## 핵심 키워드

{keywords_block}

## 발견된 엔티티

{entities_block}

## 발췌 (첫 청크)

{first_chunk}

## 관련 페이지 (자동 링크)

{links_block}

---

*결정론 추출 결과입니다. 사용자가 본문을 읽고 잘못된 추정은 수정해주세요.*
"""

ENTITY_STUB = """---
type: entity
tags: [auto-stub]
created: {today}
updated: {today}
source_count: 1
---

# {name}

> 자동 생성 스텁 — [[sources/{src}]] 에서 자주 등장. 사용자가 본문 채워주세요.

- 정의:
- 맥락:
- 관련 자료: [[sources/{src}]]
"""

CONCEPT_STUB = """---
type: concept
tags: [auto-stub, {tag}]
created: {today}
updated: {today}
source_count: 1
---

# {name}

> 자동 생성 스텁 — [[sources/{src}]] 에서 자주 등장. 사용자가 정의·예시 채워주세요.

- 정의:
- 사례:
- 관련 자료: [[sources/{src}]]
"""


def write_source_page(agentis_root: Path, src_path: Path, meta: dict, dry_run: bool = False) -> Path:
    today = _dt.date.today().isoformat()
    sources_dir = agentis_root / "memory" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{today}-{sanitize_filename(src_path.stem)}.md"
    page = sources_dir / fname

    keywords = meta.get("keywords", [])
    entities = meta.get("entities", [])
    domains = meta.get("domains", [])
    dates = meta.get("dates", [])
    title = meta.get("title", src_path.stem)
    first_chunk = meta.get("first_chunk", "")
    tokens = meta.get("tokens", 0)

    keywords_block = "\n".join(f"- {k}" for k in keywords) or "- (없음)"
    entities_block = "\n".join(f"- [[entities/{sanitize_filename(e)}]]  ({e})" for e in entities) or "- (없음)"
    # 자동 링크: 키워드 상위 3개 → concepts/, 엔티티 상위 3개 → entities/
    auto_links = []
    for k in keywords[:3]:
        auto_links.append(f"- [[concepts/{sanitize_filename(k)}]]")
    for e in entities[:3]:
        auto_links.append(f"- [[entities/{sanitize_filename(e)}]]")
    links_block = "\n".join(auto_links) or "- (없음 — 키워드/엔티티가 더 모이면 추가)"

    body = SOURCE_TEMPLATE.format(
        tags=", ".join(domains[:5]) or "auto-ingest",
        today=today,
        title=title,
        orig_path=str(src_path).replace("\\", "/"),
        tokens=tokens,
        domains=", ".join(domains) or "(미정)",
        dates=", ".join(dates) or "(없음)",
        keywords_block=keywords_block,
        entities_block=entities_block,
        first_chunk=first_chunk[:1200] if first_chunk else "(본문 추출 실패 또는 비어있음)",
        links_block=links_block,
    )

    if not dry_run:
        page.write_text(body, encoding="utf-8")
    return page


def write_stubs(agentis_root: Path, source_basename: str, keywords: list[str],
                entities: list[str], dry_run: bool = False) -> list[Path]:
    today = _dt.date.today().isoformat()
    created: list[Path] = []
    ent_dir = agentis_root / "memory" / "entities"
    con_dir = agentis_root / "memory" / "concepts"
    ent_dir.mkdir(parents=True, exist_ok=True)
    con_dir.mkdir(parents=True, exist_ok=True)
    src_no_md = source_basename[:-3] if source_basename.endswith(".md") else source_basename

    for e in entities[:5]:
        fn = sanitize_filename(e) + ".md"
        page = ent_dir / fn
        if page.exists():
            continue
        if not dry_run:
            page.write_text(ENTITY_STUB.format(name=e, today=today, src=src_no_md), encoding="utf-8")
        created.append(page)

    for k in keywords[:3]:
        fn = sanitize_filename(k) + ".md"
        page = con_dir / fn
        if page.exists():
            continue
        if not dry_run:
            page.write_text(
                CONCEPT_STUB.format(name=k, today=today, src=src_no_md, tag="auto-keyword"),
                encoding="utf-8",
            )
        created.append(page)
    return created


def update_index(agentis_root: Path, source_page: Path, dry_run: bool = False) -> bool:
    idx = agentis_root / "memory" / "_index.md"
    if not idx.is_file():
        return False
    text = idx.read_text(encoding="utf-8", errors="replace")
    rel = source_page.relative_to(agentis_root / "memory").with_suffix("").as_posix()
    link_line = f"- [[{rel}]] — 자동 수집 ({_dt.date.today().isoformat()})"
    if link_line in text:
        return False
    # `## 소스 (sources/)` 섹션 아래로
    if "## 소스" in text or "## 소스 (sources/)" in text:
        lines = text.splitlines()
        out_lines = []
        inserted = False
        for i, line in enumerate(lines):
            out_lines.append(line)
            if not inserted and line.strip().startswith("## 소스"):
                # 다음 비어있지 않은 첫 줄 뒤에 삽입 — 또는 즉시
                out_lines.append(link_line)
                inserted = True
        if inserted:
            new_text = "\n".join(out_lines)
            if not dry_run:
                idx.write_text(new_text, encoding="utf-8")
            return True
    # 섹션 없으면 끝에 append
    new_text = text.rstrip() + f"\n\n## 소스 (sources/)\n{link_line}\n"
    if not dry_run:
        idx.write_text(new_text, encoding="utf-8")
    return True


# ─── 단일 파일 처리 ──────────────────────────────────────────────────────
def find_agentis_root(start: Path) -> Path:
    p = (start if start.is_dir() else start.parent).resolve()
    for c in [p, *p.parents]:
        if (c / "agent.md").exists() or (c / "memory").is_dir():
            return c
    return p


def ingest_file(src: Path, agentis_root: Path, llm_hook: str | None = None,
                dry_run: bool = False) -> dict:
    notes: list[str] = []
    text, ex_notes = extract_text(src)
    notes.extend(ex_notes)
    if not text.strip():
        notes.append("본문이 비어있음 — 소스 페이지만 생성하고 스텁은 건너뜀.")

    chunks = chunk_text(text, target_tokens=500)
    title = extract_title(text, src)
    keywords = extract_keywords(text)
    entities = extract_entities(text)
    vocab = load_domain_vocab(agentis_root)
    domains = detect_domains(text, vocab)
    dates = extract_dates(text)
    tokens_approx = sum(
        int(sum(1 for ch in c if "가" <= ch <= "힣") * 1.2 +
            len(re.findall(r"[A-Za-z0-9]+", c)))
        for c in chunks
    )
    first_chunk = chunks[0] if chunks else ""

    # LLM hook (선택) — 결정론 결과를 *보강*만 함 (덮어쓰지 않음)
    if llm_hook:
        hook = run_llm_hook(llm_hook, text[:8000])
        if hook.get("_error"):
            notes.append(f"llm-hook 실패: {hook['_error']} — 결정론 결과만 사용.")
        else:
            for k in hook.get("keywords", []):
                if k not in keywords:
                    keywords.append(k)
            for e in hook.get("entities", []):
                if e not in entities:
                    entities.append(e)

    meta = {
        "title": title, "keywords": keywords, "entities": entities,
        "domains": domains, "dates": dates, "tokens": tokens_approx,
        "first_chunk": first_chunk,
    }

    page = write_source_page(agentis_root, src, meta, dry_run=dry_run)
    stubs = write_stubs(agentis_root, page.name, keywords, entities, dry_run=dry_run)
    idx_updated = update_index(agentis_root, page, dry_run=dry_run)

    return {
        "source_page": str(page),
        "stubs_created": [str(s) for s in stubs],
        "index_updated": idx_updated,
        "meta": {k: v for k, v in meta.items() if k != "first_chunk"},
        "notes": notes,
        "dry_run": dry_run,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="agentis 두뇌 — 사용자 자료 ingest")
    ap.add_argument("--file", type=Path, default=None)
    ap.add_argument("--dir", type=Path, default=None)
    ap.add_argument("--root", type=Path, default=None, help="agentis/ 디렉토리 (기본: 자동 탐색)")
    ap.add_argument("--llm-hook", type=str, default=None,
                    help="외부 LLM 명령 (stdin → JSON stdout)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if not args.file and not args.dir:
        ap.error("--file 또는 --dir 중 하나는 필요합니다.")

    start = args.root if args.root else Path(__file__).resolve().parent
    agentis_root = find_agentis_root(start)

    targets: list[Path] = []
    if args.file:
        if args.file.is_file():
            targets.append(args.file)
        else:
            print(json.dumps({"error": f"파일 없음: {args.file}"}, ensure_ascii=False))
            return 2
    if args.dir:
        if not args.dir.is_dir():
            print(json.dumps({"error": f"폴더 없음: {args.dir}"}, ensure_ascii=False))
            return 2
        for f in sorted(args.dir.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".md", ".txt", ".pdf", ".docx", ".csv", ".rst", ".markdown"):
                targets.append(f)

    out: list[dict] = []
    for t in targets:
        out.append(ingest_file(t, agentis_root, llm_hook=args.llm_hook, dry_run=args.dry_run))

    print(json.dumps({"agentis_root": str(agentis_root), "results": out},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
