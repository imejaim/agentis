#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.6 / agent-stats
"""
agent-stats.py — 에이전트의 능력치(Character Sheet) 자동 산출.

발상: 게임 캐릭터처럼 진화가 *눈에 보이게*. 동시에 메인 후보 1차 판단 지표.

자동 측정(결정론, 파일에서만):
  - total_log_entries : 로그 줄 수
  - by_type           : task / ingest / skill / lint / note / setup 종류별
  - skills_count      : skills/<dir>/SKILL.md 개수
  - workflows_count   : workflows/*.workflow.md 개수
  - memory_pages      : memory/**/*.md 페이지 수 (READMEs 제외)
  - concepts/entities/sources 개수
  - graph_nodes/edges : graph.json 있으면 거기서, 없으면 다시 계산
  - birth_date / age_days : log 첫 항목과 오늘
  - tokens / time     : (선택) memory/stats-raw.md 또는 로그 항목의 'tokens:'/'sec:' 메타에서 (없으면 0)

파생 능력치(RPG 풍):
  XP        = task*100 + ingest*200 + skill*500 + lint*300 + tokens/1000
  Level     = floor(sqrt(XP) / 4)
  Speed     = skills + workflows               (= 가진 도구 수)
  INT       = memory_pages + edges//3          (= 두뇌 연결성)
  Variety   = unique by_type + unique tags     (= 다양성)
  Stamina   = age_days
  Wisdom    = lint_count + (concepts>=5)?2:0 + (concepts>=10)?3:0   (=정비/추상화)

출력:
  - 콘솔: 캐릭터 시트 한 장 (utf-8)
  - agentis/memory/stats.md : 같은 내용 + 메모리 노드로 그래프에 자동 편입

표준 라이브러리만. 결정론적.

사용:
    python agentis/graph/agent-stats.py            # 콘솔 + stats.md 둘 다 갱신
    python agentis/graph/agent-stats.py --quiet    # stats.md 만
    python agentis/graph/agent-stats.py --no-write # 콘솔만
"""
from __future__ import annotations
import argparse
import datetime as _dt
import json
import math
import re
import sys
from pathlib import Path
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

LOG_HEADER_RE = re.compile(
    r"^##\s*\[(\d{4}-\d{2}-\d{2})\]\s*(\w+)\s*(?:\[(primary:\d+|aux)\])?\s*\|\s*(.+?)\s*$",
    re.MULTILINE,
)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


def parse_primary_tasks(agent_text: str) -> list[dict]:
    """agent.md 의 `primary_tasks:` YAML 리스트 파싱. pyyaml 의존 없음."""
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
    end_re_hard = re.compile(r"^(##\s|```|\Z)")
    item_re = re.compile(r"^(\s*)-\s+(.+)$")
    kv_re = re.compile(r"^(\s*)([A-Za-z_][\w-]*)\s*:\s*(.*)$")
    for j in range(start, len(lines)):
        ln = lines[j]
        if end_re_hard.match(ln):
            break
        if ln.strip() == "":
            continue
        if ln.lstrip().startswith("#"):
            continue
        m_item = item_re.match(ln)
        if m_item:
            if cur:
                tasks.append(cur)
            cur = {}
            rest = m_item.group(2).strip()
            mkv = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.+)$", rest)
            if mkv:
                cur[mkv.group(1).lower()] = mkv.group(2).strip().strip("\"'")
            continue
        m_kv = kv_re.match(ln)
        if m_kv and cur is not None:
            k = m_kv.group(2).lower()
            v = m_kv.group(3).strip().strip("\"'")
            if len(m_kv.group(1)) == 0 and k != "primary_tasks":
                break
            cur[k] = v
            continue
        if not ln.startswith(" ") and not ln.startswith("\t"):
            break
    if cur:
        tasks.append(cur)
    out = []
    for idx, t in enumerate(tasks, start=1):
        if "name" not in t and "id" not in t:
            continue
        try:
            tid = int(t.get("id", idx))
        except (TypeError, ValueError):
            tid = idx
        name = t.get("name", f"primary {tid}").strip()
        if not name:
            continue
        out.append({"id": tid, "name": name})
    out.sort(key=lambda x: x["id"])
    return out


def find_root(start: Path) -> Path:
    p = (start if start.is_dir() else start.parent).resolve()
    for c in [p, *p.parents]:
        if (c / "agent.md").exists():
            return c
    return p


def parse_h1(text: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip() if m else fallback


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def list_md(d: Path) -> list[Path]:
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.rglob("*.md")):
        if f.name.lower() in ("readme.md",) or f.name.startswith(("_template",)):
            continue
        out.append(f)
    return out


