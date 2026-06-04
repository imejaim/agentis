#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.9 / build_flow
"""
build_flow.py — 에이전트의 *주요 업무별 표준 워크플로우*를
                스윔레인(swimlane) 다이어그램 HTML 로 만든다. (v1.9)

v1.9 규칙:
  - flow.html 은 업무 히스토리 타임라인이 아니다.
  - agent.md 의 `primary_tasks:` 3~5개를 파싱해 주요 업무 레인을 만든다.
  - 각 primary task 의 `workflow:` 단계가 노드가 된다. workflow 가 없으면 기본 3단계가 자동 생성된다.
  - log.md 의 `[primary:N]` / `[aux]` 기록은 처리 횟수·최근 처리일·최근 토큰 평균 통계에만 쓴다.
  - 빈 상태 폴백: primary_tasks 미정의 시에만 기존 log.md 시간순 다이어그램으로 후퇴한다.

훑는 대상:
  agent.md   — `primary_tasks:` 블록 (id/name/description/success_metric/workflow)
  log.md     — `## [YYYY-MM-DD] <type> [primary:N | aux] | <제목>` 헤더
                본문에서 tokens: / sec: / [[skills/...]] / [[..]] 자동 추출해 통계화

출력:        agentis/graph/flow.html  (자체완결: SVG + 인라인 JS, 외부 의존 0)

표준 라이브러리만 (re, html, json, pathlib, argparse, sys, webbrowser). 외부 패키지 / 외부 CDN 없음.

사용법:
    python build_flow.py                  # 스크립트 위치 기준 ../ (= agentis/) 를 훑고 ./ 에 출력
    python build_flow.py --root PATH      # agentis 디렉토리 지정
    python build_flow.py --out PATH       # 출력 디렉토리 지정
    python build_flow.py --open           # 만든 뒤 flow.html 을 브라우저로 연다
"""
from __future__ import annotations

import argparse
import datetime as _dt
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
# 헤더: `## [YYYY-MM-DD] <type> [primary:N | aux] | <제목>`
# 태그 부분은 선택적. type 다음에 공백 후 [primary:N] 또는 [aux] 가 있을 수도 있고 없을 수도 있다.
LOG_HEADER_RE = re.compile(
    r"^##\s*\[(\d{4}-\d{2}-\d{2})\]\s*(\w+)\s*(?:\[(primary:\d+|aux)\])?\s*\|\s*(.+?)\s*$",
    re.MULTILINE,
)
SKILL_LINK_RE = re.compile(r"\[\[skills/([^\[\]|/]+?)(?:\|[^\[\]]*)?\]\]")
TOKENS_RE = re.compile(r"tokens?\s*[:=]\s*([\d,]+)", re.IGNORECASE)
SECONDS_RE = re.compile(r"\b(?:sec|seconds?|초)\s*[:=]\s*([\d.]+)", re.IGNORECASE)
ANY_WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|[^\[\]]*)?\]\]")

# type → (표시명, 색)  — aux 분류 시 채도 죽임 (JS 측에서)
TYPE_STYLE = {
    "setup":  ("부팅",  "#7fd1ff"),
    "task":   ("작업",  "#f0b860"),
    "ingest": ("수집",  "#5fcaa0"),
    "skill":  ("스킬",  "#ff8a8a"),
    "lint":   ("정비",  "#c0c0c0"),
    "note":   ("메모",  "#9b8cff"),
    "seed":   ("씨드",  "#e7ecf2"),
    "push":   ("푸시",  "#7ad6e8"),
    "_other": ("기타",  "#888888"),
}

# 주요 업무 컬러 팔레트 (1-indexed). aux 는 별도 회색.
PRIMARY_COLORS = {
    1: "#3b82f6",   # 진한 파랑
    2: "#10b981",   # 진한 초록
    3: "#8b5cf6",   # 진한 보라
    4: "#f97316",   # 진한 주황
    5: "#ec4899",   # 진한 분홍
}
AUX_COLOR = "#6b7280"   # 회색 50% 투명은 JS 측 opacity 로


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


