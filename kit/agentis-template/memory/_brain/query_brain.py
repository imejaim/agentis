#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.5 / query_brain
"""
query_brain.py — Graph RAG 쿼리 인터페이스 (사내·오프라인 친화).

모드:
  keyword  : SQLite FTS5 (BM25) — 항상 동작 (stdlib only).
  semantic : sentence-transformers + FAISS — 패키지 있을 때만.
             모델: paraphrase-multilingual-MiniLM-L12-v2 (한국어 OK, ~117MB).
             임베딩 캐시: <_brain>/embeddings.npy + ids.json.
  graph    : keyword/semantic 시드 → graph.json 의 1-hop 확장.
  hybrid   : keyword + semantic (있으면) RRF 결합 → graph 1-hop 보강. (기본)

가용성 폴백: sentence-transformers / faiss / numpy 가 없으면 자동으로
keyword + graph 만 사용. 한 줄 안내.

사용:
  python query_brain.py "<자연어 질문>" [--k 5] [--mode hybrid|semantic|keyword|graph] [--pretty]
  python query_brain.py "<질문>" --db <brain.sqlite> --graph <graph.json>
"""
from __future__ import annotations
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


# ─── 가용성 체크 ─────────────────────────────────────────────────────────
def _check_semantic() -> tuple[bool, str]:
    try:
        import numpy  # noqa: F401
    except Exception:
        return False, "numpy 없음"
    try:
        import sentence_transformers  # noqa: F401
    except Exception:
        return False, "sentence-transformers 없음 (pip install sentence-transformers)"
    try:
        import faiss  # noqa: F401
    except Exception:
        # FAISS 없어도 numpy 코사인으로 폴백 가능
        return True, "faiss 없음 (numpy 코사인으로 폴백)"
    return True, "OK"


# ─── 경로 탐색 ────────────────────────────────────────────────────────────
def find_brain_root(start: Path) -> Path:
    p = (start if start.is_dir() else start.parent).resolve()
    for c in [p, *p.parents]:
        if (c / "memory" / "_brain").is_dir() or (c / "_brain").is_dir():
            if (c / "memory" / "_brain").is_dir():
                return c
            return c.parent  # _brain 폴더의 부모의 부모(= agentis/)
        if (c / "agent.md").exists() or (c / "memory").is_dir():
            return c
    return p


# ─── FTS5 BM25 키워드 검색 ────────────────────────────────────────────────
def _fts_query_string(q: str) -> str:
    """FTS5 가 받아먹기 쉽게 토큰 단위로 OR. 짧은 토큰/구두점 제거."""
    toks = [t for t in re.split(r"[\s,./()\[\]{}!?\"'·,]+", q) if len(t) >= 2]
    if not toks:
        return '""'
    # 한글/영문 혼합에도 안전하게 따옴표로 감싸기
    return " OR ".join(f'"{t}"' for t in toks)


def keyword_search(db: Path, query: str, k: int = 10) -> list[dict]:
    if not db.is_file():
        return []
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    fts_q = _fts_query_string(query)
    results: list[dict] = []
    try:
        # FTS5 bm25() — 점수는 낮을수록 좋음 → 부호 뒤집어 비교
        cur.execute(
            "SELECT path, title, bm25(pages_fts) AS bm, snippet(pages_fts, 2, '«', '»', '…', 12) AS snip "
            "FROM pages_fts WHERE pages_fts MATCH ? ORDER BY bm LIMIT ?",
            (fts_q, k),
        )
        rows = cur.fetchall()
        for r in rows:
            results.append({
                "path": r["path"],
                "title": r["title"],
                "score": float(-r["bm"]),  # 높을수록 좋게 변환
                "snippet": r["snip"] or "",
                "source": "keyword",
            })
    except sqlite3.OperationalError:
        # FTS4 또는 일반 테이블 폴백
        like = "%" + query[:60].replace("%", "") + "%"
        cur.execute(
            "SELECT path, title, substr(body,1,200) AS snip FROM pages_fts "
            "WHERE body LIKE ? OR title LIKE ? LIMIT ?",
            (like, like, k),
        )
        for r in cur.fetchall():
            results.append({
                "path": r["path"], "title": r["title"], "score": 0.5,
                "snippet": r["snip"], "source": "keyword-like",
            })
    con.close()
    return results


