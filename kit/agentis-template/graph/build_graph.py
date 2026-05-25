#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.5 / build_graph
"""
build_graph.py — 에이전트의 "두뇌"(agentis/ 폴더의 마크다운들)를 **3D 그래프**로 만든다.

훑는 대상:  agentis/agent.md  +  agentis/memory/**/*.md  +  agentis/skills/*/SKILL.md
            +  agentis/workflows/*.workflow.md
            (README.md, *.template.md, _template*.md, graph/ 는 제외 — 스캐폴드라서)
링크:       파일 안의  [[위키링크]]  를 엣지로.
출력:       agentis/graph/graph.json  (노드/엣지/통계 — 결정론적)
            agentis/graph/graph.html  (3D 자체완결: Three.js + 3d-force-graph 인라인, 외부 의존 0)

라이브러리: agentis/graph/vendor/three.min.js + 3d-force-graph.min.js  (키트 동봉, MIT)
표준 라이브러리만 사용 (인라이닝은 read_text + replace). pip 설치 불필요.

사용법:
    python build_graph.py                  # 스크립트 위치 기준 ../ (= agentis/) 를 훑고 ./ 에 출력
    python build_graph.py --root PATH      # agentis/ 디렉토리 지정
    python build_graph.py --out PATH       # 출력 디렉토리 지정
    python build_graph.py --open           # 만든 뒤 graph.html 을 기본 브라우저로 연다
    python build_graph.py --vendor PATH    # vendor 폴더 지정 (기본: 스크립트 옆 vendor/)
"""
from __future__ import annotations
import argparse
import base64
import json
import re
import sys
import webbrowser
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
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
CORE_STEMS = {"agent", "_index", "overview", "log", "hot", "stats"}


def is_excluded(name: str) -> bool:
    n = name.lower()
    return (n == "readme.md"
            or n.endswith(".template.md")
            or n.startswith("_template")
            or n == ".gitkeep")


def find_root(start: Path) -> Path:
    p = start.resolve()
    if p.is_file():
        p = p.parent
    for cand in [p, *p.parents]:
        if (cand / "agent.md").exists() or (cand / "memory").is_dir():
            return cand
    return p


def collect_md_files(root: Path) -> list[tuple[str, Path, str]]:
    out: list[tuple[str, Path, str]] = []

    f = root / "agent.md"
    if f.is_file():
        out.append(("agent", f, "core"))

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

    sk = root / "skills"
    if sk.is_dir():
        for d in sorted(p for p in sk.iterdir() if p.is_dir()):
            sf = d / "SKILL.md"
            if sf.is_file():
                out.append((f"skills/{d.name}", sf, "skills"))
            for f in sorted(d.glob("*.md")):
                if f.name == "SKILL.md" or is_excluded(f.name):
                    continue
                out.append((f"skills/{d.name}/{f.stem}", f, "skills"))

    wf = root / "workflows"
    if wf.is_dir():
        for f in sorted(wf.glob("*.workflow.md")):
            if is_excluded(f.name):
                continue
            stem = f.name[: -len(".workflow.md")]
            out.append((f"workflows/{stem}", f, "workflows"))
        for f in sorted(wf.glob("*.md")):
            if f.name.endswith(".workflow.md") or is_excluded(f.name):
                continue
            out.append((f"workflows/{f.stem}", f, "workflows"))

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
        fallback = Path(node_id).name
        label = title_of(text, fallback)
        nodes[node_id] = {"id": node_id, "label": label, "category": cat, "deg": 0}
        by_slug.add(node_id)
        by_basename.setdefault(Path(node_id).name.lower(), []).append(node_id)

    def resolve(target: str):
        t = target.strip().strip("/")
        if not t:
            return None
        t = re.sub(r"\.md$", "", t, flags=re.IGNORECASE)
        if t in by_slug:
            return t
        for pref in ("memory/",):
            if (pref + t) in by_slug:
                return pref + t
            if t.startswith(pref) and t[len(pref):] in by_slug:
                return t[len(pref):]
        base = Path(t).name.lower()
        cands = by_basename.get(base)
        if cands:
            return sorted(cands)[0]
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
            "categories": {k: {"label": v[0], "color": v[1]} for k, v in CATEGORY_STYLE.items()},
            "_by_slug": by_slug, "_by_basename": by_basename}


