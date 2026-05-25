#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.5 / build_flow
"""
build_flow.py — 에이전트의 *업무 흐름*(agentis/memory/log.md 의 작업 연대기)을
                n8n / make / flowith 스타일의 다이어그램 HTML 로 만든다.

훑는 대상:  agentis/memory/log.md
            형식 (한 줄 헤더):  ## [YYYY-MM-DD] <type> | <제목>
            그 아래 자유 본문 (다음 `## [` 이전까지) — 산출물/스킬 메타 자동 추출:
              - `[[skills/<name>]]`   → 같은 스킬 사용 = 점선 그룹 엣지
              - `tokens: N`           → 노드 상세
              - `sec: T`              → 노드 상세
              - 첫 줄 한 줄 요약       → 노드 상세

출력:       agentis/graph/flow.html  (자체완결: SVG + 인라인 JS, 외부 의존 0)

엣지:
  - 시간순(이전 → 다음) 실선 + 화살표  (`time` 클래스, 옅은 파랑)
  - 같은 skill 을 쓴 항목끼리 점선  (`skill-group` 클래스, 노랑)

인터랙션:
  - 휠 줌 / 드래그 팬 / 클릭 = 상세 패널
  - 좌→우 (가로 시간축) ↔ 위→아래 (세로) 토글 버튼

폴백:
  log.md 가 없거나 항목이 0 개 → "아직 작업 기록이 없어요. 첫 업무를 시작해 보세요." 빈 화면.

표준 라이브러리만 (re, html, json, pathlib, argparse, sys, webbrowser). 외부 패키지 / 외부 CDN 없음.

사용법:
    python build_flow.py                  # 스크립트 위치 기준 ../ (= agentis/) 를 훑고 ./ 에 출력
    python build_flow.py --root PATH      # agentis 디렉토리 지정
    python build_flow.py --out PATH       # 출력 디렉토리 지정
    python build_flow.py --open           # 만든 뒤 flow.html 을 브라우저로 연다
"""
from __future__ import annotations

import argparse
import html as _html
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

# ── 파싱 정규식 ─────────────────────────────────────────────────────────
LOG_HEADER_RE = re.compile(
    r"^##\s*\[(\d{4}-\d{2}-\d{2})\]\s*(\w+)\s*\|\s*(.+?)\s*$",
    re.MULTILINE,
)
SKILL_LINK_RE = re.compile(r"\[\[skills/([^\[\]|/]+?)(?:\|[^\[\]]*)?\]\]")
TOKENS_RE = re.compile(r"tokens?\s*[:=]\s*([\d,]+)", re.IGNORECASE)
SECONDS_RE = re.compile(r"\b(?:sec|seconds?|초)\s*[:=]\s*([\d.]+)", re.IGNORECASE)
ANY_WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|[^\[\]]*)?\]\]")

# type → (표시명, 색)
TYPE_STYLE = {
    "setup":  ("부팅",  "#7fd1ff"),
    "task":   ("작업",  "#f0b860"),
    "ingest": ("수집",  "#5fcaa0"),
    "skill":  ("스킬",  "#ff8a8a"),
    "lint":   ("정비",  "#c0c0c0"),
    "note":   ("메모",  "#9b8cff"),
    "seed":   ("씨드",  "#e7ecf2"),
    "_other": ("기타",  "#888888"),
}


# ── 루트 / 추출 ─────────────────────────────────────────────────────────
def find_root(start: Path) -> Path:
    p = start.resolve()
    if p.is_file():
        p = p.parent
    for cand in [p, *p.parents]:
        if (cand / "agent.md").exists() or (cand / "memory").is_dir():
            return cand
    return p


def extract_agent_name(root: Path) -> str:
    f = root / "agent.md"
    if not f.is_file():
        return "Agentis"
    txt = f.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^#\s+(.+?)\s*$", txt, re.MULTILINE)
    return (m.group(1).strip() if m else "Agentis") or "Agentis"