def parse_primary_tasks(agent_text: str) -> list[dict]:
    """agent.md 의 `primary_tasks:` YAML 블록을 들여쓰기 기반으로 파싱.

    v1.8+ 권장 구조:
        primary_tasks:
          - id: 1
            name: 고객 문의 처리
            description: 문의 접수부터 답변까지
            success_metric: 답변 누락 0
            workflow:
              - 문의 접수
              - 원인 확인
              - 답변/기록

    `workflow:` 가 없으면 기본 3단계 워크플로우를 자동 부여한다.
    """
    lines = agent_text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if re.match(r"^\s*primary_tasks\s*:\s*$", ln):
            start = i + 1
            break
    if start is None:
        return []

    tasks: list[dict] = []
    cur: dict | None = None
    in_workflow = False
    item_re = re.compile(r"^(\s*)-\s+(.+)$")
    kv_re = re.compile(r"^(\s*)([A-Za-z_][\w-]*)\s*:\s*(.*)$")

    def finish_cur() -> None:
        nonlocal cur, in_workflow
        if cur:
            tasks.append(cur)
        cur = None
        in_workflow = False

    for j in range(start, len(lines)):
        ln = lines[j]
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if re.match(r"^```", ln) or re.match(r"^##\s", ln):
            break

        m_item = item_re.match(ln)
        if m_item:
            indent = len(m_item.group(1).replace("\t", "    "))
            rest = m_item.group(2).strip()
            # primary_tasks 바로 아래의 새 항목. workflow 하위 항목은 보통 4칸 이상 들여쓰기다.
            if indent <= 2 and re.match(r"^[A-Za-z_][\w-]*\s*:", rest):
                finish_cur()
                cur = {"workflow": []}
                in_workflow = False
                mkv = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.+)$", rest)
                if mkv:
                    cur[mkv.group(1).lower()] = mkv.group(2).strip().strip("\"'")
                continue
            if cur is not None and in_workflow:
                cur.setdefault("workflow", []).append(rest.strip().strip("\"'"))
                continue

        m_kv = kv_re.match(ln)
        if m_kv and cur is not None:
            indent = len(m_kv.group(1).replace("\t", "    "))
            k = m_kv.group(2).lower()
            v = m_kv.group(3).strip().strip("\"'")
            if indent == 0 and k != "primary_tasks":
                break
            if k == "workflow":
                cur.setdefault("workflow", [])
                in_workflow = True
            else:
                cur[k] = v
                in_workflow = False
            continue

        if not ln.startswith(" ") and not ln.startswith("\t"):
            break

    finish_cur()

    out = []
    for idx, t in enumerate(tasks, start=1):
        if "name" not in t and "id" not in t:
            continue
        try:
            tid = int(t.get("id", idx))
        except (TypeError, ValueError):
            tid = idx
        name = str(t.get("name", f"primary {tid}")).strip()
        if not name:
            continue
        workflow = [str(x).strip() for x in t.get("workflow", []) if str(x).strip()]
        if not workflow:
            workflow = ["요청/트리거 확인", "처리/검증", "산출물 보고/기억 갱신"]
        out.append({
            "id": tid,
            "name": name,
            "description": str(t.get("description", "")).strip(),
            "success_metric": str(t.get("success_metric", "")).strip(),
            "workflow": workflow,
        })
    out.sort(key=lambda x: x["id"])
    return out

def parse_log(log_text: str) -> list[dict]:
    """log.md 의 `## [날짜] type [primary:N|aux] | 제목` 헤더 추출.
    각 항목 본문에서 skills/tokens/sec/related 추출.
    """
    headers = list(LOG_HEADER_RE.finditer(log_text))
    entries: list[dict] = []
    for i, m in enumerate(headers):
        date = m.group(1)
        typ_raw = m.group(2).lower()
        typ = typ_raw if typ_raw in TYPE_STYLE else "_other"
        tag_raw = (m.group(3) or "").lower()
        title = m.group(4).strip()
        body_start = m.end()
        body_end = headers[i + 1].start() if (i + 1) < len(headers) else len(log_text)
        body = log_text[body_start:body_end].strip()

        # 분류: primary:N 또는 aux. type 이 task 가 아닌 경우 (setup/ingest/skill/lint/note/seed/push) 는 자동 aux.
        primary_id: int | None = None
        classification = "aux"
        if tag_raw.startswith("primary:"):
            try:
                primary_id = int(tag_raw.split(":", 1)[1])
                classification = "primary"
            except (ValueError, IndexError):
                pass
        elif tag_raw == "aux":
            classification = "aux"
        else:
            # 태그 없음: task 면 미분류(aux 취급), 그 외 type 도 aux
            classification = "aux"

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

        # 관련 페이지
        related: list[str] = []
        seen_r: set[str] = set()
        for w in ANY_WIKILINK_RE.findall(body):
            w = w.strip()
            if not w or w.lower().startswith("skills/"):
                continue
            if w in seen_r:
                continue
            seen_r.add(w)
            related.append(w)

        # 첫 줄 요약
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
            "classification": classification,   # 'primary' | 'aux'
            "primary_id": primary_id,           # int | None
        })
    return entries


# ── 결정론적 노드 → 좌표 매핑 ───────────────────────────────────────────
def assign_order(entries: list[dict]) -> list[dict]:
    """entries 는 log.md 등장 순서 = 보통 [최신, ..., 과거]. 시간 순방향 `order` 부여."""
    n = len(entries)
    out = []
    for i, e in enumerate(entries):
        order = n - 1 - i
        e2 = dict(e)
        e2["order"] = order
        out.append(e2)
    out.sort(key=lambda x: x["order"])
    return out


def _avg_recent_tokens(entries: list[dict], primary_id: int, k: int = 5) -> int:
    """해당 primary 의 가장 최근 k 개 항목 평균 토큰. 토큰 0 항목 제외."""
    its = [e for e in entries if e.get("classification") == "primary" and e.get("primary_id") == primary_id and e.get("tokens")]
    its.sort(key=lambda x: x.get("date", ""), reverse=True)
    its = its[:k]
    if not its:
        return 0
    return int(sum(e["tokens"] for e in its) / len(its))


