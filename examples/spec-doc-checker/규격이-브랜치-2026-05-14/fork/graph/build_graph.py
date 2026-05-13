#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_graph.py — 에이전트의 "두뇌"(agentis/ 폴더의 마크다운들)를 그래프로 만든다.

훑는 대상:  agentis/agent.md  +  agentis/memory/**/*.md  +  agentis/skills/*/SKILL.md
            +  agentis/workflows/*.workflow.md
            (README.md, *.template.md, _template*.md, graph/ 는 제외 — 스캐폴드라서)
링크:       파일 안의  [[위키링크]]  를 엣지로.
출력:       agentis/graph/graph.json  (노드/엣지/통계 — 결정론적)
            agentis/graph/graph.html  (자체완결형: 외부 의존 0, 인트라넷/오프라인 OK)

표준 라이브러리만 사용. pip 설치 불필요.

사용법:
    python build_graph.py                 # 스크립트 위치 기준 ../  (= agentis/) 를 훑고 ./ 에 출력
    python build_graph.py --root PATH      # agentis/ 디렉토리 지정
    python build_graph.py --out PATH       # 출력 디렉토리 지정
    python build_graph.py --open           # 만든 뒤 graph.html 을 기본 브라우저로 연다
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import webbrowser
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # Windows 콘솔(cp949)에서 한글 출력 안전하게
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|[^\[\]]*)?\]\]")
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

# 카테고리 → (표시이름, 색)  — Obsidian 풍 다크 테마
CATEGORY_STYLE = {
    "core":      ("CORE",      "#7fd1ff"),   # agent / _index / overview / log / hot
    "concepts":  ("CONCEPTS",  "#f0b860"),
    "entities":  ("ENTITIES",  "#9b8cff"),
    "sources":   ("SOURCES",   "#5fcaa0"),
    "skills":    ("SKILLS",    "#ff8a8a"),
    "workflows": ("WORKFLOWS", "#c0c0c0"),
    "_other":    ("OTHER",     "#888888"),
}
CORE_STEMS = {"agent", "_index", "overview", "log", "hot"}

# 스캔에서 제외할 파일명 패턴 (스캐폴드/문서)
def is_excluded(name: str) -> bool:
    n = name.lower()
    return (n == "readme.md"
            or n.endswith(".template.md")
            or n.startswith("_template")
            or n == ".gitkeep")


def find_root(start: Path) -> Path:
    """주어진 경로에서 agentis 루트를 찾는다 (agent.md 또는 memory/ 가 있는 곳)."""
    p = start.resolve()
    if p.is_file():
        p = p.parent
    for cand in [p, *p.parents]:
        if (cand / "agent.md").exists() or (cand / "memory").is_dir():
            return cand
    return p


def collect_md_files(root: Path) -> list[tuple[str, Path, str]]:
    """(node_id, 파일경로, category) 목록. node_id 는 root 기준 의미있는 경로."""
    out: list[tuple[str, Path, str]] = []

    # 1) 루트의 agent.md
    f = root / "agent.md"
    if f.is_file():
        out.append(("agent", f, "core"))

    # 2) memory/**/*.md
    mem = root / "memory"
    if mem.is_dir():
        for f in sorted(mem.rglob("*.md")):
            if not f.is_file() or is_excluded(f.name):
                continue
            rel = f.relative_to(mem)
            node_id = ("memory/" + rel.with_suffix("").as_posix())
            parts = rel.parts
            if len(parts) == 1:
                cat = "core" if rel.stem in CORE_STEMS else "_other"
            else:
                top = parts[0]
                cat = top if top in CATEGORY_STYLE else "_other"
            out.append((node_id, f, cat))

    # 3) skills/*/SKILL.md  ->  node id = skills/<dir>
    sk = root / "skills"
    if sk.is_dir():
        for d in sorted(p for p in sk.iterdir() if p.is_dir()):
            sf = d / "SKILL.md"
            if sf.is_file():
                out.append((f"skills/{d.name}", sf, "skills"))
            # 추가 .md 도 (있으면)
            for f in sorted(d.glob("*.md")):
                if f.name == "SKILL.md" or is_excluded(f.name):
                    continue
                out.append((f"skills/{d.name}/{f.stem}", f, "skills"))

    # 4) workflows/*.workflow.md  ->  node id = workflows/<stem-without-.workflow>
    wf = root / "workflows"
    if wf.is_dir():
        for f in sorted(wf.glob("*.workflow.md")):
            if is_excluded(f.name):
                continue
            stem = f.name[: -len(".workflow.md")]
            out.append((f"workflows/{stem}", f, "workflows"))
        for f in sorted(wf.glob("*.md")):  # .workflow.md 가 아닌 다른 .md
            if f.name.endswith(".workflow.md") or is_excluded(f.name):
                continue
            out.append((f"workflows/{f.stem}", f, "workflows"))

    # 중복 node_id 제거 (먼저 들어온 것 우선)
    seen: set[str] = set()
    uniq = []
    for nid, fp, cat in out:
        if nid in seen:
            continue
        seen.add(nid)
        uniq.append((nid, fp, cat))
    return uniq