def parse_extra_meta(text: str) -> tuple[int, float]:
    """로그 항목 본문에서 'tokens: N' / 'sec: X' 메타를 발견하면 합산. 없으면 0."""
    tok = 0; sec = 0.0
    for m in re.finditer(r"tokens?\s*[:=]\s*([\d,]+)", text, re.IGNORECASE):
        tok += int(m.group(1).replace(",", ""))
    for m in re.finditer(r"\b(sec|seconds?|초)\s*[:=]\s*([\d.]+)", text, re.IGNORECASE):
        try:
            sec += float(m.group(2))
        except Exception:
            pass
    return tok, sec


def collect(root: Path) -> dict:
    out = {"root": str(root)}

    # agent.md
    agent_text = (root / "agent.md").read_text(encoding="utf-8", errors="replace")
    out["name"] = parse_h1(agent_text, root.name)

    # primary_tasks (v1.6)
    out["primary_tasks"] = parse_primary_tasks(agent_text)

    # log
    log = root / "memory" / "log.md"
    by_type = Counter()
    entries = []
    primary_counter: Counter[int] = Counter()
    aux_count = 0
    primary_total = 0
    if log.is_file():
        text = log.read_text(encoding="utf-8", errors="replace")
        for m in LOG_HEADER_RE.finditer(text):
            date, typ, tag_raw, title = m.group(1), m.group(2).lower(), (m.group(3) or "").lower(), m.group(4)
            entries.append((date, typ, title))
            by_type[typ] += 1
            if tag_raw.startswith("primary:"):
                try:
                    pid = int(tag_raw.split(":", 1)[1])
                    primary_counter[pid] += 1
                    primary_total += 1
                except (ValueError, IndexError):
                    aux_count += 1
            else:
                aux_count += 1
        tokens, secs = parse_extra_meta(text)
    else:
        tokens, secs = 0, 0.0
    out["entries"] = entries
    out["by_type"] = dict(by_type)
    out["tokens"] = tokens
    out["seconds"] = secs
    out["primary_counts"] = dict(primary_counter)   # {1: 23, 2: 18, ...}
    out["primary_total"] = primary_total
    out["aux_count"] = aux_count

    # birth/age
    if entries:
        try:
            d0 = min(_dt.date.fromisoformat(e[0]) for e in entries)
            out["birth_date"] = d0.isoformat()
            out["age_days"] = max(1, (_dt.date.today() - d0).days)
        except Exception:
            out["birth_date"] = ""
            out["age_days"] = 0
    else:
        out["birth_date"] = ""
        out["age_days"] = 0

    # skills / workflows
    sk = root / "skills"
    out["skills_count"] = sum(1 for d in (sk.iterdir() if sk.is_dir() else []) if d.is_dir() and (d / "SKILL.md").is_file())
    wf = root / "workflows"
    out["workflows_count"] = sum(1 for f in (wf.iterdir() if wf.is_dir() else []) if f.is_file() and f.name.endswith(".workflow.md"))

    # memory pages
    mem = root / "memory"
    pages = list_md(mem)
    out["memory_pages"] = len(pages)
    out["concepts"] = len(list_md(mem / "concepts"))
    out["entities"] = len(list_md(mem / "entities"))
    out["sources"]  = len(list_md(mem / "sources"))

    # tags (도메인 유전자 후보)
    tag_counter = Counter()
    for f in pages:
        try:
            fm = parse_frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        raw = fm.get("tags", "")
        if raw:
            for t in re.split(r"[,\[\]\s]+", raw):
                t = t.strip("'\"")
                if t:
                    tag_counter[t.lower()] += 1
    out["top_tags"] = tag_counter.most_common(8)

    # graph
    gj = root / "graph" / "graph.json"
    if gj.is_file():
        try:
            g = json.loads(gj.read_text(encoding="utf-8"))
            out["graph_nodes"] = g["stats"]["nodes"]
            out["graph_edges"] = g["stats"]["edges"]
        except Exception:
            out["graph_nodes"] = 0; out["graph_edges"] = 0
    else:
        out["graph_nodes"] = 0; out["graph_edges"] = 0

    return out


# ─── 파생 ────────────────────────────────────────────────────────────────────