def extract_agent_name(root: Path) -> str:
    f = root / "agent.md"
    if not f.is_file():
        return "Agentis"
    txt = f.read_text(encoding="utf-8", errors="replace")
    m = H1_RE.search(txt)
    return (m.group(1).strip() if m else "Agentis") or "Agentis"


# ─────────────────────────────────────────────────────────────────────
# v1.5 — 캐릭터 빌보드 + 활성 노드 추적 (v1.4.1)
# ─────────────────────────────────────────────────────────────────────
# agent.md 의 `character:` 필드(또는 본문 한 줄) → 곰/개구리/고양이 선택. 기본 코부장.
CHARACTER_FILES = {
    "코부장": "Ko-bujang.svg",
    "ko-bujang": "Ko-bujang.svg",
    "kobujang": "Ko-bujang.svg",
    "오과장": "Oh-gwajang.svg",
    "oh-gwajang": "Oh-gwajang.svg",
    "ohgwajang": "Oh-gwajang.svg",
    "젬대리": "Jem-daeri.svg",
    "jem-daeri": "Jem-daeri.svg",
    "jemdaeri": "Jem-daeri.svg",
}
CHARACTER_RE = re.compile(r"^\s*[-*]?\s*\**\s*character\s*\**\s*[:=]\s*\**\s*([^\n*<]+)", re.IGNORECASE | re.MULTILINE)
WIKILINK_FIRST_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|[^\[\]]*)?\]\]")


def parse_character_choice(root: Path) -> str:
    """agent.md 에서 `character:` 필드를 찾는다. 없으면 기본 '코부장'."""
    f = root / "agent.md"
    if not f.is_file():
        return "코부장"
    text = f.read_text(encoding="utf-8", errors="replace")
    m = CHARACTER_RE.search(text)
    if not m:
        return "코부장"
    raw = m.group(1).strip().strip("`'\"").lower()
    # 정규화: 한글 그대로면 그대로, 영문/하이픈/공백은 비교용으로 lower-stripped
    key_kr = m.group(1).strip().strip("`'\"")
    if key_kr in CHARACTER_FILES:
        return key_kr
    if raw in CHARACTER_FILES:
        return raw
    return "코부장"


def parse_active_node(root: Path, by_slug: set[str], by_basename: dict[str, list[str]]) -> str | None:
    """memory/hot.md 의 첫 [[위키링크]] → 활성 노드 ID. 없으면 None."""
    hot = root / "memory" / "hot.md"
    if not hot.is_file():
        return None
    text = hot.read_text(encoding="utf-8", errors="replace")
    for m in WIKILINK_FIRST_RE.finditer(text):
        t = m.group(1).strip().strip("/")
        if not t:
            continue
        t = re.sub(r"\.md$", "", t, flags=re.IGNORECASE)
        if t in by_slug:
            return t
        if ("memory/" + t) in by_slug:
            return "memory/" + t
        base = Path(t).name.lower()
        cands = by_basename.get(base)
        if cands:
            return sorted(cands)[0]
    return None


def load_character_data_uri(vendor_dir: Path, choice: str) -> tuple[str, str] | None:
    """캐릭터 SVG 를 base64 data URI 로. (data_uri, 표시 이름) 또는 None.

    SVG 는 `kit/agentis-template/graph/assets/characters/` 또는 (사용자 키트 기준)
    `<graph>/assets/characters/` 에 있다. vendor_dir 옆 assets/characters 를 우선 본다.
    """
    fname = CHARACTER_FILES.get(choice)
    if not fname:
        return None
    # vendor_dir 는 보통 .../graph/vendor → 캐릭터는 .../graph/assets/characters
    graph_dir = vendor_dir.parent if vendor_dir.name == "vendor" else vendor_dir
    candidates = [
        graph_dir / "assets" / "characters" / fname,
        vendor_dir.parent / "assets" / "characters" / fname,
    ]
    for c in candidates:
        if c.is_file():
            try:
                raw = c.read_bytes()
            except Exception:
                continue
            b64 = base64.b64encode(raw).decode("ascii")
            return f"data:image/svg+xml;base64,{b64}", choice
    return None