def title_of(text: str, fallback: str) -> str:
    m = H1_RE.search(text)
    if m:
        # 선두 이모지/기호 정리
        return re.sub(r"^[#\s]*", "", m.group(1)).strip() or fallback
    return fallback


def build(root: Path):
    files = collect_md_files(root)
    nodes: dict[str, dict] = {}
    raw_text: dict[str, str] = {}
    by_slug: set[str] = set()
    by_basename: dict[str, list[str]] = {}

    for node_id, fp, cat in files:
        text = fp.read_text(encoding="utf-8", errors="replace")
        raw_text[node_id] = text
        # 표시 라벨: 파일 H1, 단 SKILL.md 면 폴더명, agent.md 면 H1(에이전트 이름)
        fallback = Path(node_id).name
        label = title_of(text, fallback)
        nodes[node_id] = {"id": node_id, "label": label, "category": cat, "deg": 0}
        by_slug.add(node_id)
        by_basename.setdefault(Path(node_id).name.lower(), []).append(node_id)
        # memory/foo 는 [[foo]] 로도 찾을 수 있게 basename 등록 (이미 위에서 됨)

    def resolve(target: str):
        t = target.strip().strip("/")
        if not t:
            return None
        t = re.sub(r"\.md$", "", t, flags=re.IGNORECASE)
        # 1) 정확한 node id
        if t in by_slug:
            return t
        # 2) "memory/" 접두 보정 (memory/concepts/x <-> concepts/x)
        for pref in ("memory/",):
            if (pref + t) in by_slug:
                return pref + t
            if t.startswith(pref) and t[len(pref):] in by_slug:
                return t[len(pref):]
        # 3) basename 일치
        base = Path(t).name.lower()
        cands = by_basename.get(base)
        if cands:
            return sorted(cands)[0]   # 결정론
        return None

    edges: list[dict] = []
    seen_e: set[tuple[str, str]] = set()
    broken: list[tuple[str, str]] = []
    for src, text in raw_text.items():
        for m in WIKILINK_RE.finditer(text):
            tgt = resolve(m.group(1))
            if tgt is None:
                broken.append((src, m.group(1).strip()))
                continue
            if tgt == src:
                continue
            key = (src, tgt)
            if key in seen_e:
                continue
            seen_e.add(key)
            edges.append({"source": src, "target": tgt})
            nodes[src]["deg"] += 1
            nodes[tgt]["deg"] += 1

    node_list = sorted(nodes.values(), key=lambda n: n["id"])
    edge_list = sorted(edges, key=lambda e: (e["source"], e["target"]))
    stats = {
        "nodes": len(node_list),
        "edges": len(edge_list),
        "orphans": sum(1 for n in node_list if n["deg"] == 0),
        "broken_links": len(broken),
        "by_category": {c: sum(1 for n in node_list if n["category"] == c)
                        for c in sorted({n["category"] for n in node_list})},
    }
    return {"nodes": node_list, "edges": edge_list, "stats": stats,
            "broken": sorted(set(broken)),
            "categories": {k: {"label": v[0], "color": v[1]} for k, v in CATEGORY_STYLE.items()}}