def derive(s: dict) -> dict:
    bt = s["by_type"]
    task = bt.get("task", 0); ingest = bt.get("ingest", 0); skill = bt.get("skill", 0)
    lint = bt.get("lint", 0); note = bt.get("note", 0); setup = bt.get("setup", 0)

    xp = task * 100 + ingest * 200 + skill * 500 + lint * 300 + (s["tokens"] // 1000)
    level = int(math.sqrt(xp) / 4) if xp > 0 else 0
    speed = s["skills_count"] + s["workflows_count"]
    intel = s["memory_pages"] + (s["graph_edges"] // 3)
    variety = len([k for k, v in bt.items() if v > 0]) + len(s["top_tags"])
    stamina = s["age_days"]
    wisdom = lint + (2 if s["concepts"] >= 5 else 0) + (3 if s["concepts"] >= 10 else 0)

    eff = None
    if s["tokens"] > 0 and (task + ingest) > 0:
        eff = round((task + ingest) * 1000 / max(1, s["tokens"]), 2)  # 1000 토큰당 작업 처리 수

    return {
        "XP": xp, "Level": level,
        "Speed": speed, "INT": intel, "Variety": variety,
        "Stamina": stamina, "Wisdom": wisdom,
        "Efficiency_per_1k_tok": eff,
        "_breakdown": {"task": task, "ingest": ingest, "skill": skill, "lint": lint, "note": note, "setup": setup},
    }


# ─── 렌더 ────────────────────────────────────────────────────────────────────

BAR_CHARS = "▏▎▍▌▋▊▉█"  # 8 단계


def bar(val: int | float, vmax: int | float, width: int = 12) -> str:
    if vmax <= 0:
        return "░" * width
    r = min(1.0, max(0.0, val / vmax))
    fill = int(round(r * width))
    return "█" * fill + "░" * (width - fill)


def sheet(s: dict, d: dict, *, plain: bool = False) -> str:
    name = s["name"]
    birth = s["birth_date"] or "(아직 없음)"
    age = s["age_days"]
    bt = d["_breakdown"]
    eff = d["Efficiency_per_1k_tok"]
    eff_s = f"{eff}" if eff is not None else "(토큰 미기록)"

    lines = []
    lines.append("═" * 56)
    lines.append(f" 🧬  {name} — Agentis Character Sheet")
    lines.append("═" * 56)
    lines.append(f"  Level: {d['Level']:>3}      XP: {d['XP']:>6,}      생일: {birth} ({age}일째)")
    lines.append("─" * 56)
    lines.append(f"  ⚡ Speed     {d['Speed']:>3}  {bar(d['Speed'], 30)}  (스킬+워크플로우)")
    lines.append(f"  🧠 INT       {d['INT']:>3}  {bar(d['INT'], 60)}  (기억·연결성)")
    lines.append(f"  🎨 Variety   {d['Variety']:>3}  {bar(d['Variety'], 20)}  (작업·태그 다양성)")
    lines.append(f"  💪 Stamina   {d['Stamina']:>3}  {bar(d['Stamina'], 365)} (생존일수)")
    lines.append(f"  🦉 Wisdom    {d['Wisdom']:>3}  {bar(d['Wisdom'], 15)}  (정비·추상화)")
    lines.append("─" * 56)
    lines.append(f"  작업 — task {bt['task']} / ingest {bt['ingest']} / skill {bt['skill']} / lint {bt['lint']} / note {bt['note']} / setup {bt['setup']}")
    lines.append(f"  보유 — 스킬 {s['skills_count']} / 워크플로우 {s['workflows_count']} / 메모리 페이지 {s['memory_pages']}")
    lines.append(f"  메모리 — 개념 {s['concepts']} / 엔티티 {s['entities']} / 소스 {s['sources']}")
    lines.append(f"  그래프 — 노드 {s['graph_nodes']} / 엣지 {s['graph_edges']}")
    lines.append(f"  토큰 사용 — {s['tokens']:,}  ·  처리시간 합 — {s['seconds']:.1f}s")
    lines.append(f"  효율(작업/1k토큰) — {eff_s}")

    # 주요 업무 처리율 (v1.6)
    pt = s.get("primary_tasks", []) or []
    p_total = s.get("primary_total", 0)
    a_count = s.get("aux_count", 0)
    denom = p_total + a_count
    if pt:
        lines.append("─" * 56)
        rate = (p_total * 100 // denom) if denom else 0
        lines.append(f"  🎯 주요 업무 처리율: {rate}% ({p_total} / {denom}건)")
        for t in pt:
            cnt = s.get("primary_counts", {}).get(t["id"], 0)
            lines.append(f"     - [{t['id']}] {t['name']}: {cnt}건")
        lines.append(f"     부수 업무: {a_count}건")

    if s["top_tags"]:
        lines.append("─" * 56)
        lines.append("  🧬 감지된 도메인 유전자 (상위 태그):")
        for t, c in s["top_tags"]:
            lines.append(f"     {t}  ×{c}")
    lines.append("═" * 56)
    return "\n".join(lines)


def stats_md(s: dict, d: dict) -> str:
    today = _dt.date.today().isoformat()
    bt = d["_breakdown"]
    eff = d["Efficiency_per_1k_tok"]
    tags = "\n".join(f"- `{t}`  ×{c}" for t, c in s["top_tags"]) or "- (아직 없음)"

    # 주요 업무 처리율 (v1.6)
    pt = s.get("primary_tasks", []) or []
    p_total = s.get("primary_total", 0)
    a_count = s.get("aux_count", 0)
    denom = p_total + a_count
    rate = (p_total * 100 // denom) if denom else 0
    if pt:
        primary_block_lines = [
            f"## 🎯 주요 업무 처리율 (v1.6)",
            "",
            f"- **처리율**: **{rate}%** ({p_total} / {denom}건)",
            "",
            "| # | 주요 업무 | 처리 횟수 |",
            "|---|----------|---------|",
        ]
        for t in pt:
            cnt = s.get("primary_counts", {}).get(t["id"], 0)
            primary_block_lines.append(f"| {t['id']} | {t['name']} | {cnt} |")
        primary_block_lines.append(f"| — | 부수 업무 (aux) | {a_count} |")
        primary_block = "\n".join(primary_block_lines) + "\n"
    else:
        primary_block = (
            "## 🎯 주요 업무 처리율 (v1.6)\n\n"
            "_아직 `primary_tasks:` 가 정의되지 않았어요. `agent.md` 에 3~5개 채우면 처리율이 집계됩니다._\n"
        )

    return f"""---
type: stats
updated: {today}
auto: true
---

# 🧬 {s['name']} — Character Sheet

> 능력치는 `agentis/` 파일에서 자동 산출됩니다 (`python agentis/graph/agent-stats.py`). 진화하는 모습이 눈에 보이도록.

## 요약
- **Level**: {d['Level']}  ·  **XP**: {d['XP']:,}
- **생일**: {s['birth_date'] or '(아직 없음)'}  ·  **나이**: {s['age_days']}일
- **효율(작업/1k 토큰)**: {eff if eff is not None else '(토큰 미기록)'}

{primary_block}

## 능력치

| 능력 | 값 | 설명 |
|------|----|----|
| ⚡ Speed | **{d['Speed']}** | 스킬 + 워크플로우 (가진 도구) |
| 🧠 INT | **{d['INT']}** | 메모리 페이지 + 그래프 연결성 |
| 🎨 Variety | **{d['Variety']}** | 작업 종류 + 태그 다양성 |
| 💪 Stamina | **{d['Stamina']}** | 생존일수 |
| 🦉 Wisdom | **{d['Wisdom']}** | 정비(lint) + 개념 추상화 |

## 작업 내역 (`memory/log.md` 집계)

| 종류 | 수 |
|------|----|
| task   | {bt['task']} |
| ingest | {bt['ingest']} |
| skill  | {bt['skill']} |
| lint   | {bt['lint']} |
| note   | {bt['note']} |
| setup  | {bt['setup']} |

## 보유 자원

- 스킬: **{s['skills_count']}** (`skills/<이름>/SKILL.md`)
- 워크플로우: **{s['workflows_count']}** (`workflows/*.workflow.md`)
- 메모리 페이지: **{s['memory_pages']}** (개념 {s['concepts']} / 엔티티 {s['entities']} / 소스 {s['sources']})
- 그래프: 노드 {s['graph_nodes']} / 엣지 {s['graph_edges']}

## 🧬 감지된 도메인 유전자 (상위 태그)

{tags}

## XP 산식 (참고)

```
XP = task×100 + ingest×200 + skill×500 + lint×300 + (tokens / 1000)
Level = floor(sqrt(XP) / 4)
```

토큰·시간을 정확히 반영하려면 `memory/log.md` 항목 본문에 `tokens: N` / `sec: T` 메타를 한 줄 적어두면 자동 합산됩니다.
"""


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="에이전트 능력치(Character Sheet) 산출")
    ap.add_argument("--root", type=Path, default=here.parent, help="agentis 디렉토리 (기본: 스크립트 기준 ../)")
    ap.add_argument("--quiet", action="store_true", help="콘솔 출력 생략, stats.md 만 갱신")
    ap.add_argument("--no-write", action="store_true", help="stats.md 쓰지 않고 콘솔만")
    args = ap.parse_args(argv)

    root = find_root(args.root)
    if not (root / "agent.md").is_file():
        print(f"[stats] agent.md 를 찾을 수 없음: {root}", file=sys.stderr)
        return 2

    s = collect(root)
    d = derive(s)

    if not args.quiet:
        print(sheet(s, d))

    if not args.no_write:
        out = root / "memory" / "stats.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(stats_md(s, d), encoding="utf-8")
        if not args.quiet:
            print(f"[stats] -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