def parse_log(log_text: str) -> list[dict]:
    """log.md 의 `## [날짜] type | 제목` 헤더들을 추출.
    각 항목의 본문(다음 헤더 직전까지)에서 skills, tokens, sec, 산출물 라인 추출.
    오래된 것 → 최신 순서를 유지하기 위해 마지막에 역순 정렬은 호출자가 하지 않음;
    여기서는 *log.md 등장 순서대로* 반환 (최신이 위 = 보통).
    """
    headers = list(LOG_HEADER_RE.finditer(log_text))
    entries: list[dict] = []
    for i, m in enumerate(headers):
        date = m.group(1)
        typ_raw = m.group(2).lower()
        typ = typ_raw if typ_raw in TYPE_STYLE else "_other"
        title = m.group(3).strip()
        body_start = m.end()
        body_end = headers[i + 1].start() if (i + 1) < len(headers) else len(log_text)
        body = log_text[body_start:body_end].strip()

        # skills
        skills = sorted({s.lower() for s in SKILL_LINK_RE.findall(body)})

        # 토큰/시간
        toks = sum(int(x.replace(",", "")) for x in TOKENS_RE.findall(body))
        secs = 0.0
        for s in SECONDS_RE.findall(body):
            try:
                secs += float(s)
            except Exception:
                pass

        # 산출물 / 관련 페이지: 본문의 [[..]] 링크들 (skills 제외)
        related = []
        seen_r: set[str] = set()
        for w in ANY_WIKILINK_RE.findall(body):
            w = w.strip()
            if not w or w.lower().startswith("skills/"):
                continue
            if w in seen_r:
                continue
            seen_r.add(w)
            related.append(w)

        # 본문 첫 줄 (요약)
        first_line = ""
        for line in body.splitlines():
            line = line.strip().lstrip("-*").strip()
            if line:
                first_line = line
                break

        entries.append({
            "id": f"e{i:03d}",
            "date": date,
            "type": typ,
            "type_raw": typ_raw,
            "title": title,
            "summary": first_line,
            "skills": skills,
            "tokens": toks,
            "seconds": round(secs, 2),
            "related": related[:8],
            "body_preview": body[:600],
        })
    return entries


# ── 결정론적 노드 → 좌표 매핑 ───────────────────────────────────────────
# 시간축 = 로그 등장 순서를 *역순으로 사용*. log.md 는 최신이 위라서, 다이어그램에서
# 왼쪽(=첫 작업) → 오른쪽(=최신 작업) 으로 보이게 하려면 등장 순서를 뒤집어야 함.
# 여기서는 build 시점에 entries 를 그대로 두고, 별도 `order` 인덱스(과거→현재)를 부여.
def assign_order(entries: list[dict]) -> list[dict]:
    """entries 의 등장 순서가 [최신, ..., 과거] 라고 가정.
    `order` 필드(0=가장 과거 → N-1=최신)와 `lane` 필드(겹침 방지용 채널 0/1/2)를 부여."""
    n = len(entries)
    out = []
    for i, e in enumerate(entries):
        order = n - 1 - i  # 등장 순서 역순 = 시간 순방향
        e2 = dict(e)
        e2["order"] = order
        e2["lane"] = order % 3  # 3 채널로 살짝 지그재그 (가독성)
        out.append(e2)
    # order 순서로 정렬해서 반환 (옛 → 새)
    out.sort(key=lambda x: x["order"])
    return out


def build(root: Path) -> dict:
    log_path = root / "memory" / "log.md"
    agent_name = extract_agent_name(root)
    if not log_path.is_file():
        return {"agent": agent_name, "entries": [], "edges_time": [], "edges_skill": [],
                "by_type": {}, "skills_used": [], "empty_reason": "log.md 가 아직 없음"}

    text = log_path.read_text(encoding="utf-8", errors="replace")
    raw = parse_log(text)
    if not raw:
        return {"agent": agent_name, "entries": [], "edges_time": [], "edges_skill": [],
                "by_type": {}, "skills_used": [], "empty_reason": "log.md 에 항목이 없음"}

    entries = assign_order(raw)

    # 시간순 엣지
    edges_time = []
    for i in range(len(entries) - 1):
        edges_time.append({"source": entries[i]["id"], "target": entries[i + 1]["id"]})

    # 스킬 그룹 엣지 (같은 skill 을 쓴 항목끼리 모든 쌍 — 단, 인접 쌍만 두면 너무 적고 모든 쌍이면 너무 많아짐)
    # 절충: 같은 skill 의 *연속 사용* 만 (시간순으로 인접한 동일 스킬 사용 쌍).
    edges_skill = []
    skill_to_entries: dict[str, list[dict]] = {}
    for e in entries:
        for s in e["skills"]:
            skill_to_entries.setdefault(s, []).append(e)
    skills_used = sorted(skill_to_entries.keys())
    for s, es in skill_to_entries.items():
        es_sorted = sorted(es, key=lambda x: x["order"])
        for i in range(len(es_sorted) - 1):
            edges_skill.append({"source": es_sorted[i]["id"], "target": es_sorted[i + 1]["id"], "skill": s})

    # 통계
    by_type: dict[str, int] = {}
    for e in entries:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1

    return {
        "agent": agent_name,
        "entries": entries,
        "edges_time": edges_time,
        "edges_skill": edges_skill,
        "by_type": by_type,
        "skills_used": skills_used,
        "empty_reason": None,
        "types": {k: {"label": v[0], "color": v[1]} for k, v in TYPE_STYLE.items()},
    }


