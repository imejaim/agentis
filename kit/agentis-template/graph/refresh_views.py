#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agentis-kit: v1.10 / refresh_views
"""
refresh_views.py — Agentis 사람용/호환용 시각화 산출물을 한 번에 갱신한다.

갱신 대상:
  - agentis/memory/_brain/brain.sqlite       (검색/회상 인덱스, 있으면)
  - agentis/graph/graph.html + graph.json    (기존 3D 호환 뷰)
  - agentis/graph/flow.html                  (기존 primary_tasks 스윔레인)
  - <workspace>/workflows.html               (.clinerules/workflows 결정론 뷰)
  - <workspace>/holonomic-brain.html/json    (사람용 두뇌 지도)

이 스크립트는 memory/agent.md/skills/workflows 원본을 수정하지 않는다.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def find_workspace(start: Path) -> Path:
    p = start.resolve()
    if p.is_file():
        p = p.parent
    for cand in [p, *p.parents]:
        if (cand / "agentis").is_dir() or (cand / ".clinerules").is_dir():
            return cand
    return p


def run(label: str, cmd: list[str], *, optional: bool = False) -> tuple[str, int]:
    print(f"[refresh_views] {label}: {' '.join(cmd)}")
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
    if proc.returncode != 0 and optional:
        print(f"[refresh_views] optional step failed: {label} ({proc.returncode})")
        return label, 0
    return label, proc.returncode


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Agentis view files refresh")
    ap.add_argument("--workspace", type=Path, default=here.parent.parent, help="작업 폴더 루트")
    ap.add_argument("--skip-legacy", action="store_true", help="graph/graph.html, flow.html 호환 산출물은 건너뜀")
    ap.add_argument("--quiet", action="store_true", help="성공 요약만 출력")
    args = ap.parse_args(argv)

    workspace = find_workspace(args.workspace)
    agentis = workspace / "agentis"
    graph_dir = agentis / "graph"
    if not agentis.is_dir():
        print(f"[refresh_views] agentis/ 폴더를 찾을 수 없음: {agentis}", file=sys.stderr)
        return 2

    results: list[tuple[str, int]] = []
    py = sys.executable or "python3"

    brain_index = agentis / "memory" / "_brain" / "build_brain_index.py"
    if brain_index.is_file():
        results.append(run("brain index", [py, str(brain_index), "--root", str(agentis), "--quiet"], optional=True))

    if not args.skip_legacy:
        build_graph = graph_dir / "build_graph.py"
        if build_graph.is_file():
            results.append(run("legacy graph", [py, str(build_graph), "--root", str(agentis), "--out", str(graph_dir)], optional=True))
        build_flow = graph_dir / "build_flow.py"
        if build_flow.is_file():
            results.append(run("legacy flow", [py, str(build_flow), "--root", str(agentis), "--out", str(graph_dir)], optional=True))

    build_workflows = graph_dir / "build_workflows.py"
    if build_workflows.is_file():
        results.append(run("workflows.html", [py, str(build_workflows), "--workspace", str(workspace)]))
    else:
        results.append(("workflows.html", 2))

    build_brain = graph_dir / "build_holonomic_brain.py"
    if build_brain.is_file():
        results.append(run("holonomic-brain.html", [py, str(build_brain), "--root", str(agentis), "--workspace", str(workspace)]))
    else:
        results.append(("holonomic-brain.html", 2))

    failed = [(label, code) for label, code in results if code != 0]
    if failed:
        print("[refresh_views] failed: " + ", ".join(f"{label}={code}" for label, code in failed), file=sys.stderr)
        return 1
    print(f"[refresh_views] OK workspace={workspace}")
    print(f"[refresh_views] root views: {workspace / 'workflows.html'} / {workspace / 'holonomic-brain.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