def _last_date(entries: list[dict], primary_id: int) -> str:
    its = [e for e in entries if e.get("classification") == "primary" and e.get("primary_id") == primary_id]
    if not its:
        return ""
    return max(e["date"] for e in its)


def build_workflow_entries(primary_tasks: list[dict]) -> list[dict]:
    """primary_tasks 를 업무 히스토리가 아닌 '주요 업무별 표준 워크플로우' 노드로 변환."""
    entries: list[dict] = []
    order = 0
    for task in primary_tasks:
        pid = int(task["id"])
        steps = task.get("workflow") or ["요청/트리거 확인", "처리/검증", "산출물 보고/기억 갱신"]
        for step_idx, step in enumerate(steps, start=1):
            entries.append({
                "id": f"p{pid}s{step_idx}",
                "date": "workflow",
                "type": "task",
                "type_raw": "workflow",
                "title": f"{task['name']} · {step}",
                "summary": task.get("description") or task.get("success_metric") or "주요 업무 표준 단계",
                "skills": [],
                "tokens": 0,
                "seconds": 0,
                "related": [],
                "body_preview": "",
                "classification": "primary",
                "primary_id": pid,
                "workflow_step": step_idx,
                "order": order,
            })
            order += 1
    return entries


def build(root: Path) -> dict:
    log_path = root / "memory" / "log.md"
    agent_name = extract_agent_name(root)

    # primary_tasks
    primary_tasks: list[dict] = []
    agent_path = root / "agent.md"
    if agent_path.is_file():
        agent_text = agent_path.read_text(encoding="utf-8", errors="replace")
        primary_tasks = parse_primary_tasks(agent_text)

    if log_path.is_file():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        raw = parse_log(text)
        empty_reason = "log.md 에 항목이 없음" if not raw else None
    else:
        raw = []
        empty_reason = "log.md 가 아직 없음"

    # v1.8+: primary_tasks 가 있으면 flow.html 의 본문 노드는 업무 히스토리가 아니라
    # '주요 업무별 표준 워크플로우'다. log.md 는 처리 횟수/최근일/토큰 통계로만 사용한다.
    if primary_tasks:
        entries = build_workflow_entries(primary_tasks)
    else:
        if not raw:
            return {
                "agent": agent_name, "entries": [], "edges_time": [], "edges_skill": [],
                "by_type": {}, "skills_used": [], "primary_tasks": primary_tasks,
                "primary_stats": [], "empty_reason": empty_reason,
                "types": {k: {"label": v[0], "color": v[1]} for k, v in TYPE_STYLE.items()},
                "primary_colors": PRIMARY_COLORS, "aux_color": AUX_COLOR,
                "counts": {"primary": 0, "aux": 0, "total": 0, "primary_30d": 0, "aux_30d": 0},
            }
        entries = assign_order(raw)

    # 엣지: workflow 모드에서는 같은 primary 안의 단계만 연결한다. primary_tasks 가 없을 때만 시간순 히스토리.
    edges_time = []
    if primary_tasks:
        by_primary: dict[int, list[dict]] = {}
        for e in entries:
            by_primary.setdefault(int(e.get("primary_id") or 0), []).append(e)
        for es in by_primary.values():
            es_sorted = sorted(es, key=lambda x: x.get("workflow_step", x.get("order", 0)))
            for i in range(len(es_sorted) - 1):
                edges_time.append({"source": es_sorted[i]["id"], "target": es_sorted[i + 1]["id"]})
    else:
        for i in range(len(entries) - 1):
            edges_time.append({"source": entries[i]["id"], "target": entries[i + 1]["id"]})

    # 스킬 그룹 엣지 (히스토리 모드에서만 의미 있음)
    edges_skill = []
    skill_to_entries: dict[str, list[dict]] = {}
    if not primary_tasks:
        for e in entries:
            for s in e["skills"]:
                skill_to_entries.setdefault(s, []).append(e)
        for s, es in skill_to_entries.items():
            es_sorted = sorted(es, key=lambda x: x["order"])
            for i in range(len(es_sorted) - 1):
                edges_skill.append({"source": es_sorted[i]["id"], "target": es_sorted[i + 1]["id"], "skill": s})
    skills_used = sorted(skill_to_entries.keys())

    by_type: dict[str, int] = {}
    for e in entries:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1

    # 카운트/카드 통계는 log.md 실제 처리 기록 기준. 다이어그램 노드는 표준 workflow 기준.
    stat_entries = raw if primary_tasks else entries
    today = _dt.date.today()
    primary_n = sum(1 for e in stat_entries if e["classification"] == "primary")
    aux_n = len(stat_entries) - primary_n
    primary_30d = 0
    aux_30d = 0
    for e in stat_entries:
        try:
            d = _dt.date.fromisoformat(e["date"])
        except ValueError:
            continue
        if (today - d).days <= 30:
            if e["classification"] == "primary":
                primary_30d += 1
            else:
                aux_30d += 1

    primary_stats = []
    for pt in primary_tasks:
        pid = pt["id"]
        count = sum(1 for e in raw if e.get("primary_id") == pid)
        primary_stats.append({
            "id": pid,
            "name": pt["name"],
            "description": pt.get("description", ""),
            "success_metric": pt.get("success_metric", ""),
            "count": count,
            "last_date": _last_date(raw, pid),
            "avg_tokens": _avg_recent_tokens(raw, pid),
            "color": PRIMARY_COLORS.get(pid, AUX_COLOR),
        })

    return {
        "agent": agent_name,
        "entries": entries,
        "edges_time": edges_time,
        "edges_skill": edges_skill,
        "by_type": by_type,
        "skills_used": skills_used,
        "primary_tasks": primary_tasks,
        "primary_stats": primary_stats,
        "empty_reason": None,
        "types": {k: {"label": v[0], "color": v[1]} for k, v in TYPE_STYLE.items()},
        "primary_colors": PRIMARY_COLORS,
        "aux_color": AUX_COLOR,
        "counts": {
            "primary": primary_n,
            "aux": aux_n,
            "total": len(entries),
            "primary_30d": primary_30d,
            "aux_30d": aux_30d,
        },
    }