# --------------------------------------------------------------------------
# 자체완결형 HTML (D3 등 외부 의존 없음 — 손으로 짠 force 레이아웃 + SVG)
# --------------------------------------------------------------------------
HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>Agentis — 두뇌 그래프</title>
<style>
  html,body{margin:0;height:100%;background:#0e1116;color:#cdd3da;font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow:hidden}
  #hud{position:fixed;left:14px;top:12px;z-index:10;background:rgba(14,17,22,.78);border:1px solid #2a313c;border-radius:8px;padding:10px 12px;backdrop-filter:blur(4px);max-width:280px}
  #hud h1{font-size:13px;margin:0 0 6px;color:#e7ecf2;letter-spacing:.04em}
  #hud .stat{color:#8b95a1;font-size:12px}
  #legend{margin-top:8px;display:flex;flex-wrap:wrap;gap:6px 10px}
  #legend span{display:inline-flex;align-items:center;gap:5px;font-size:11px;color:#9aa4af;cursor:default}
  #legend i{width:9px;height:9px;border-radius:50%;display:inline-block}
  #tip{position:fixed;pointer-events:none;background:#1b212b;border:1px solid #333c48;border-radius:6px;padding:4px 8px;font-size:12px;color:#e7ecf2;opacity:0;transition:opacity .1s;z-index:20}
  #hint{position:fixed;right:14px;bottom:12px;color:#5b6470;font-size:11px;z-index:10}
  svg{width:100vw;height:100vh;display:block;cursor:grab}
  svg:active{cursor:grabbing}
  .link{stroke:#3a424e;stroke-opacity:.5}
  .node circle{stroke:#0e1116;stroke-width:1.4px;cursor:pointer}
  .node text{fill:#aeb6bf;font-size:10px;paint-order:stroke;stroke:#0e1116;stroke-width:3px;stroke-linejoin:round;pointer-events:none}
  .dim{opacity:.12}
  .link.dim{stroke-opacity:.05}
</style></head><body>
<div id="hud">
  <h1>🧠 AGENTIS — 두뇌 그래프</h1>
  <div class="stat" id="stat"></div>
  <div id="legend"></div>
</div>
<div id="tip"></div>
<div id="hint">드래그=이동 · 휠=확대 · 노드 드래그=고정 · 노드 클릭=이웃 강조 · 빈 곳 클릭=해제</div>
<svg id="svg"></svg>
<script>
const DATA = /*__DATA__*/;
const CAT = DATA.categories;
const svg = document.getElementById('svg');
const tip = document.getElementById('tip');
const NS = 'http://www.w3.org/2000/svg';
let W = innerWidth, H = innerHeight;

const nodes = DATA.nodes.map(n => ({...n,
  x: W/2 + (Math.random()-.5)*Math.min(W,H)*0.6,
  y: H/2 + (Math.random()-.5)*Math.min(W,H)*0.6, vx:0, vy:0, fixed:false}));
const idx = Object.fromEntries(nodes.map((n,i)=>[n.id,i]));
const links = DATA.edges.map(e=>({s:idx[e.source],t:idx[e.target]})).filter(e=>e.s!=null&&e.t!=null);
nodes.forEach(n=>{ n.r = 4 + Math.sqrt(n.deg)*2.2; });

let tx=0,ty=0,scale=1;
const root=document.createElementNS(NS,'g'); svg.appendChild(root);
const gL=document.createElementNS(NS,'g'); root.appendChild(gL);
const gN=document.createElementNS(NS,'g'); root.appendChild(gN);
function applyView(){ root.setAttribute('transform',`translate(${tx},${ty}) scale(${scale})`); }

const linkEls=links.map(()=>{const l=document.createElementNS(NS,'line');l.setAttribute('class','link');gL.appendChild(l);return l;});
const nodeEls=nodes.map(n=>{
  const g=document.createElementNS(NS,'g'); g.setAttribute('class','node');
  const c=document.createElementNS(NS,'circle'); c.setAttribute('r',n.r);
  c.setAttribute('fill',(CAT[n.category]||CAT._other).color);
  const t=document.createElementNS(NS,'text'); t.setAttribute('x',n.r+3); t.setAttribute('y',3);
  t.textContent=n.label.length>30? n.label.slice(0,29)+'…':n.label;
  if(nodes.length>120 && n.deg<2) t.setAttribute('opacity','0');
  g.appendChild(c); g.appendChild(t); gN.appendChild(g); g._n=n; g._c=c; g._t=t;
  c.addEventListener('mouseenter',ev=>{tip.textContent=n.label+'  ('+(CAT[n.category]||CAT._other).label.toLowerCase()+', deg '+n.deg+')';tip.style.opacity=1;mv(ev);});
  c.addEventListener('mousemove',mv); c.addEventListener('mouseleave',()=>tip.style.opacity=0);
  c.addEventListener('click',ev=>{ev.stopPropagation();focusOn(n);});
  return g;
});
function mv(ev){tip.style.left=(ev.clientX+12)+'px';tip.style.top=(ev.clientY+10)+'px';}

const adj=nodes.map(()=>new Set());
links.forEach(l=>{adj[l.s].add(l.t);adj[l.t].add(l.s);});
let focus=null;
function focusOn(n){
  focus=(focus===n)?null:n;
  nodeEls.forEach((g,i)=>{const on=!focus||i===idx[focus.id]||adj[idx[focus.id]].has(i);g.classList.toggle('dim',focus&&!on);});
  linkEls.forEach((el,i)=>{const l=links[i];const on=!focus||l.s===idx[focus.id]||l.t===idx[focus.id];el.classList.toggle('dim',focus&&!on);});
}
svg.addEventListener('click',()=>{if(focus){focus=null;nodeEls.forEach(g=>g.classList.remove('dim'));linkEls.forEach(e=>e.classList.remove('dim'));}});

let alpha=1;
function tick(){
  alpha*=0.992; if(alpha<0.004)alpha=0.004;
  for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
    const a=nodes[i],b=nodes[j];let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy||0.01;
    const f=1800/d2*alpha,d=Math.sqrt(d2),fx=dx/d*f,fy=dy/d*f;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;
  }
  const L=72;
  for(const l of links){const a=nodes[l.s],b=nodes[l.t];let dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)||0.01;
    const f=(d-L)*0.036,fx=dx/d*f,fy=dy/d*f;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;}
  for(const n of nodes){n.vx+=(W/2-n.x)*0.0009;n.vy+=(H/2-n.y)*0.0009;}
  for(const n of nodes){if(n.fixed)continue;n.vx*=0.82;n.vy*=0.82;n.x+=n.vx;n.y+=n.vy;}
  for(let i=0;i<links.length;i++){const l=links[i],a=nodes[l.s],b=nodes[l.t],el=linkEls[i];
    el.setAttribute('x1',a.x);el.setAttribute('y1',a.y);el.setAttribute('x2',b.x);el.setAttribute('y2',b.y);}
  for(let i=0;i<nodes.length;i++)nodeEls[i].setAttribute('transform','translate('+nodes[i].x+','+nodes[i].y+')');
  requestAnimationFrame(tick);
}
let panning=false,px=0,py=0,dragging=null;
svg.addEventListener('mousedown',ev=>{if(ev.target===svg||ev.target===root){panning=true;px=ev.clientX;py=ev.clientY;}});
addEventListener('mousemove',ev=>{
  if(panning){tx+=ev.clientX-px;ty+=ev.clientY-py;px=ev.clientX;py=ev.clientY;applyView();}
  if(dragging){const r=svg.getBoundingClientRect();dragging.x=(ev.clientX-r.left-tx)/scale;dragging.y=(ev.clientY-r.top-ty)/scale;dragging.vx=dragging.vy=0;alpha=Math.max(alpha,0.3);}
});
addEventListener('mouseup',()=>{panning=false;dragging=null;});
svg.addEventListener('wheel',ev=>{ev.preventDefault();const s=Math.exp(-ev.deltaY*0.0015),mx=ev.clientX,my=ev.clientY;tx=mx-(mx-tx)*s;ty=my-(my-ty)*s;scale*=s;applyView();},{passive:false});
nodeEls.forEach(g=>g._c.addEventListener('mousedown',ev=>{ev.stopPropagation();dragging=g._n;dragging.fixed=true;}));

document.getElementById('stat').textContent=
  `${DATA.stats.nodes} 노드 · ${DATA.stats.edges} 링크 · 고아 ${DATA.stats.orphans}`+(DATA.stats.broken_links?` · 깨진링크 ${DATA.stats.broken_links}`:'');
const used=[...new Set(nodes.map(n=>n.category))].sort();
document.getElementById('legend').innerHTML=used.map(c=>{const s=CAT[c]||CAT._other;const k=DATA.stats.by_category[c]||0;return `<span><i style="background:${s.color}"></i>${s.label} ${k}</span>`;}).join('');
addEventListener('resize',()=>{W=innerWidth;H=innerHeight;});
applyView();tick();
</script></body></html>
"""


def write_outputs(graph: dict, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "graph.json"
    json_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    html = HTML_TEMPLATE.replace("/*__DATA__*/", json.dumps(graph, ensure_ascii=False))
    html_path = out_dir / "graph.html"
    html_path.write_text(html, encoding="utf-8")
    return json_path, html_path


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent          # .../agentis/graph
    ap = argparse.ArgumentParser(description="agentis/ 두뇌를 그래프로 빌드")
    ap.add_argument("--root", type=Path, default=here.parent, help="agentis 디렉토리 (기본: 스크립트 기준 ../)")
    ap.add_argument("--out", type=Path, default=here, help="출력 디렉토리 (기본: 스크립트 폴더)")
    ap.add_argument("--open", action="store_true", help="만든 뒤 graph.html 을 브라우저로 연다")
    args = ap.parse_args(argv)

    root = find_root(args.root)
    if not ((root / "agent.md").exists() or (root / "memory").is_dir()):
        print(f"[build_graph] agentis 루트를 찾을 수 없음 (agent.md 나 memory/ 가 있어야 함): {root}", file=sys.stderr)
        return 2

    graph = build(root)
    json_path, html_path = write_outputs(graph, args.out.resolve())
    s = graph["stats"]
    print(f"[build_graph] root={root}")
    print(f"[build_graph] {s['nodes']} 노드 / {s['edges']} 링크 / 고아 {s['orphans']} / 깨진링크 {s['broken_links']}")
    print(f"[build_graph] 카테고리: " + ", ".join(f"{k} {v}" for k, v in s["by_category"].items()))
    print(f"[build_graph] -> {json_path}")
    print(f"[build_graph] -> {html_path}")
    if graph["broken"]:
        print("[build_graph] 깨진 [[링크]] (대상 페이지 없음 — 오타이거나 아직 안 만든 페이지):")
        for src, tgt in graph["broken"][:20]:
            print(f"   {src}  ->  [[{tgt}]]")
    if args.open:
        webbrowser.open(html_path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
