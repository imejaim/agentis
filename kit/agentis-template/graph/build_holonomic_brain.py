#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.10 / build_holonomic_brain
"""
build_holonomic_brain.py — agentis 두뇌 그래프 데이터를 사람용 루트
holonomic-brain.html 로 렌더한다.

기존 graph/graph.html 은 3D 엔진 산출물로 유지하고, 이 파일은 구조·건강·링크 상태를
읽기 쉬운 정적 HTML로 보여준다. mtime/현재시각 없이 markdown 소스에서 결정론 생성.
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import sys
import tempfile
import webbrowser
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

CATEGORY_ORDER = ["core", "concepts", "entities", "sources", "skills", "workflows", "_other"]
LAYER_LABELS = {
    "core": "Core / 정체성",
    "concepts": "Concepts / 개념",
    "entities": "Entities / 대상",
    "sources": "Sources / 원천",
    "skills": "Skills / 실행능력",
    "workflows": "Workflows / 반복절차",
    "_other": "Other",
}


def load_build_graph(graph_dir: Path):
    path = graph_dir / "build_graph.py"
    spec = importlib.util.spec_from_file_location("agentis_build_graph", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[holonomic-brain] build_graph.py 로드 실패: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_agentis_root(start: Path) -> Path:
    p = start.resolve()
    if p.is_file():
        p = p.parent
    for cand in [p, *p.parents]:
        if (cand / "agent.md").exists() or (cand / "memory").is_dir():
            return cand
        if (cand / "agentis" / "memory").is_dir():
            return cand / "agentis"
    return p


def read_holonomic_note(root: Path) -> str:
    note = root / "memory" / "_brain" / "holonomic.md"
    if not note.is_file():
        return "홀로노믹 원리 노트가 아직 없습니다. memory/_brain/holonomic.md 를 만들면 여기에 요약됩니다."
    text = note.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[#>*_`\[\]()-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:520].rstrip() + ("…" if len(text) > 520 else "")


def enrich(graph: dict, root: Path, build_graph_mod) -> dict:
    by_cat: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}
    for node in graph.get("nodes", []):
        by_cat.setdefault(node.get("category", "_other"), []).append(node)
    for nodes in by_cat.values():
        nodes.sort(key=lambda n: n.get("id", ""))
    graph_payload = {k: v for k, v in graph.items() if not k.startswith("_")}
    active = None
    if hasattr(build_graph_mod, "parse_active_node"):
        active = build_graph_mod.parse_active_node(root, graph["_by_slug"], graph["_by_basename"])
    graph_payload["active_node"] = active
    graph_payload["layers"] = [
        {"id": cat, "label": LAYER_LABELS.get(cat, cat), "count": len(by_cat.get(cat, [])), "nodes": by_cat.get(cat, [])[:18]}
        for cat in CATEGORY_ORDER if by_cat.get(cat)
    ]
    graph_payload["holonomic_note"] = read_holonomic_note(root)
    graph_payload["root"] = root.as_posix()
    return graph_payload


def esc(x: object) -> str:
    return html.escape(str(x), quote=True)


def render(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    stats = data.get("stats", {})
    cats = data.get("categories", {})
    layer_html = []
    for layer in data.get("layers", []):
        color = cats.get(layer["id"], {}).get("color", "#64748b")
        nodes = "".join(f"<li><code>{esc(n['id'])}</code><span>{esc(n['label'])}</span><em>deg {esc(n.get('deg', 0))}</em></li>" for n in layer.get("nodes", []))
        layer_html.append(f"""
        <section class="layer" style="--c:{esc(color)}">
          <h2><span></span>{esc(layer['label'])} <b>{layer['count']}</b></h2>
          <ul>{nodes}</ul>
        </section>""")
    broken = data.get("broken", [])[:12]
    broken_html = "".join(f"<li><code>{esc(src)}</code> → <code>[[{esc(tgt)}]]</code></li>" for src, tgt in broken) or "<li>깨진 링크 없음</li>"
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Holonomic Brain</title>
<style>
:root{{--bg:#fbfaf7;--ink:#16181d;--muted:#6b7280;--line:#e5e7eb;--card:#fff;--blue:#2563eb}}
*{{box-sizing:border-box}} body{{margin:0;background:radial-gradient(circle at top left,#e0f2fe 0,#fbfaf7 34%,#f8fafc 100%);color:var(--ink);font:15px/1.58 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
header,main{{max-width:1180px;margin:auto;padding:0 22px}} header{{padding-top:36px}} h1{{font-size:36px;letter-spacing:-.04em;margin:0 0 8px}} .lead{{max-width:840px;color:#475569}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:22px 0}} .stat{{background:rgba(255,255,255,.86);border:1px solid var(--line);border-radius:18px;padding:15px;box-shadow:0 12px 30px rgba(15,23,42,.06)}} .stat b{{display:block;font-size:28px}}
.hero{{display:grid;grid-template-columns:minmax(280px,1.2fr) minmax(260px,.8fr);gap:16px;margin:18px 0}} .panel{{background:rgba(255,255,255,.9);border:1px solid var(--line);border-radius:22px;padding:20px;box-shadow:0 12px 34px rgba(15,23,42,.06)}}
.rings{{display:grid;place-items:center;min-height:300px}} .ring{{width:min(320px,80vw);aspect-ratio:1;border-radius:50%;border:1px dashed #cbd5e1;display:grid;place-items:center;position:relative}} .ring:before{{content:'';position:absolute;inset:17%;border:1px dashed #bfdbfe;border-radius:50%}} .ring:after{{content:'';position:absolute;inset:33%;background:#0f172a;border-radius:50%;box-shadow:0 18px 50px rgba(15,23,42,.25)}} .ring strong{{z-index:1;color:white}}
.layers{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px;margin:18px 0 50px}} .layer{{background:white;border:1px solid var(--line);border-radius:20px;padding:17px;box-shadow:0 10px 28px rgba(15,23,42,.05)}} .layer h2{{font-size:17px;margin:0 0 10px;display:flex;align-items:center;gap:8px}} .layer h2 span{{width:11px;height:11px;border-radius:50%;background:var(--c)}} .layer h2 b{{margin-left:auto;color:var(--muted);font-size:14px}} ul{{margin:0;padding:0;list-style:none}} li{{display:grid;grid-template-columns:1.1fr 1fr auto;gap:8px;padding:7px 0;border-top:1px dashed #edf2f7;align-items:center}} code{{font-size:12px;background:#f1f5f9;border-radius:6px;padding:2px 5px;word-break:break-all}} em{{font-size:12px;color:var(--muted);font-style:normal}} .broken li{{grid-template-columns:1fr}}
.links{{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}} .links a{{color:white;background:#0f172a;text-decoration:none;border-radius:999px;padding:8px 12px;font-size:13px}} .note{{color:#475569}} footer{{max-width:1180px;margin:0 auto 40px;padding:0 22px;color:var(--muted);font-size:13px}}
@media(max-width:780px){{.hero{{grid-template-columns:1fr}} h1{{font-size:30px}} li{{grid-template-columns:1fr}}}}
</style></head><body>
<header>
  <h1>Holonomic Brain</h1>
  <p class="lead">이 에이전트의 기억은 markdown 페이지와 <code>[[wikilink]]</code> 연결로 자랍니다. 이 페이지는 루트에서 바로 여는 사람용 두뇌 지도이며, 3D 실험 뷰는 <code>agentis/graph/graph.html</code>에 유지됩니다.</p>
  <div class="stats"><div class="stat"><b>{esc(stats.get('nodes',0))}</b>nodes</div><div class="stat"><b>{esc(stats.get('edges',0))}</b>links</div><div class="stat"><b>{esc(stats.get('orphans',0))}</b>orphans</div><div class="stat"><b>{esc(stats.get('broken_links',0))}</b>broken</div></div>
</header>
<main>
  <section class="hero">
    <div class="panel rings"><div class="ring"><strong>{esc(data.get('active_node') or 'hot.md')}</strong></div></div>
    <div class="panel"><h2>홀로노믹 원리</h2><p class="note">{esc(data.get('holonomic_note',''))}</p><div class="links"><a href="agentis/graph/graph.html">3D graph</a><a href="workflows.html">workflows</a><a href="agentis/memory/_brain/brain.sqlite">brain index</a></div></div>
  </section>
  <section class="panel broken"><h2>깨진 링크 점검</h2><ul>{broken_html}</ul></section>
  <section class="layers">{''.join(layer_html)}</section>
</main>
<footer>자동 갱신: <code>python agentis/graph/refresh_views.py --workspace .</code> · 원본 root: <code>{esc(data.get('root',''))}</code></footer>
<script>const DATA = {payload};</script>
</body></html>"""


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as fh:
        fh.write(text)
        tmp = Path(fh.name)
    tmp.replace(path)


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="agentis 두뇌를 root holonomic-brain.html 로 렌더")
    ap.add_argument("--root", type=Path, default=here.parent, help="agentis 디렉토리")
    ap.add_argument("--workspace", type=Path, default=None, help="작업 폴더 루트 (기본: agentis 부모)")
    ap.add_argument("--out", type=Path, default=None, help="출력 HTML (기본: <workspace>/holonomic-brain.html)")
    ap.add_argument("--json-out", type=Path, default=None, help="출력 JSON (기본: <workspace>/holonomic-brain.json)")
    ap.add_argument("--open", action="store_true", help="생성 후 브라우저로 열기")
    args = ap.parse_args(argv)

    root = find_agentis_root(args.root)
    workspace = args.workspace.resolve() if args.workspace else root.parent
    graph_mod = load_build_graph(here)
    graph = graph_mod.build(root)
    data = enrich(graph, root, graph_mod)
    out = args.out or (workspace / "holonomic-brain.html")
    json_out = args.json_out or (workspace / "holonomic-brain.json")
    atomic_write(json_out.resolve(), json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    atomic_write(out.resolve(), render(data))
    print(f"[holonomic-brain] root={root} nodes={data['stats']['nodes']} edges={data['stats']['edges']} active={data.get('active_node') or '-'}")
    print(f"[holonomic-brain] -> {out.resolve()} ({out.resolve().stat().st_size} bytes)")
    print(f"[holonomic-brain] -> {json_out.resolve()}")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