# ── HTML ──────────────────────────────────────────────────────────────
EMPTY_HTML = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  html,body{margin:0;height:100%;background:#070a10;color:#cdd3da;font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center}
  h1{font-size:18px;color:#e7ecf2;margin:0 0 8px}
  p{color:#7c8693;margin:4px 0;max-width:560px;padding:0 20px}
  .em{color:#f0b860}
  code{background:#1a2029;color:#f0b860;padding:1px 5px;border-radius:3px;font-size:11px}
  .brand{position:fixed;left:14px;bottom:12px;color:#3a414c;font-size:10px}
</style></head>
<body>
<h1>🎯 __AGENT__ — 업무 흐름 (스윔레인)</h1>
<p>__EMPTY_MSG__</p>
<p class="em">tip: 주요 업무를 먼저 정의하세요 — <code>agentis/agent.md</code> 의<br>
<code>primary_tasks:</code> 블록에 3~5개 항목을 채우면<br>
이 다이어그램이 스윔레인으로 자동 구성됩니다.</p>
<div class="brand">Agentis v1.9 · build_flow.py · 자체완결 (외부 의존 0)</div>
</body></html>
"""

# 본 다이어그램: 인라인 SVG + 인라인 JS. 외부 라이브러리 없음.
MAIN_HTML = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  html,body{margin:0;height:100%;background:#070a10;color:#cdd3da;font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;overflow:hidden}
  #wrap{position:fixed;inset:0}
  svg{width:100%;height:100%;display:block;background:#070a10;cursor:grab}
  svg.dragging{cursor:grabbing}

  /* 상단 헤더 한 줄 */
  #topbar{position:fixed;left:0;right:0;top:0;height:36px;background:rgba(8,11,17,.95);border-bottom:1px solid #1a2029;display:flex;align-items:center;padding:0 16px;z-index:11;font-size:12px;color:#9aa4af;letter-spacing:.01em}
  #topbar b{color:#e7ecf2;font-weight:600}
  #topbar .sep{color:#3a414c;margin:0 10px}

  /* 좌측 대시보드 — 주요 업무 카드 */
  #dash{position:fixed;left:14px;top:50px;z-index:10;display:flex;flex-direction:column;gap:7px;max-width:280px}
  .card{background:rgba(14,17,22,.86);border:1px solid #2a313c;border-left-width:4px;border-radius:8px;padding:9px 11px;backdrop-filter:blur(6px);transition:transform .12s,border-color .12s}
  .card:hover{transform:translateX(2px);border-color:#7fd1ff}
  .card .ttl{font-size:12px;font-weight:600;color:#e7ecf2;line-height:1.3;margin-bottom:3px}
  .card .meta{font-size:10.5px;color:#7c8693;line-height:1.5}
  .card .badge{display:inline-block;font-family:'JetBrains Mono',Consolas,monospace;font-size:9.5px;color:#0a0d12;padding:1px 6px;border-radius:3px;font-weight:600;margin-right:6px}
  .card.aux{border-left-color:__AUX_COLOR__;opacity:.66}
  .card.aux .ttl{color:#9aa4af}

  /* 토글 + 범례 */
  #ctrls{position:fixed;right:14px;top:50px;z-index:10;background:rgba(14,17,22,.82);border:1px solid #2a313c;border-radius:10px;padding:10px 12px;backdrop-filter:blur(6px);max-width:260px}
  #ctrls h2{font-size:11px;margin:0 0 6px;color:#9aa4af;font-weight:600;letter-spacing:.06em;text-transform:uppercase}
  #legend{display:flex;flex-wrap:wrap;gap:5px 9px;margin-bottom:8px}
  #legend span{display:inline-flex;align-items:center;gap:4px;font-size:10.5px;color:#9aa4af}
  #legend i{width:8px;height:8px;border-radius:50%;display:inline-block}
  #toggles{display:flex;flex-direction:column;gap:4px}
  #toggles button{background:#1a2029;border:1px solid #2a313c;color:#cdd3da;padding:4px 8px;border-radius:5px;font-size:11px;cursor:pointer;font-family:inherit;text-align:left}
  #toggles button:hover{background:#222a35;border-color:#3a414c}
  #toggles button.active{background:#1f2d3a;border-color:#7fd1ff;color:#7fd1ff}

  #hint{position:fixed;right:14px;bottom:12px;color:#5b6470;font-size:11px;z-index:10;text-align:right}
  #brand{position:fixed;left:14px;bottom:12px;color:#3a414c;font-size:10px;z-index:10}
  #info{position:fixed;right:14px;top:50px;z-index:12;background:rgba(14,17,22,.96);border:1px solid #2a313c;border-radius:10px;padding:14px 16px;backdrop-filter:blur(6px);max-width:380px;display:none;max-height:75vh;overflow:auto}
  #info h2{font-size:14px;margin:0 0 4px;color:#e7ecf2;font-weight:600;word-break:break-all}
  #info .meta{color:#7c8693;font-size:11px;margin-bottom:8px}
  #info .row{margin:6px 0;font-size:12px;color:#aeb6bf}
  #info .row b{color:#9aa4af;font-size:10px;letter-spacing:.06em;display:block;margin-bottom:2px}
  #info code{background:#1a2029;padding:1px 5px;border-radius:3px;font-size:11px;color:#f0b860}
  #info .closeX{position:absolute;top:6px;right:10px;background:none;border:0;color:#5b6470;font-size:14px;cursor:pointer}

  /* 스윔레인 */
  .lane-band{fill:#0c1018;stroke:#1a2029;stroke-width:1}
  .lane-band.aux{fill:#0a0d12;opacity:.55}
  .lane-label{fill:#9aa4af;font-size:11px;font-weight:600;font-family:inherit}
  .lane-sub{fill:#5b6470;font-size:9.5px;font-family:inherit}
  .lane-divider{stroke:#1a2029;stroke-width:1;stroke-dasharray:3 4}

  /* 노드 */
  .node-rect{stroke:#1a2029;stroke-width:1.5;cursor:pointer;transition:stroke .15s}
  .node-rect:hover{stroke:#fff;stroke-width:2}
  .node-rect.sel{stroke:#fff;stroke-width:2.5}
  .node-rect.aux{opacity:.5}
  .node-text{fill:#0a0d12;font-size:11px;font-weight:600;pointer-events:none;font-family:inherit}
  .node-date{fill:#0a0d12;font-size:9px;opacity:.7;pointer-events:none;font-family:inherit}
  .node-text.aux{fill:#e7ecf2;opacity:.85}
  .node-date.aux{fill:#9aa4af}

  /* 엣지 */
  .edge-time{stroke:#7fd1ff;stroke-width:1.2;fill:none;opacity:.42}
  .edge-skill{stroke:#f0b860;stroke-width:0.9;stroke-dasharray:4 4;fill:none;opacity:.35}
</style></head>
<body>
<div id="topbar"></div>
<div id="wrap">
<div id="dash"></div>
<div id="ctrls">
  <h2>범례</h2>
  <div id="legend"></div>
  <h2>레이아웃</h2>
  <div id="toggles">
    <button id="btn-horiz" class="active">좌 → 우 (시간축 가로 + 스윔레인)</button>
    <button id="btn-vert">위 → 아래 (시간축 세로)</button>
  </div>
</div>
<div id="info"><button class="closeX" id="closeInfo">×</button><div id="infoBody"></div></div>
<div id="hint">드래그 = 이동 · 휠 = 줌 · 노드 = 상세</div>
<div id="brand">Agentis v1.9 · build_flow.py · 자체완결 (외부 의존 0)</div>
<svg id="svg" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <marker id="arrow-time" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#7fd1ff" opacity="0.7"/>
    </marker>
  </defs>
  <g id="viewport">
    <g id="lanes"></g>
    <g id="edges"></g>
    <g id="nodes"></g>
  </g>
</svg>
</div>
<script>
const DATA = __DATA__;
const TYPES = DATA.types;
const PRIMARY_COLORS = DATA.primary_colors || {};
const AUX_COLOR = DATA.aux_color || '#6b7280';
const HAS_PRIMARY = (DATA.primary_tasks && DATA.primary_tasks.length > 0);

// ── 레이아웃 ────────────────────────────────────────────────────────
const NODE_W = 200, NODE_H = 48, GAP_X = 70, GAP_Y = 82;
const LANE_H = 92;       // 스윔레인 한 칸 높이
const LANE_LBL_W = 180;  // 레인 라벨 영역 너비
const TOP_PAD = 20;
let orientation = 'horiz';  // 'horiz' = 스윔레인 가로, 'vert' = 시간축 세로 (단순)

// 레인 정의: HAS_PRIMARY 면 primary N + aux. 아니면 단일 레인.
function buildLanes() {
  const lanes = [];
  if (HAS_PRIMARY) {
    DATA.primary_tasks.forEach((t, idx) => {
      lanes.push({
        kind: 'primary',
        id: t.id,
        name: t.name,
        sub: t.description || '',
        color: PRIMARY_COLORS[t.id] || AUX_COLOR,
        yIndex: idx,
      });
    });
    lanes.push({
      kind: 'aux',
      id: 'aux',
      name: '부수 업무 (aux)',
      sub: '주요 업무 외 모든 작업 (자동/수동 분류)',
      color: AUX_COLOR,
      yIndex: lanes.length,
    });
  } else {
    lanes.push({
      kind: 'all',
      id: 'all',
      name: '전체 작업',
      sub: 'primary_tasks 미정의 — 단순 시간순',
      color: '#7fd1ff',
      yIndex: 0,
    });
  }
  return lanes;
}

function laneFor(entry, lanes) {
  if (!HAS_PRIMARY) return lanes[0];
  if (entry.classification === 'primary' && entry.primary_id != null) {
    const ln = lanes.find(l => l.kind === 'primary' && l.id === entry.primary_id);
    if (ln) return ln;
  }
  return lanes.find(l => l.kind === 'aux') || lanes[lanes.length - 1];
}

function laidOut(lanes) {
  const n = DATA.entries.length;
  return DATA.entries.map((e) => {
    const ord = e.order;
    if (orientation === 'horiz') {
      const lane = laneFor(e, lanes);
      const ly = TOP_PAD + lane.yIndex * LANE_H + (LANE_H - NODE_H) / 2;
      return Object.assign({}, e, {
        x: LANE_LBL_W + 30 + ord * (NODE_W + GAP_X),
        y: ly,
        laneId: lane.id,
        laneKind: lane.kind,
      });
    } else {
      // 세로 모드 — 단순 시간축. lane 무시 (대신 type 별 컬럼)
      return Object.assign({}, e, {
        x: 220 + ((e.order % 3) - 1) * (NODE_W + 30),
        y: 60 + ord * (NODE_H + GAP_Y),
        laneId: 'vert',
        laneKind: e.classification,
      });
    }
  });
}

function render() {
  const lanes = buildLanes();
  const positioned = laidOut(lanes);
  const byId = Object.fromEntries(positioned.map(p => [p.id, p]));

  const lanesG = document.getElementById('lanes');
  const edgesG = document.getElementById('edges');
  const nodesG = document.getElementById('nodes');
  lanesG.innerHTML = '';
  edgesG.innerHTML = '';
  nodesG.innerHTML = '';

  // 스윔레인 밴드 (가로 모드만)
  if (orientation === 'horiz') {
    const lastOrd = Math.max(0, DATA.entries.length - 1);
    const totalW = LANE_LBL_W + 30 + (lastOrd + 1) * (NODE_W + GAP_X) + 100;
    lanes.forEach((ln, i) => {
      const y = TOP_PAD + i * LANE_H;
      const band = svgEl('rect', {
        class: 'lane-band' + (ln.kind === 'aux' ? ' aux' : ''),
        x: 0, y: y, width: totalW, height: LANE_H,
      });
      lanesG.appendChild(band);

      // 왼쪽 컬러 스트라이프
      const stripe = svgEl('rect', {
        x: 0, y: y, width: 4, height: LANE_H, fill: ln.color, opacity: ln.kind === 'aux' ? 0.5 : 0.95,
      });
      lanesG.appendChild(stripe);

      // 라벨
      const lbl = svgEl('text', {
        class: 'lane-label', x: 14, y: y + 22,
      });
      lbl.textContent = ln.kind === 'primary' ? `[primary:${ln.id}] ${ln.name}` : ln.name;
      lanesG.appendChild(lbl);

      const sub = svgEl('text', {
        class: 'lane-sub', x: 14, y: y + 38,
      });
      sub.textContent = truncate(ln.sub, 28);
      lanesG.appendChild(sub);

      // 카운트 배지
      const cnt = DATA.entries.filter(e => {
        const elane = laneFor(e, lanes);
        return elane.id === ln.id && elane.kind === ln.kind;
      }).length;
      const cntT = svgEl('text', {
        class: 'lane-sub', x: 14, y: y + 56,
      });
      cntT.textContent = `처리 ${cnt}건`;
      lanesG.appendChild(cntT);

      // 디바이더 (마지막 제외)
      if (i < lanes.length - 1) {
        const div = svgEl('line', {
          class: 'lane-divider', x1: LANE_LBL_W, y1: y + LANE_H, x2: totalW, y2: y + LANE_H,
        });
        lanesG.appendChild(div);
      }
    });
  }

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
    const isAux = (p.classification === 'aux');
    const fill = (HAS_PRIMARY && p.classification === 'primary' && p.primary_id != null)
      ? (PRIMARY_COLORS[p.primary_id] || AUX_COLOR)
      : (isAux ? AUX_COLOR : (TYPES[p.type] || TYPES._other).color);

    const g = svgEl('g', { transform: `translate(${p.x},${p.y})`, 'data-id': p.id });
    const rect = svgEl('rect', {
      class: 'node-rect' + (isAux ? ' aux' : ''), width: NODE_W, height: NODE_H, rx: 7, ry: 7,
      fill: fill,
    });
    g.appendChild(rect);

    const title = svgEl('text', {
      class: 'node-text' + (isAux ? ' aux' : ''),
      x: 10, y: 19,
    });
    title.textContent = truncate(p.title, 26);
    g.appendChild(title);

    const ty = TYPES[p.type] || TYPES._other;
    const sub = svgEl('text', {
      class: 'node-date' + (isAux ? ' aux' : ''),
      x: 10, y: 35,
    });
    const tag = (p.classification === 'primary' && p.primary_id != null) ? `[p${p.primary_id}]` : '[aux]';
    sub.textContent = `${tag} [${p.date}] ${ty.label}` + (p.skills.length ? ` · 🔧${p.skills.length}` : '');
    g.appendChild(sub);

    g.addEventListener('click', (ev) => {
      ev.stopPropagation();
      showDetail(p);
      document.querySelectorAll('.node-rect.sel').forEach(n => n.classList.remove('sel'));
      rect.classList.add('sel');
    });
    nodesG.appendChild(g);
  });

  fitView(positioned, lanes);
}

function pathBetween(s, t, curved) {
  const sx = s.x + NODE_W, sy = s.y + NODE_H / 2;
  const tx = t.x, ty = t.y + NODE_H / 2;
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
const infoBody = document.getElementById('infoBody');
function showDetail(p) {
  const ty = TYPES[p.type] || TYPES._other;
  const skills = p.skills.length ? p.skills.map(s => `<code>skills/${esc(s)}</code>`).join(' ') : '<i style="color:#5b6470">없음</i>';
  const related = p.related.length ? p.related.map(r => `<code>${esc(r)}</code>`).join(' ') : '<i style="color:#5b6470">없음</i>';
  const tokens = p.tokens ? p.tokens.toLocaleString() + ' tok' : '미기록';
  const secs = p.seconds ? p.seconds + ' s' : '미기록';
  const cls = (p.classification === 'primary' && p.primary_id != null)
    ? `<span style="color:${esc(PRIMARY_COLORS[p.primary_id] || AUX_COLOR)};font-weight:600">[primary:${p.primary_id}]</span>`
    : '<span style="color:#9aa4af">[aux]</span>';
  info.style.display = 'block';
  infoBody.innerHTML =
    `<h2>${esc(p.title)}</h2>` +
    `<div class="meta">${cls} · [${esc(p.date)}] · ${esc(ty.label)} (${esc(p.type_raw)}) · #${p.order + 1}</div>` +
    `<div class="row"><b>요약</b>${esc(p.summary || '(본문 첫 줄 없음)')}</div>` +
    `<div class="row"><b>사용 스킬</b>${skills}</div>` +
    `<div class="row"><b>관련 페이지</b>${related}</div>` +
    `<div class="row"><b>토큰 · 시간</b>${tokens} · ${secs}</div>`;
}
document.getElementById('closeInfo').addEventListener('click', () => {
  info.style.display = 'none';
});
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
function fitView(positioned, lanes) {
  if (!positioned.length) return;
  let minX, minY, maxX, maxY;
  if (orientation === 'horiz' && lanes && lanes.length) {
    minX = 0;
    maxX = LANE_LBL_W + 30 + DATA.entries.length * (NODE_W + GAP_X) + 60;
    minY = 0;
    maxY = TOP_PAD + lanes.length * LANE_H + 20;
  } else {
    const xs = positioned.map(p => p.x);
    const ys = positioned.map(p => p.y);
    minX = Math.min(...xs); maxX = Math.max(...xs) + NODE_W;
    minY = Math.min(...ys); maxY = Math.max(...ys) + NODE_H;
  }
  const w = svg.clientWidth || window.innerWidth;
  const h = svg.clientHeight || window.innerHeight;
  const padL = 320, padR = 290, padT = 70, padB = 50;
  vz = Math.min((w - padL - padR) / Math.max(1, maxX - minX), (h - padT - padB) / Math.max(1, maxY - minY), 1.0);
  if (!isFinite(vz) || vz <= 0) vz = 1;
  vx = padL - minX * vz;
  vy = padT - minY * vz + Math.max(0, (h - padT - padB - (maxY - minY) * vz) / 2);
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

// ── 상단 헤더 한 줄 ────────────────────────────────────────────────
const tbar = document.getElementById('topbar');
const c = DATA.counts;
const pn = (DATA.primary_tasks || []).length;
tbar.innerHTML =
  `<b>🎯 ${esc(DATA.agent)}</b><span class="sep">·</span>` +
  `주요 업무 <b>${pn}</b>개<span class="sep">·</span>` +
  `처리 <b>${c.primary_30d}</b>건 (지난 30일)<span class="sep">·</span>` +
  `부수 업무 <b>${c.aux_30d}</b>건<span class="sep">·</span>` +
  `<span style="color:#5b6470">총 ${c.total}건 (주요 ${c.primary} / 부수 ${c.aux})</span>`;

// ── 좌측 대시보드 카드 ──────────────────────────────────────────────
const dash = document.getElementById('dash');
(DATA.primary_stats || []).forEach(s => {
  const card = document.createElement('div');
  card.className = 'card';
  card.style.borderLeftColor = s.color;
  const avgTok = s.avg_tokens ? `${s.avg_tokens.toLocaleString()} tok` : '—';
  card.innerHTML =
    `<div class="ttl"><span class="badge" style="background:${esc(s.color)}">p${s.id}</span>${esc(s.name)}</div>` +
    `<div class="meta">처리 <b style="color:#cdd3da">${s.count}</b>건 · 최근 ${esc(s.last_date || '미처리')}<br>` +
    `최근 토큰 평균 ${avgTok}</div>`;
  dash.appendChild(card);
});
// 부수 카드
if (DATA.counts.aux > 0) {
  const auxCard = document.createElement('div');
  auxCard.className = 'card aux';
  auxCard.innerHTML =
    `<div class="ttl"><span class="badge" style="background:${esc(AUX_COLOR)}">aux</span>부수 업무</div>` +
    `<div class="meta">처리 <b style="color:#9aa4af">${DATA.counts.aux}</b>건 · 지난 30일 ${DATA.counts.aux_30d}건</div>`;
  dash.appendChild(auxCard);
}

// ── 범례 채우기 ───────────────────────────────────────────────────
const legend = document.getElementById('legend');
const legParts = [];
(DATA.primary_tasks || []).forEach(t => {
  legParts.push(`<span><i style="background:${esc(PRIMARY_COLORS[t.id] || AUX_COLOR)}"></i>p${t.id}</span>`);
});
legParts.push(`<span><i style="background:${esc(AUX_COLOR)};opacity:.5"></i>aux</span>`);
legend.innerHTML = legParts.join('');

render();
window.addEventListener('resize', () => fitView(laidOut(buildLanes()), buildLanes()));
</script>
</body></html>
"""


def write_outputs(graph: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    title = f"{graph['agent']} — 업무 흐름 (Agentis 스윔레인)"
    safe_title = _html.escape(title)
    safe_agent = _html.escape(graph["agent"])

    if not graph["entries"]:
        # 빈 상태: log 없음 또는 primary_tasks 없음 모두
        msg = "아직 작업 기록이 없어요. 첫 업무를 시작해 보세요."
        if graph.get("empty_reason"):
            msg = graph["empty_reason"] + " — 첫 업무를 시작해 보세요."
        html = (EMPTY_HTML
                .replace("__TITLE__", safe_title)
                .replace("__AGENT__", safe_agent)
                .replace("__EMPTY_MSG__", _html.escape(msg)))
    else:
        payload = {
            "agent": graph["agent"],
            "entries": [{k: v for k, v in e.items() if k != "body_preview"} for e in graph["entries"]],
            "edges_time": graph["edges_time"],
            "edges_skill": graph["edges_skill"],
            "by_type": graph["by_type"],
            "skills_used": graph["skills_used"],
            "primary_tasks": graph["primary_tasks"],
            "primary_stats": graph["primary_stats"],
            "primary_colors": {str(k): v for k, v in graph["primary_colors"].items()},
            "aux_color": graph["aux_color"],
            "counts": graph["counts"],
            "types": graph["types"],
        }
        # JS 는 obj 의 키를 str/num 동일 처리하지만, JSON.parse 시 모두 str. lookup 을 obj[pid] (num key) 가 아닌
        # obj[String(pid)] 로 하도록 PRIMARY_COLORS 사용 측에서 처리.
        data_json = json.dumps(payload, ensure_ascii=False)
        html = MAIN_HTML
        html = html.replace("__TITLE__", safe_title)
        html = html.replace("__AGENT__", safe_agent)
        html = html.replace("__AUX_COLOR__", graph["aux_color"])
        html = html.replace("__DATA__", data_json)

    html_path = out_dir / "flow.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent  # .../agentis/graph
    ap = argparse.ArgumentParser(description="agentis 의 업무 흐름을 flow.html (스윔레인) 로 빌드")
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
    pn = len(graph["primary_tasks"])
    print(f"[build_flow] root={root}")
    if n == 0:
        print(f"[build_flow] {graph.get('empty_reason') or '항목 없음'} — 빈 폴백 HTML 생성 (primary_tasks {pn})")
    else:
        c = graph["counts"]
        print(f"[build_flow] {n} 작업 (주요 {c['primary']} / 부수 {c['aux']}) · primary_tasks {pn}개 · 시간엣지 {len(graph['edges_time'])} · 스킬그룹엣지 {len(graph['edges_skill'])}")
        if pn:
            for s in graph["primary_stats"]:
                print(f"             - [p{s['id']}] {s['name']}: {s['count']}건 (마지막 {s['last_date'] or '—'})")
        print(f"[build_flow] type 분포: " + ", ".join(f"{k} {v}" for k, v in sorted(graph["by_type"].items())))
    print(f"[build_flow] -> {html_path}  ({html_path.stat().st_size // 1024} KB, 자체완결 외부 의존 0)")

    if args.open:
        webbrowser.open(html_path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