# ─── 의미 검색 (semantic) ─────────────────────────────────────────────────
def _build_or_load_embeddings(db: Path, brain_dir: Path):
    """페이지 본문 임베딩을 캐시(<brain>/embeddings.npy + ids.json) 로 관리.
    가용 시 sentence-transformers, FAISS 사용. 폴백은 numpy 코사인.
    """
    import numpy as np
    from sentence_transformers import SentenceTransformer
    model_name = "paraphrase-multilingual-MiniLM-L12-v2"
    emb_npy = brain_dir / "embeddings.npy"
    ids_js = brain_dir / "ids.json"
    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.execute("SELECT id, path, title, content_hash FROM pages ORDER BY id")
    rows = cur.fetchall()
    cur2 = con.cursor()
    # 텍스트(제목 + body 상단)는 별도 조회
    texts: list[str] = []
    for pid, path, title, ch in rows:
        cur2.execute("SELECT body FROM pages_fts WHERE path = ? LIMIT 1", (path,))
        b = cur2.fetchone()
        body = (b[0] if b and b[0] else "")[:1500]
        texts.append(f"{title}\n{body}")
    ids = [{"id": r[0], "path": r[1], "title": r[2], "hash": r[3]} for r in rows]
    con.close()

    # 캐시 유효성: ids.json 의 hash 들이 그대로면 재사용.
    if emb_npy.is_file() and ids_js.is_file():
        try:
            cached = json.loads(ids_js.read_text(encoding="utf-8"))
            same = (len(cached) == len(ids) and all(
                cached[i].get("path") == ids[i]["path"] and cached[i].get("hash") == ids[i]["hash"]
                for i in range(len(ids))
            ))
            if same:
                embs = np.load(emb_npy)
                return embs, ids
        except Exception:
            pass

    model = SentenceTransformer(model_name)
    embs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    embs = np.asarray(embs, dtype="float32")
    np.save(emb_npy, embs)
    ids_js.write_text(json.dumps(ids, ensure_ascii=False, indent=2), encoding="utf-8")
    return embs, ids


def semantic_search(db: Path, brain_dir: Path, query: str, k: int = 10) -> list[dict]:
    import numpy as np
    from sentence_transformers import SentenceTransformer
    embs, ids = _build_or_load_embeddings(db, brain_dir)
    model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    q = model.encode([query], normalize_embeddings=True)
    q = np.asarray(q, dtype="float32")[0]
    # FAISS 가능하면 사용
    try:
        import faiss
        index = faiss.IndexFlatIP(embs.shape[1])
        index.add(embs)
        D, I = index.search(q.reshape(1, -1), min(k, len(ids)))
        scored = [(float(D[0][i]), int(I[0][i])) for i in range(len(I[0]))]
    except Exception:
        sims = (embs @ q).astype("float32")
        order = sims.argsort()[::-1][:k]
        scored = [(float(sims[i]), int(i)) for i in order]
    out: list[dict] = []
    for s, idx in scored:
        if idx < 0 or idx >= len(ids):
            continue
        meta = ids[idx]
        out.append({
            "path": meta["path"], "title": meta["title"],
            "score": float(s), "snippet": "", "source": "semantic",
        })
    return out


# ─── 그래프 1-hop 확장 ────────────────────────────────────────────────────
def _load_graph(graph_json: Path) -> tuple[dict, list[dict]]:
    if not graph_json.is_file():
        return {}, []
    try:
        data = json.loads(graph_json.read_text(encoding="utf-8"))
    except Exception:
        return {}, []
    nodes = {n.get("id"): n for n in data.get("nodes", []) if n.get("id")}
    edges = data.get("edges") or data.get("links") or []
    return nodes, edges


def _path_to_node_id(rel_path: str) -> str:
    """memory/concepts/foo.md  → memory/concepts/foo  (build_graph.py 의 node_id 규칙).
    agent.md → agent.
    """
    p = rel_path
    if p.endswith(".md"):
        p = p[:-3]
    return p


def graph_expand(seeds: list[str], graph_json: Path, max_neighbors: int = 5) -> dict[str, list[str]]:
    nodes, edges = _load_graph(graph_json)
    if not nodes:
        return {s: [] for s in seeds}
    neigh: dict[str, list[str]] = {s: [] for s in seeds}
    seed_ids = {_path_to_node_id(s) for s in seeds}
    for e in edges:
        src = e.get("source") or e.get("src") or e.get("from")
        dst = e.get("target") or e.get("dst") or e.get("to")
        if not src or not dst:
            continue
        if src in seed_ids and dst not in seed_ids:
            seed_path = src + ".md"
            neigh.setdefault(seed_path, []).append(dst)
        if dst in seed_ids and src not in seed_ids:
            seed_path = dst + ".md"
            neigh.setdefault(seed_path, []).append(src)
    # cap
    for k, v in list(neigh.items()):
        # dedupe + cap
        seen = []
        for x in v:
            if x not in seen:
                seen.append(x)
        neigh[k] = seen[:max_neighbors]
    return neigh