# ── HTML ──────────────────────────────────────────────────────────────
EMPTY_HTML = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  html,body{margin:0;height:100%;background:#070a10;color:#cdd3da;font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center}
  h1{font-size:18px;color:#e7ecf2;margin:0 0 8px}
  p{color:#7c8693;margin:4px 0;max-width:520px;padding:0 20px}
  .em{color:#f0b860}
  .brand{position:fixed;left:14px;bottom:12px;color:#3a414c;font-size:10px}
</style></head>
<body>
<h1>📋 __AGENT__ — 업무 흐름 다이어그램</h1>
<p>아직 작업 기록이 없어요. 첫 업무를 시작해 보세요.</p>
<p class="em">tip: 작업을 마칠 때마다 <code>agentis/memory/log.md</code> 맨 위에<br>
<code>## [YYYY-MM-DD] task | 제목</code> 형식으로 한 줄씩 쌓이면<br>
이 다이어그램이 자동으로 채워집니다.</p>
<div class="brand">Agentis v1.5 · build_flow.py · 자체완결 (외부 의존 0)</div>
</body></html>
"""

# 본 다이어그램은 인라인 SVG + 인라인 JS. 외부 라이브러리 없음.
MAIN_HTML = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  html,body{margin:0;height:100%;background:#070a10;color:#cdd3da;font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;overflow:hidden}
  #wrap{position:fixed;inset:0}
  svg{width:100%;height:100%;display:block;background:#070a10;cursor:grab}
  svg.dragging{cursor:grabbing}
  #hud{position:fixed;left:14px;top:12px;z-index:10;background:rgba(14,17,22,.82);border:1px solid #2a313c;border-radius:10px;padding:12px 14px;backdrop-filter:blur(6px);max-width:320px}
  #hud h1{font-size:13px;margin:0 0 6px;color:#e7ecf2;letter-spacing:.04em;font-weight:600}
  #hud .stat{color:#8b95a1;font-size:11px;margin-bottom:6px}
  #legend{display:flex;flex-wrap:wrap;gap:6px 10px;margin-top:6px}
  #legend span{display:inline-flex;align-items:center;gap:5px;font-size:11px;color:#9aa4af}
  #legend i{width:9px;height:9px;border-radius:50%;display:inline-block}
  #toggles{margin-top:10px;display:flex;flex-direction:column;gap:5px}
  #toggles button{background:#1a2029;border:1px solid #2a313c;color:#cdd3da;padding:5px 9px;border-radius:6px;font-size:11px;cursor:pointer;font-family:inherit}
  #toggles button:hover{background:#222a35;border-color:#3a414c}
  #toggles button.active{background:#1f2d3a;border-color:#7fd1ff;color:#7fd1ff}
  #hint{position:fixed;right:14px;bottom:12px;color:#5b6470;font-size:11px;z-index:10;text-align:right}
  #brand{position:fixed;left:14px;bottom:12px;color:#3a414c;font-size:10px;z-index:10}
  #info{position:fixed;right:14px;top:12px;z-index:10;background:rgba(14,17,22,.92);border:1px solid #2a313c;border-radius:10px;padding:14px 16px;backdrop-filter:blur(6px);max-width:380px;display:none;max-height:80vh;overflow:auto}
  #info h2{font-size:14px;margin:0 0 4px;color:#e7ecf2;font-weight:600;word-break:break-all}
  #info .meta{color:#7c8693;font-size:11px;margin-bottom:8px}
  #info .row{margin:6px 0;font-size:12px;color:#aeb6bf}
  #info .row b{color:#9aa4af;font-size:10px;letter-spacing:.06em;display:block;margin-bottom:2px}
  #info code{background:#1a2029;padding:1px 5px;border-radius:3px;font-size:11px;color:#f0b860}
  .node-rect{stroke:#1a2029;stroke-width:1.5;cursor:pointer;transition:stroke .15s}
  .node-rect:hover{stroke:#fff;stroke-width:2}
  .node-rect.sel{stroke:#fff;stroke-width:2.5}
  .node-text{fill:#0a0d12;font-size:11px;font-weight:600;pointer-events:none;font-family:inherit}
  .node-date{fill:#0a0d12;font-size:9px;opacity:.7;pointer-events:none;font-family:inherit}
  .edge-time{stroke:#7fd1ff;stroke-width:1.4;fill:none;opacity:.55}
  .edge-skill{stroke:#f0b860;stroke-width:1.0;stroke-dasharray:4 4;fill:none;opacity:.4}
</style></head>
<body>
<div id="wrap">
<div id="hud">
  <h1>📋 __AGENT__ — 업무 흐름</h1>
  <div class="stat" id="stat"></div>
  <div id="legend"></div>
  <div id="toggles">
    <button id="btn-horiz" class="active">좌 → 우 (시간축 가로)</button>
    <button id="btn-vert">위 → 아래 (시간축 세로)</button>
  </div>
</div>
<div id="info"></div>
<div id="hint">드래그 = 이동 · 휠 = 줌 · 노드 = 상세</div>
<div id="brand">Agentis v1.5 · build_flow.py · 자체완결 (외부 의존 0)</div>
<svg id="svg" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arrow-time" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#7fd1ff" opacity="0.7"/>
    </marker>
  </defs>
  <g id="viewport">
    <g id="edges"></g>
    <g id="nodes"></g>
  </g>
</svg>
</div>
<script>
const DATA = __DATA__;
const TYPES = DATA.types;

// ── 레이아웃 ────────────────────────────────────────────────────────
const NODE_W = 200, NODE_H = 56, GAP_X = 90, GAP_Y = 96;
let orientation = 'horiz';  // 'horiz' | 'vert'

function laidOut() {
  const n = DATA.entries.length;
  return DATA.entries.map((e, i) => {
    const ord = e.order;  // 0 = 가장 옛, n-1 = 가장 최신
    const laneOffset = (e.lane - 1) * (NODE_H + 22);
    if (orientation === 'horiz') {
      return Object.assign({}, e, {
        x: 60 + ord * (NODE_W + GAP_X),
        y: 220 + laneOffset
      });
    } else {
      return Object.assign({}, e, {
        x: 200 + (e.lane - 1) * (NODE_W + 30),
        y: 60 + ord * (NODE_H + GAP_Y)
      });
    }
  });
}

function render() {
  const positioned = laidOut();
  const byId = Object.fromEntries(positioned.map(p => [p.id, p]));

  const edgesG = document.getElementById('edges');
  const nodesG = document.getElementById('nodes');
  edgesG.innerHTML = '';
  nodesG.innerHTML = '';

  // 엣지 — 스킬 (밑에 깔리도록 먼저)
  DATA.edges_skill.forEach(ed => {
    const s = byId[ed.source], t = byId[ed.target];
    if (!s || !t) return;
    const path = pathBetween(s, t, true);
    const el = svgEl('path', { d: path, class: 'edge-skill' });
    el.setAttribute('data-skill', ed.skill);
    edgesG.appendChild(el);
  });

  // 엣지 — 시간
  DATA.edges_time.forEach(ed => {
    const s = byId[ed.source], t = byId[ed.target];
    if (!s || !t) return;
    const path = pathBetween(s, t, false);
    const el = svgEl('path', { d: path, class: 'edge-time', 'marker-end': 'url(#arrow-time)' });
    edgesG.appendChild(el);
  });

  // 노드
  positioned.forEach(p => {
    const g = svgEl('g', { transform: `translate(${p.x},${p.y})`, 'data-id': p.id });
    const ty = TYPES[p.type] || TYPES._other;
    const rect = svgEl('rect', {
      class: 'node-rect', width: NODE_W, height: NODE_H, rx: 8, ry: 8,
      fill: ty.color
    });
    g.appendChild(rect);

    const title = svgEl('text', { class: 'node-text', x: 10, y: 22 });
    title.textContent = truncate(p.title, 26);
    g.appendChild(title);

    const sub = svgEl('text', { class: 'node-date', x: 10, y: 40 });
    sub.textContent = `[${p.date}] ${ty.label}` + (p.skills.length ? ` · 🔧${p.skills.length}` : '');
    g.appendChild(sub);

    g.addEventListener('click', (ev) => {
      ev.stopPropagation();
      showDetail(p);
      document.querySelectorAll('.node-rect.sel').forEach(n => n.classList.remove('sel'));
      rect.classList.add('sel');
    });
    nodesG.appendChild(g);
  });

  fitView(positioned);
}

function pathBetween(s, t, curved) {
  const sx = s.x + NODE_W, sy = s.y + NODE_H / 2;
  const tx = t.x, ty = t.y + NODE_H / 2;
  // 세로 모드면 출발/도착 점을 위/아래로
  let ax, ay, bx, by;
  if (orientation === 'horiz') {
    ax = sx; ay = sy; bx = tx; by = ty;
    const mx = (ax + bx) / 2;
    return `M ${ax} ${ay} C ${mx} ${ay}, ${mx} ${by}, ${bx} ${by}`;
  } else {
    ax = s.x + NODE_W / 2; ay = s.y + NODE_H;
    bx = t.x + NODE_W / 2; by = t.y;
    const my = (ay + by) / 2;
    return `M ${ax} ${ay} C ${ax} ${my}, ${bx} ${my}, ${bx} ${by}`;
  }
}

function svgEl(name, attrs) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', name);
  if (attrs) for (const k in attrs) el.setAttribute(k, attrs[k]);
  return el;
}

function truncate(s, n) {
  s = String(s || '');
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}

// ── 상세 패널 ──────────────────────────────────────────────────────
const info = document.getElementById('info');
function showDetail(p) {
  const ty = TYPES[p.type] || TYPES._other;
  const skills = p.skills.length ? p.skills.map(s => `<code>skills/${esc(s)}</code>`).join(' ') : '<i style="color:#5b6470">없음</i>';
  const related = p.related.length ? p.related.map(r => `<code>${esc(r)}</code>`).join(' ') : '<i style="color:#5b6470">없음</i>';
  const tokens = p.tokens ? p.tokens.toLocaleString() + ' tok' : '미기록';
  const secs = p.seconds ? p.seconds + ' s' : '미기록';
  info.style.display = 'block';
  info.innerHTML =
    `<h2>${esc(p.title)}</h2>` +
    `<div class="meta">[${esc(p.date)}] · ${esc(ty.label)} (${esc(p.type_raw)}) · #${p.order + 1}</div>` +
    `<div class="row"><b>요약</b>${esc(p.summary || '(본문 첫 줄 없음)')}</div>` +
    `<div class="row"><b>사용 스킬</b>${skills}</div>` +
    `<div class="row"><b>관련 페이지</b>${related}</div>` +
    `<div class="row"><b>토큰 · 시간</b>${tokens} · ${secs}</div>`;
}
document.getElementById('svg').addEventListener('click', () => {
  info.style.display = 'none';
  document.querySelectorAll('.node-rect.sel').forEach(n => n.classList.remove('sel'));
});

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ── 줌 · 팬 ────────────────────────────────────────────────────────
const svg = document.getElementById('svg');
const viewport = document.getElementById('viewport');
let vx = 0, vy = 0, vz = 1;
function applyView() {
  viewport.setAttribute('transform', `translate(${vx},${vy}) scale(${vz})`);
}
function fitView(positioned) {
  if (!positioned.length) return;
  const xs = positioned.map(p => p.x);
  const ys = positioned.map(p => p.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs) + NODE_W;
  const minY = Math.min(...ys), maxY = Math.max(...ys) + NODE_H;
  const w = svg.clientWidth || window.innerWidth;
  const h = svg.clientHeight || window.innerHeight;
  const pad = 80;
  vz = Math.min((w - pad * 2) / Math.max(1, maxX - minX), (h - pad * 2) / Math.max(1, maxY - minY), 1.2);
  vx = pad - minX * vz + (w - pad * 2 - (maxX - minX) * vz) / 2;
  vy = pad - minY * vz + (h - pad * 2 - (maxY - minY) * vz) / 2;
  applyView();
}
svg.addEventListener('wheel', (e) => {
  e.preventDefault();
  const k = e.deltaY < 0 ? 1.12 : 1 / 1.12;
  const rect = svg.getBoundingClientRect();
  const mx = e.clientX - rect.left, my = e.clientY - rect.top;
  vx = mx - (mx - vx) * k;
  vy = my - (my - vy) * k;
  vz *= k;
  vz = Math.max(0.15, Math.min(vz, 4));
  applyView();
}, { passive: false });

let dragging = false, lx = 0, ly = 0;
svg.addEventListener('mousedown', (e) => {
  dragging = true; lx = e.clientX; ly = e.clientY; svg.classList.add('dragging');
});
window.addEventListener('mousemove', (e) => {
  if (!dragging) return;
  vx += (e.clientX - lx); vy += (e.clientY - ly);
  lx = e.clientX; ly = e.clientY;
  applyView();
});
window.addEventListener('mouseup', () => { dragging = false; svg.classList.remove('dragging'); });

// ── 토글 ───────────────────────────────────────────────────────────
document.getElementById('btn-horiz').addEventListener('click', () => {
  orientation = 'horiz';
  document.getElementById('btn-horiz').classList.add('active');
  document.getElementById('btn-vert').classList.remove('active');
  render();
});
document.getElementById('btn-vert').addEventListener('click', () => {
  orientation = 'vert';
  document.getElementById('btn-vert').classList.add('active');
  document.getElementById('btn-horiz').classList.remove('active');
  render();
});

// ── HUD 채우기 ─────────────────────────────────────────────────────
document.getElementById('stat').textContent =
  `${DATA.entries.length} 작업 · 시간엣지 ${DATA.edges_time.length} · 스킬그룹엣지 ${DATA.edges_skill.length} · 스킬 ${DATA.skills_used.length}종`;

const legend = document.getElementById('legend');
const usedTypes = [...new Set(DATA.entries.map(e => e.type))];
usedTypes.sort();
legend.innerHTML = usedTypes.map(t => {
  const s = TYPES[t] || TYPES._other;
  const k = DATA.by_type[t] || 0;
  return `<span><i style="background:${s.color}"></i>${esc(s.label)} ${k}</span>`;
}).join('');

render();
window.addEventListener('resize', () => fitView(laidOut()));
</script>
</body></html>
"""


def write_outputs(graph: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    title = f"{graph['agent']} — 업무 흐름 (Agentis)"
    safe_title = _html.escape(title)
    safe_agent = _html.escape(graph["agent"])

    if not graph["entries"]:
        html = EMPTY_HTML.replace("__TITLE__", safe_title).replace("__AGENT__", safe_agent)
    else:
        # JSON 페이로드에 들어가지 않아도 되는 필드(body_preview)는 자르고, 나머지는 그대로
        payload = {
            "agent": graph["agent"],
            "entries": [{k: v for k, v in e.items() if k != "body_preview"} for e in graph["entries"]],
            "edges_time": graph["edges_time"],
            "edges_skill": graph["edges_skill"],
            "by_type": graph["by_type"],
            "skills_used": graph["skills_used"],
            "types": graph["types"],
        }
        data_json = json.dumps(payload, ensure_ascii=False)
        html = MAIN_HTML
        html = html.replace("__TITLE__", safe_title)
        html = html.replace("__AGENT__", safe_agent)
        html = html.replace("__DATA__", data_json)

    html_path = out_dir / "flow.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent  # .../agentis/graph
    ap = argparse.ArgumentParser(description="agentis 의 업무 흐름을 flow.html 로 빌드")
    ap.add_argument("--root", type=Path, default=here.parent, help="agentis 디렉토리 (기본: 스크립트 기준 ../)")
    ap.add_argument("--out", type=Path, default=here, help="출력 디렉토리 (기본: 스크립트 폴더)")
    ap.add_argument("--open", action="store_true", help="만든 뒤 flow.html 을 브라우저로 연다")
    args = ap.parse_args(argv)

    root = find_root(args.root)
    if not ((root / "agent.md").exists() or (root / "memory").is_dir()):
        print(f"[build_flow] agentis 루트를 찾을 수 없음 (agent.md 나 memory/ 가 있어야 함): {root}", file=sys.stderr)
        return 2

    graph = build(root)
    html_path = write_outputs(graph, args.out.resolve())

    n = len(graph["entries"])
    print(f"[build_flow] root={root}")
    if n == 0:
        print(f"[build_flow] {graph.get('empty_reason') or '항목 없음'} — 빈 폴백 HTML 생성")
    else:
        print(f"[build_flow] {n} 작업 / 시간엣지 {len(graph['edges_time'])} / 스킬그룹엣지 {len(graph['edges_skill'])} / 스킬 {len(graph['skills_used'])}종")
        print(f"[build_flow] type 분포: " + ", ".join(f"{k} {v}" for k, v in sorted(graph["by_type"].items())))
    print(f"[build_flow] -> {html_path}  ({html_path.stat().st_size // 1024} KB, 자체완결 외부 의존 0)")

    if args.open:
        webbrowser.open(html_path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
