#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.10 / build_workflows
"""
build_workflows.py — .clinerules/workflows/*.md 를 결정론적으로 읽어
작업 폴더 루트의 workflows.html 을 만든다.

원칙:
  - 정본 입력은 agentis/workflows/ 가 아니라 .clinerules/workflows/ 이다.
  - 생성물은 사람에게 보여지는 문서이므로 작업 폴더 루트의 workflows.html 로 둔다.
  - 정렬은 파일명 기준 stable sort. mtime/현재시각은 쓰지 않는다.
  - 외부 CDN/패키지 없이 단일 HTML.
"""
from __future__ import annotations

import argparse
import hashlib
import html
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

H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$", re.MULTILINE)
CHECK_RE = re.compile(r"^\s*-\s+\[[ xX]\]\s+(.+?)\s*$", re.MULTILINE)
BULLET_RE = re.compile(r"^\s*-\s+(?!\[[ xX]\])(.+?)\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)

EXCLUDE_PREFIXES = (".", "_")
EXCLUDE_PARTS = ("backup", ".backup-", "~")


def find_workspace(start: Path) -> Path:
    p = start.resolve()
    if p.is_file():
        p = p.parent
    for cand in [p, *p.parents]:
        if (cand / ".clinerules" / "workflows").is_dir() or (cand / "agentis").is_dir():
            return cand
    return p


def is_workflow_file(path: Path) -> bool:
    name = path.name
    lower = name.lower()
    if path.suffix.lower() != ".md":
        return False
    if name.startswith(EXCLUDE_PREFIXES):
        return False
    if any(part in lower for part in EXCLUDE_PARTS):
        return False
    return path.is_file()


def title_of(text: str, fallback: str) -> str:
    m = H1_RE.search(text)
    if m:
        return m.group(1).strip() or fallback
    return fallback


def short(text: str, limit: int = 160) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[#>*_`\[\]()-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


def extract_commands(fences: list[str]) -> list[str]:
    cmds: list[str] = []
    for block in fences:
        for ln in block.splitlines():
            line = ln.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(("python ", "python3 ", "uv ", "npm ", "node ", "git ", "pytest ")):
                cmds.append(line)
            if len(cmds) >= 4:
                return cmds
    return cmds


def collect(workspace: Path, workflows_dir: Path | None = None) -> dict:
    wf_dir = workflows_dir or (workspace / ".clinerules" / "workflows")
    files = sorted([p for p in wf_dir.glob("*.md") if is_workflow_file(p)], key=lambda p: (p.name != "00-전체업무순서.md", p.name)) if wf_dir.is_dir() else []
    items = []
    for p in files:
        text = p.read_text(encoding="utf-8", errors="replace")
        stem = p.stem
        headings = [m.group(2).strip() for m in HEADING_RE.finditer(text)][:8]
        checks = [m.group(1).strip() for m in CHECK_RE.finditer(text)][:8]
        bullets = [m.group(1).strip() for m in BULLET_RE.finditer(text)][:8]
        fences = FENCE_RE.findall(text)
        script = workspace / "agentis" / "workflows" / f"{stem}.py"
        source_workflow = workspace / "agentis" / "workflows" / f"{stem}.workflow.md"
        sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]
        items.append({
            "file": p.relative_to(workspace).as_posix() if p.is_relative_to(workspace) else p.as_posix(),
            "stem": stem,
            "title": title_of(text, stem),
            "summary": short(text),
            "headings": headings,
            "checks": checks,
            "bullets": bullets,
            "commands": extract_commands(fences),
            "has_script": script.is_file(),
            "script": script.relative_to(workspace).as_posix() if script.is_file() else None,
            "has_agentis_source": source_workflow.is_file(),
            "agentis_source": source_workflow.relative_to(workspace).as_posix() if source_workflow.is_file() else None,
            "sections": len(headings),
            "check_count": len(CHECK_RE.findall(text)),
            "command_count": len(extract_commands(fences)),
            "sha256_12": sha,
        })
    return {
        "source": wf_dir.relative_to(workspace).as_posix() if wf_dir.exists() and wf_dir.is_relative_to(workspace) else wf_dir.as_posix(),
        "count": len(items),
        "items": items,
        "stats": {
            "scripted": sum(1 for x in items if x["has_script"]),
            "with_checks": sum(1 for x in items if x["check_count"] > 0),
            "with_commands": sum(1 for x in items if x["command_count"] > 0),
        },
    }


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


def render(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    cards = []
    for i, item in enumerate(data["items"], start=1):
        badges = []
        badges.append("실행스크립트" if item["has_script"] else "문서전용")
        if item["check_count"]:
            badges.append(f"체크 {item['check_count']}")
        if item["command_count"]:
            badges.append(f"명령 {item['command_count']}")
        steps = item["checks"] or item["bullets"] or item["headings"]
        steps_html = "".join(f"<li>{esc(x)}</li>" for x in steps[:6]) or "<li>본문 절차를 확인하세요.</li>"
        cards.append(f"""
        <article class="card">
          <div class="num">{i:02d}</div>
          <div class="body">
            <h2>{esc(item['title'])}</h2>
            <p>{esc(item['summary'])}</p>
            <div class="badges">{''.join(f'<span>{esc(b)}</span>' for b in badges)}</div>
            <ol>{steps_html}</ol>
            <footer><code>{esc(item['file'])}</code>{' · <code>'+esc(item['script'])+'</code>' if item['script'] else ''}</footer>
          </div>
        </article>""")
    if not cards:
        cards.append("<article class='empty'>.clinerules/workflows/ 에 확정 workflow md 파일이 아직 없습니다.</article>")
    flow_nodes = "".join(f"<div class='flow-node'><b>{i:02d}</b><span>{esc(x['title'])}</span></div>" for i, x in enumerate(data["items"], start=1))
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agentis Workflows</title>
<style>
:root{{--bg:#f7f8fb;--ink:#141821;--muted:#687386;--line:#dfe5ef;--card:#fff;--blue:#2563eb;--green:#059669;--amber:#d97706}}
*{{box-sizing:border-box}} body{{margin:0;background:linear-gradient(180deg,#f8fbff,#f3f4f8);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
header{{padding:34px 22px 18px;max-width:1100px;margin:auto}} h1{{font-size:34px;margin:0 0 8px;letter-spacing:-.03em}} .lead{{color:var(--muted);max-width:820px}}
.stats{{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}} .stat{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:10px 14px;box-shadow:0 8px 24px rgba(20,24,33,.05)}} .stat b{{display:block;font-size:24px}}
main{{max-width:1100px;margin:0 auto 50px;padding:0 22px}} .flow{{display:flex;gap:10px;overflow-x:auto;padding:12px 0 22px;margin-bottom:12px}}
.flow-node{{min-width:190px;background:#0f172a;color:white;border-radius:18px;padding:13px 14px;position:relative;box-shadow:0 12px 30px rgba(15,23,42,.16)}} .flow-node b{{color:#93c5fd;margin-right:8px}} .flow-node:after{{content:'→';position:absolute;right:-13px;top:50%;transform:translateY(-50%);color:#64748b}} .flow-node:last-child:after{{display:none}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}} .card{{display:flex;gap:14px;background:var(--card);border:1px solid var(--line);border-radius:20px;padding:18px;box-shadow:0 10px 30px rgba(20,24,33,.06)}}
.num{{font-weight:800;color:var(--blue);font-size:18px}} h2{{font-size:18px;margin:0 0 6px}} p{{margin:0 0 10px;color:#4b5563}} ol{{padding-left:19px;margin:11px 0}} li{{margin:4px 0}} .badges{{display:flex;gap:6px;flex-wrap:wrap}} .badges span{{font-size:12px;background:#eef4ff;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:999px;padding:3px 8px}} footer{{font-size:12px;color:var(--muted);border-top:1px dashed var(--line);padding-top:10px;margin-top:10px}} code{{background:#f1f5f9;border-radius:6px;padding:2px 5px}} .empty{{padding:30px;background:white;border:1px dashed var(--line);border-radius:18px;color:var(--muted)}}
.note{{margin-top:24px;color:var(--muted);font-size:13px}} @media(max-width:640px){{h1{{font-size:28px}} .card{{padding:15px}} .flow-node{{min-width:170px}}}}
</style></head><body>
<header>
  <h1>Workflows</h1>
  <p class="lead">확정 업무 절차를 <code>{esc(data['source'])}</code> 에서 결정론적으로 읽어 만든 사람용 안내판입니다. 이 HTML은 편집 정본이 아니며, 원본 markdown을 고치고 refresh 하면 다시 생성됩니다.</p>
  <div class="stats"><div class="stat"><b>{data['count']}</b>workflow</div><div class="stat"><b>{data['stats']['scripted']}</b>scripted</div><div class="stat"><b>{data['stats']['with_checks']}</b>with checks</div><div class="stat"><b>{data['stats']['with_commands']}</b>with commands</div></div>
</header>
<main>
  <section class="flow">{flow_nodes}</section>
  <section class="grid">{''.join(cards)}</section>
  <p class="note">자동 갱신: <code>python agentis/graph/refresh_views.py --workspace .</code> · 데이터는 아래 <code>DATA</code> JSON에 포함됩니다.</p>
</main>
<script>const DATA = {payload};</script>
</body></html>"""


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as fh:
        fh.write(content)
        tmp = Path(fh.name)
    tmp.replace(path)


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=".clinerules/workflows 를 root workflows.html 로 렌더")
    ap.add_argument("--workspace", type=Path, default=here.parent.parent, help="작업 폴더 루트 (기본: agentis/graph 기준 ../../)")
    ap.add_argument("--workflows", type=Path, default=None, help="입력 workflows 디렉토리 (기본: <workspace>/.clinerules/workflows)")
    ap.add_argument("--out", type=Path, default=None, help="출력 HTML (기본: <workspace>/workflows.html)")
    ap.add_argument("--open", action="store_true", help="생성 후 브라우저로 열기")
    args = ap.parse_args(argv)

    workspace = find_workspace(args.workspace)
    out = args.out or (workspace / "workflows.html")
    data = collect(workspace, args.workflows)
    html_text = render(data)
    atomic_write(out.resolve(), html_text)
    print(f"[build_workflows] source={data['source']} workflows={data['count']}")
    print(f"[build_workflows] -> {out.resolve()} ({out.resolve().stat().st_size} bytes)")
    if args.open:
        webbrowser.open(out.resolve().as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