# ─── RRF 결합 ─────────────────────────────────────────────────────────────
def rrf_merge(*rankings: list[dict], k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion. 입력: 각 모달의 정렬된 결과 list[dict] (path 기준).
    출력: path별로 합쳐서 점수 내림차순.
    """
    score: dict[str, float] = {}
    meta: dict[str, dict] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            p = item["path"]
            score[p] = score.get(p, 0.0) + 1.0 / (k + rank)
            if p not in meta:
                meta[p] = dict(item)
            else:
                # snippet 이 빈 쪽을 채워줌
                if not meta[p].get("snippet") and item.get("snippet"):
                    meta[p]["snippet"] = item["snippet"]
                meta[p]["source"] = meta[p].get("source", "") + "+" + item.get("source", "")
    out = []
    for p, s in sorted(score.items(), key=lambda kv: -kv[1]):
        m = meta[p]
        m["score"] = round(s, 6)
        out.append(m)
    return out


# ─── 메인 검색 ────────────────────────────────────────────────────────────
def query(query_str: str, *, db: Path, brain_dir: Path, graph_json: Path,
          mode: str = "hybrid", k: int = 5) -> dict:
    notes: list[str] = []
    sem_ok, sem_msg = _check_semantic()
    chosen_mode = mode
    if mode in ("semantic", "hybrid") and not sem_ok:
        notes.append(f"semantic 사용 불가({sem_msg}). keyword+graph 로 폴백.")
        chosen_mode = "keyword" if mode == "semantic" else "hybrid-kw-only"

    rankings: list[list[dict]] = []
    if chosen_mode in ("keyword", "hybrid", "hybrid-kw-only", "graph"):
        rankings.append(keyword_search(db, query_str, k=max(k * 2, 10)))
    if chosen_mode in ("semantic", "hybrid") and sem_ok:
        try:
            rankings.append(semantic_search(db, brain_dir, query_str, k=max(k * 2, 10)))
        except Exception as e:
            notes.append(f"semantic 실행 실패: {e}. keyword 로 진행.")

    if not rankings:
        return {"query": query_str, "mode": chosen_mode, "results": [], "notes": notes}

    if chosen_mode in ("hybrid", "hybrid-kw-only"):
        merged = rrf_merge(*rankings)
    else:
        merged = rankings[0]

    top = merged[:k]
    if chosen_mode in ("graph", "hybrid", "hybrid-kw-only", "keyword", "semantic"):
        # graph 모드든 기본이든 1-hop neighbors 는 항상 주는 게 RAG 적
        seeds = [r["path"] for r in top]
        neigh = graph_expand(seeds, graph_json, max_neighbors=5)
        for r in top:
            r["neighbors"] = neigh.get(r["path"], [])

    return {
        "query": query_str,
        "mode": chosen_mode,
        "results": top,
        "notes": notes,
    }


# ─── 사람용 출력 ──────────────────────────────────────────────────────────
def pretty(result: dict) -> str:
    out = []
    out.append(f"질문: {result['query']}")
    out.append(f"모드: {result['mode']}")
    if result.get("notes"):
        for n in result["notes"]:
            out.append(f"  ※ {n}")
    out.append("")
    if not result["results"]:
        out.append("  (결과 없음)")
        return "\n".join(out)
    for i, r in enumerate(result["results"], 1):
        out.append(f"{i}. {r['title']}  ({r['path']})")
        out.append(f"   score={r.get('score', 0):.4f}  source={r.get('source', '?')}")
        if r.get("snippet"):
            out.append(f"   …{r['snippet'][:160]}")
        if r.get("neighbors"):
            out.append(f"   이웃: {', '.join(r['neighbors'][:5])}")
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="agentis 두뇌 — Graph RAG 쿼리")
    ap.add_argument("query", nargs="?", help="자연어 질문")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--mode", choices=["hybrid", "keyword", "semantic", "graph"], default="hybrid")
    ap.add_argument("--db", type=Path, default=None, help="brain.sqlite 경로")
    ap.add_argument("--graph", type=Path, default=None, help="graph.json 경로")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--check", action="store_true", help="가용성만 확인하고 끝")
    args = ap.parse_args(argv)

    if args.check:
        ok, msg = _check_semantic()
        print(f"semantic: {'OK' if ok else 'N/A'} — {msg}")
        return 0

    if not args.query:
        ap.error("질문을 주세요. 예: query_brain.py \"규격 인증 절차\"")

    here = Path(__file__).resolve().parent
    # _brain 디렉토리 기준
    brain_dir = here
    if not (brain_dir / "build_brain_index.py").exists():
        # 다른 위치에서 실행됐을 수 있음 — 탐색
        root = find_brain_root(here)
        brain_dir = root / "memory" / "_brain"
        if not brain_dir.is_dir():
            print(json.dumps({"error": "_brain 디렉토리를 못 찾음. --db 를 지정하세요."}, ensure_ascii=False))
            return 2

    db = args.db or (brain_dir / "brain.sqlite")
    # agentis/ 루트 추정
    agentis_root = brain_dir.parent.parent if brain_dir.name == "_brain" else brain_dir.parent
    graph_json = args.graph or (agentis_root / "graph" / "graph.json")

    if not db.is_file():
        print(json.dumps({"error": f"brain.sqlite 없음 — 먼저 build_brain_index.py 실행. 경로: {db}"},
                         ensure_ascii=False))
        return 2

    result = query(args.query, db=db, brain_dir=brain_dir, graph_json=graph_json,
                   mode=args.mode, k=args.k)
    if args.pretty:
        print(pretty(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