# ─────────────────────────────────────────────────────────────────────
# 3D HTML 템플릿 (Three.js + 3d-force-graph 인라인)
# ─────────────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>__TITLE__</title>
<style>
  html,body{margin:0;height:100%;background:#070a10;color:#cdd3da;font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;overflow:hidden}
  #graph{width:100vw;height:100vh}
  #hud{position:fixed;left:14px;top:12px;z-index:10;background:rgba(14,17,22,.78);border:1px solid #2a313c;border-radius:10px;padding:12px 14px;backdrop-filter:blur(6px);max-width:320px}
  #hud h1{font-size:13px;margin:0 0 6px;color:#e7ecf2;letter-spacing:.04em;font-weight:600}
  #hud .stat{color:#8b95a1;font-size:12px}
  #legend{margin-top:8px;display:flex;flex-wrap:wrap;gap:6px 10px}
  #legend span{display:inline-flex;align-items:center;gap:5px;font-size:11px;color:#9aa4af;cursor:pointer;user-select:none}
  #legend i{width:9px;height:9px;border-radius:50%;display:inline-block}
  #legend span.off{opacity:.35}
  #hint{position:fixed;right:14px;bottom:12px;color:#5b6470;font-size:11px;z-index:10;text-align:right}
  #brand{position:fixed;left:14px;bottom:12px;color:#3a414c;font-size:10px;z-index:10}
  #info{position:fixed;right:14px;top:12px;z-index:10;background:rgba(14,17,22,.86);border:1px solid #2a313c;border-radius:10px;padding:12px 14px;backdrop-filter:blur(6px);max-width:340px;display:none}
  #info h2{font-size:13px;margin:0 0 4px;color:#e7ecf2;font-weight:600;word-break:break-all}
  #info .meta{color:#7c8693;font-size:11px;margin-bottom:6px}
  #info .neighbors{color:#aeb6bf;font-size:11px;max-height:240px;overflow:auto}
  #info .neighbors b{display:block;color:#9aa4af;margin-bottom:4px;font-size:10px;letter-spacing:.06em}
  #info .neighbors div.nb{padding:2px 0;cursor:pointer;word-break:break-all}
  #info .neighbors div.nb:hover{color:#7fd1ff}
</style></head>
<body>
<div id="hud">
  <h1>🧠 __AGENT__ — 두뇌 그래프 (3D)</h1>
  <div class="stat" id="stat"></div>
  <div id="legend"></div>
</div>
<div id="info"></div>
<div id="hint">드래그=회전 · 휠=줌 · 우클릭드래그=이동<br>노드클릭=포커스 · 범례클릭=카테고리 토글</div>
<div id="brand">Agentis v1.4 · 자체완결 (외부 의존 0)</div>
<div id="graph"></div>
<script>/*=THREE=*/
__THREE_JS__
/*=/THREE=*/</script>
<script>/*=FORCE3D=*/
__FORCE3D__
/*=/FORCE3D=*/</script>
<script>
const DATA = __DATA__;
const CAT = DATA.categories;

const gd = {
  nodes: DATA.nodes.map(n => ({...n})),
  links: DATA.edges.map(e => ({source: e.source, target: e.target}))
};

const elem = document.getElementById('graph');
const Graph = ForceGraph3D()(elem)
  .graphData(gd)
  .backgroundColor('#070a10')
  .nodeLabel(n => `${n.label}\n[${(CAT[n.category]||CAT._other).label}] · deg ${n.deg}`)
  .nodeColor(n => (CAT[n.category]||CAT._other).color)
  .nodeVal(n => Math.max(3, Math.sqrt(n.deg + 1) * 3))
  .nodeOpacity(0.92)
  .linkColor(() => 'rgba(180, 200, 230, 0.18)')
  .linkOpacity(0.55)
  .linkWidth(0.4)
  .linkDirectionalParticles(1)
  .linkDirectionalParticleSpeed(0.0035)
  .linkDirectionalParticleWidth(1.2)
  .linkDirectionalParticleColor(() => '#7fd1ff')
  .showNavInfo(false)
  .onNodeClick(n => focusOn(n))
  .onBackgroundClick(() => clearFocus());

const _dist0 = Math.max(260, Math.sqrt(gd.nodes.length) * 60);
Graph.cameraPosition({ x: 0, y: 0, z: _dist0 });

// idle 자동 공전 (사용자 인터랙션 시 멈춤)
let _autoOrbit = true;
let _theta = 0;
setInterval(() => {
  if (!_autoOrbit || document.hidden) return;
  _theta += 0.0009;
  Graph.cameraPosition({
    x: _dist0 * Math.sin(_theta),
    z: _dist0 * Math.cos(_theta)
  });
}, 50);
elem.addEventListener('mousedown', () => { _autoOrbit = false; });
elem.addEventListener('wheel', () => { _autoOrbit = false; }, { passive: true });

// 포커스 — 카메라 이동 + 정보 패널
const info = document.getElementById('info');
function focusOn(n) {
  _autoOrbit = false;
  const dist = 90;
  const r = 1 + dist / Math.max(1, Math.hypot(n.x||1, n.y||1, n.z||1));
  Graph.cameraPosition({ x: (n.x||1) * r, y: (n.y||1) * r, z: (n.z||1) * r }, n, 1400);
  const neigh = gd.links.filter(l => {
    const sId = (typeof l.source === 'object') ? l.source.id : l.source;
    const tId = (typeof l.target === 'object') ? l.target.id : l.target;
    return sId === n.id || tId === n.id;
  }).map(l => {
    const sId = (typeof l.source === 'object') ? l.source.id : l.source;
    const tId = (typeof l.target === 'object') ? l.target.id : l.target;
    return sId === n.id ? tId : sId;
  });
  info.style.display = 'block';
  info.innerHTML =
    `<h2>${esc(n.label)}</h2>` +
    `<div class="meta">${esc(n.id)} · ${esc((CAT[n.category]||CAT._other).label)} · deg ${n.deg}</div>` +
    `<div class="neighbors">${neigh.length
      ? '<b>이웃 ' + neigh.length + '</b>' + neigh.map(id => `<div class="nb" data-id="${esc(id)}">↳ ${esc(id)}</div>`).join('')
      : '<i style="color:#5b6470">이웃 없음 (고아 노드)</i>'
    }</div>`;
  info.querySelectorAll('.nb').forEach(el => {
    el.addEventListener('click', () => {
      const t = gd.nodes.find(nn => nn.id === el.dataset.id);
      if (t) focusOn(t);
    });
  });
}
function clearFocus() { info.style.display = 'none'; }
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

// 범례 + 카테고리 토글
const used = [...new Set(gd.nodes.map(n => n.category))].sort();
const legend = document.getElementById('legend');
legend.innerHTML = used.map(c => {
  const s = CAT[c] || CAT._other;
  const k = DATA.stats.by_category[c] || 0;
  return `<span data-cat="${esc(c)}"><i style="background:${s.color}"></i>${esc(s.label)} ${k}</span>`;
}).join('');
const visible = new Set(used);
legend.querySelectorAll('span').forEach(sp => sp.addEventListener('click', () => {
  const c = sp.dataset.cat;
  if (visible.has(c)) { visible.delete(c); sp.classList.add('off'); }
  else { visible.add(c); sp.classList.remove('off'); }
  Graph.graphData({
    nodes: gd.nodes.filter(n => visible.has(n.category)),
    links: gd.links.filter(l => {
      const sId = (typeof l.source === 'object') ? l.source.id : l.source;
      const tId = (typeof l.target === 'object') ? l.target.id : l.target;
      const sn = gd.nodes.find(n => n.id === sId);
      const tn = gd.nodes.find(n => n.id === tId);
      return sn && tn && visible.has(sn.category) && visible.has(tn.category);
    })
  });
}));

document.getElementById('stat').textContent =
  `${DATA.stats.nodes} 노드 · ${DATA.stats.edges} 링크 · 고아 ${DATA.stats.orphans}` +
  (DATA.stats.broken_links ? ` · 깨진링크 ${DATA.stats.broken_links}` : '');

/*─────────────────────────────────────────────────────────────────
  v1.4.1 — 캐릭터 빌보드 + 활성 노드 추적
  - agent.md 의 character: 필드 → SVG 데이터 URI 를 DATA.character 로 주입
  - memory/hot.md 의 첫 [[링크]] → DATA.active_node (해당 노드 옆에 떠 있음)
  - 카메라 정면 빌보드 (THREE.Sprite), idle sin-wave bobbing, 활성 노드 부드러운 추적
─────────────────────────────────────────────────────────────────*/
(function setupCharacterBillboard(){
  if (!DATA.character || !DATA.character.uri || typeof THREE === 'undefined') return;
  const scene = Graph.scene && Graph.scene();
  if (!scene) return;

  const tex = new THREE.TextureLoader().load(DATA.character.uri);
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false });
  const sprite = new THREE.Sprite(mat);
  // 빌보드 크기: 노드 평균 크기보다 살짝 큼
  const SPRITE_SIZE = 36;
  sprite.scale.set(SPRITE_SIZE, SPRITE_SIZE, 1);
  sprite.renderOrder = 999;
  scene.add(sprite);

  // 캐릭터 이름 라벨 (HUD)
  const charLabel = document.createElement('div');
  charLabel.style.cssText = 'position:fixed;left:14px;top:170px;z-index:10;background:rgba(14,17,22,.78);border:1px solid #2a313c;border-radius:8px;padding:6px 10px;font-size:11px;color:#cdd3da;backdrop-filter:blur(6px)';
  charLabel.textContent = '🎭 ' + DATA.character.name + ' · 활성 노드 추적 중';
  document.body.appendChild(charLabel);

  // 활성 노드 찾기
  function findActive() {
    if (!DATA.active_node) return null;
    return gd.nodes.find(n => n.id === DATA.active_node) || null;
  }

  // 그래프 엔진 tick 마다 빌보드 위치 갱신
  let t0 = performance.now();
  Graph.onEngineTick(() => {
    const now = performance.now();
    const dt = (now - t0) / 1000;
    const bob = Math.sin(dt * Math.PI) * 8; // 2초 주기, ±8px 위아래
    const active = findActive();
    let tx, ty, tz;
    if (active && typeof active.x === 'number') {
      // 활성 노드 옆(오른쪽 위) + bob
      tx = active.x + 28;
      ty = (active.y || 0) + 28 + bob;
      tz = active.z || 0;
    } else {
      // 활성 노드 없으면 그래프 중심 위에 떠 있음
      tx = 0;
      ty = 60 + bob;
      tz = 0;
    }
    // 부드러운 lerp 추적
    sprite.position.x += (tx - sprite.position.x) * 0.12;
    sprite.position.y += (ty - sprite.position.y) * 0.12;
    sprite.position.z += (tz - sprite.position.z) * 0.12;
  });

  // 활성 노드가 있으면 시작 시 잠깐 거기로 카메라 끌어가기 (선택)
  setTimeout(() => {
    const a = findActive();
    if (a) {
      charLabel.textContent = '🎭 ' + DATA.character.name + ' · 옆에 있음: ' + a.id;
    } else {
      charLabel.textContent = '🎭 ' + DATA.character.name + ' (활성 노드 없음 — hot.md 첫 [[링크]] 비어있음)';
    }
  }, 1200);
})();
</script>
</body></html>
"""


def load_vendor(vendor_dir: Path) -> tuple[str, str]:
    three_p = vendor_dir / "three.min.js"
    f3d_p = vendor_dir / "3d-force-graph.min.js"
    if not three_p.is_file() or not f3d_p.is_file():
        raise SystemExit(
            f"[build_graph] vendor 파일을 찾을 수 없음: {vendor_dir}\n"
            f"  필요: three.min.js + 3d-force-graph.min.js\n"
            f"  키트에서 받기: https://github.com/imejaim/agentis/tree/main/kit/agentis-template/graph/vendor"
        )
    three_js = three_p.read_text(encoding="utf-8")
    f3d_js = f3d_p.read_text(encoding="utf-8")
    # 토큰 충돌 검사 (인라인 안전성)
    for token in ("__THREE_JS__", "__FORCE3D__", "__DATA__"):
        if token in three_js or token in f3d_js:
            raise SystemExit(f"[build_graph] vendor 안에 인라인 토큰 충돌: {token}")
    # </script> 가 vendor 안에 있는지도 확인 (보통 없음)
    if "</script>" in three_js or "</script>" in f3d_js:
        raise SystemExit("[build_graph] vendor 안에 </script> 가 있어서 인라인 위험. 수동 escape 필요.")
    return three_js, f3d_js


def write_outputs(graph: dict, out_dir: Path, vendor_dir: Path, agent_name: str):
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON 파일에는 내부 인덱스 캐시(_by_*) 와 큰 character data URI 는 빼고 저장
    graph_json_payload = {k: v for k, v in graph.items() if not k.startswith("_")}
    # character 는 JSON 에도 이름만 남기고 data URI 는 제거 (파일 비대화 방지)
    if "character" in graph_json_payload and isinstance(graph_json_payload["character"], dict):
        graph_json_payload["character"] = {
            "name": graph_json_payload["character"].get("name"),
            "applied": bool(graph_json_payload["character"].get("uri")),
        }
    json_path = out_dir / "graph.json"
    json_path.write_text(json.dumps(graph_json_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    three_js, f3d_js = load_vendor(vendor_dir)

    # HTML 에 넣을 데이터: 내부 인덱스 캐시 제외, character data URI 는 포함
    graph_for_html = {k: v for k, v in graph.items() if not k.startswith("_")}
    data_json = json.dumps(graph_for_html, ensure_ascii=False)
    safe_title = (agent_name + " — 두뇌 그래프 (Agentis)").replace("<", "&lt;").replace(">", "&gt;")
    safe_agent = agent_name.replace("<", "&lt;").replace(">", "&gt;")

    html = HTML_TEMPLATE
    html = html.replace("__TITLE__", safe_title)
    html = html.replace("__AGENT__", safe_agent)
    html = html.replace("__DATA__", data_json)
    html = html.replace("__THREE_JS__", three_js, 1)
    html = html.replace("__FORCE3D__", f3d_js, 1)

    html_path = out_dir / "graph.html"
    html_path.write_text(html, encoding="utf-8")
    return json_path, html_path


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent          # .../agentis/graph
    ap = argparse.ArgumentParser(description="agentis/ 두뇌를 3D 그래프로 빌드")
    ap.add_argument("--root", type=Path, default=here.parent, help="agentis 디렉토리 (기본: 스크립트 기준 ../)")
    ap.add_argument("--out", type=Path, default=here, help="출력 디렉토리 (기본: 스크립트 폴더)")
    ap.add_argument("--vendor", type=Path, default=here / "vendor", help="vendor 폴더 (기본: 스크립트 옆 vendor/)")
    ap.add_argument("--open", action="store_true", help="만든 뒤 graph.html 을 브라우저로 연다")
    args = ap.parse_args(argv)

    root = find_root(args.root)
    if not ((root / "agent.md").exists() or (root / "memory").is_dir()):
        print(f"[build_graph] agentis 루트를 찾을 수 없음 (agent.md 나 memory/ 가 있어야 함): {root}", file=sys.stderr)
        return 2

    graph = build(root)
    agent_name = extract_agent_name(root)

    # v1.4.1 — 캐릭터 빌보드 + 활성 노드
    char_choice = parse_character_choice(root)
    char_loaded = load_character_data_uri(args.vendor.resolve(), char_choice)
    if char_loaded:
        uri, name = char_loaded
        graph["character"] = {"name": name, "uri": uri}
    else:
        graph["character"] = {"name": char_choice, "uri": None}
    active = parse_active_node(root, graph["_by_slug"], graph["_by_basename"])
    graph["active_node"] = active

    json_path, html_path = write_outputs(graph, args.out.resolve(), args.vendor.resolve(), agent_name)
    s = graph["stats"]
    print(f"[build_graph] root={root}")
    print(f"[build_graph] {s['nodes']} 노드 / {s['edges']} 링크 / 고아 {s['orphans']} / 깨진링크 {s['broken_links']}")
    print(f"[build_graph] 카테고리: " + ", ".join(f"{k} {v}" for k, v in s["by_category"].items()))
    char_status = "적용됨" if (char_loaded is not None) else "SVG 못 찾음 — 빌보드 생략"
    print(f"[build_graph] 캐릭터: {char_choice} ({char_status})  · 활성노드: {active or '(없음 — hot.md 비어있음)'}")
    print(f"[build_graph] -> {json_path}")
    print(f"[build_graph] -> {html_path}  ({html_path.stat().st_size // 1024} KB, 3D · 외부 의존 0)")
    if graph["broken"]:
        print("[build_graph] 깨진 [[링크]] (대상 페이지 없음 — 오타이거나 아직 안 만든 페이지):")
        for src, tgt in graph["broken"][:20]:
            print(f"   {src}  ->  [[{tgt}]]")
    if args.open:
        webbrowser.open(html_path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
