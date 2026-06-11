import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


install = load_module("agentis_install", ROOT / "install.py")
build_flow = load_module("agentis_build_flow", ROOT / "kit" / "agentis-template" / "graph" / "build_flow.py")
build_workflows = load_module("agentis_build_workflows", ROOT / "kit" / "agentis-template" / "graph" / "build_workflows.py")
build_holonomic = load_module("agentis_build_holonomic", ROOT / "kit" / "agentis-template" / "graph" / "build_holonomic_brain.py")


class AgentisUpgradeSafetyTests(unittest.TestCase):
    def test_install_routing_rule_copies_natural_language_router(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            src = base / "seed" / "10-agent-routing.md"
            target = base / "project"
            src.parent.mkdir(parents=True)
            target.mkdir()
            src.write_text("# router\n", encoding="utf-8")

            dst, status = install.install_routing_rule(src, target, dry_run=False)

            self.assertEqual(dst, target / ".clinerules" / "10-agent-routing.md")
            self.assertEqual(status, "added")
            self.assertEqual(dst.read_text(encoding="utf-8"), "# router\n")

    def test_install_rule_workflows_copies_kit_workflows_to_clinerules(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            workflows_src = base / "kit" / "agentis-template" / "workflows"
            target = base / "project"
            workflows_src.mkdir(parents=True)
            target.mkdir()
            (workflows_src / "월간보고.workflow.md").write_text("# 월간보고\n", encoding="utf-8")

            dst, stats = install.install_rule_workflows(workflows_src, target, dry_run=False)

            self.assertEqual(dst, target / ".clinerules" / "workflows")
            self.assertTrue((target / ".clinerules" / "workflows" / "월간보고.md").is_file())
            self.assertEqual(stats["added"], 1)

    def test_install_rule_workflows_preserves_user_modified_rules_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            workflows_src = base / "kit" / "agentis-template" / "workflows"
            target_rule = base / "project" / ".clinerules" / "workflows" / "월간보고.md"
            workflows_src.mkdir(parents=True)
            target_rule.parent.mkdir(parents=True)
            (workflows_src / "월간보고.workflow.md").write_text("# standard\n", encoding="utf-8")
            target_rule.write_text("# user custom\n", encoding="utf-8")

            _dst, stats = install.install_rule_workflows(workflows_src, base / "project", dry_run=False, force=False)

            self.assertEqual(target_rule.read_text(encoding="utf-8"), "# user custom\n")
            self.assertEqual(stats["kept"], 1)

    def test_safe_kit_upgrade_preserves_generated_graph_and_memory(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            kit_src = base / "kit-src"
            kit_dst = base / "project" / "agentis"
            (kit_src / "graph").mkdir(parents=True)
            (kit_src / "memory").mkdir(parents=True)
            (kit_src / "graph" / "flow.html").write_text("TEMPLATE FLOW", encoding="utf-8")
            (kit_src / "graph" / "graph.html").write_text("TEMPLATE GRAPH", encoding="utf-8")
            (kit_src / "memory" / "log.md").write_text("TEMPLATE LOG", encoding="utf-8")
            (kit_src / "graph" / "README.md").write_text("new guide", encoding="utf-8")

            (kit_dst / "graph").mkdir(parents=True)
            (kit_dst / "memory").mkdir(parents=True)
            (kit_dst / "graph" / "flow.html").write_text("USER FLOW", encoding="utf-8")
            (kit_dst / "graph" / "graph.html").write_text("USER GRAPH", encoding="utf-8")
            (kit_dst / "memory" / "log.md").write_text("USER LOG", encoding="utf-8")

            stats = install.safe_upgrade_kit(kit_src, kit_dst, dry_run=False)

            self.assertEqual((kit_dst / "graph" / "flow.html").read_text(encoding="utf-8"), "USER FLOW")
            self.assertEqual((kit_dst / "graph" / "graph.html").read_text(encoding="utf-8"), "USER GRAPH")
            self.assertEqual((kit_dst / "memory" / "log.md").read_text(encoding="utf-8"), "USER LOG")
            self.assertEqual((kit_dst / "graph" / "README.md").read_text(encoding="utf-8"), "new guide")
            self.assertGreaterEqual(stats["protected_kept"], 3)
            self.assertEqual(stats["added"], 1)

    def test_safe_kit_upgrade_updates_kit_owned_script_with_backup(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            kit_src = base / "kit-src"
            kit_dst = base / "project" / "agentis"
            (kit_src / "graph").mkdir(parents=True)
            (kit_dst / "graph").mkdir(parents=True)
            rel = Path("graph") / "build_flow.py"
            (kit_src / rel).write_text("# agentis-kit: v1.9 / build_flow\nNEW", encoding="utf-8")
            (kit_dst / rel).write_text("# agentis-kit: v1.7 / build_flow\nOLD", encoding="utf-8")

            stats = install.safe_upgrade_kit(kit_src, kit_dst, dry_run=False)

            self.assertIn("v1.9", (kit_dst / rel).read_text(encoding="utf-8"))
            self.assertEqual(stats["updated"], 1)
            backups = list((kit_dst / ".upgrade-backups").rglob("build_flow.py"))
            self.assertEqual(len(backups), 1)
            self.assertIn("v1.7", backups[0].read_text(encoding="utf-8"))

    def test_upgrade_kit_preserves_existing_seed_and_clinerules_workflows(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "project"
            target.mkdir()
            (target / ".clinerules" / "workflows").mkdir(parents=True)
            (target / ".clinerules" / "agentis.md").write_text("# USER SEED\ncustom", encoding="utf-8")
            (target / ".clinerules" / "workflows" / "00-전체업무순서.md").write_text("# USER FLOW\ncustom", encoding="utf-8")
            (target / "agentis" / "graph").mkdir(parents=True)
            (target / "agentis" / "graph" / "build_flow.py").write_text("# agentis-kit: old\nOLD", encoding="utf-8")

            rc = install.main(["--target", str(target), "--upgrade-kit", "--quiet"])

            self.assertEqual(rc, install.EXIT_OK)
            self.assertEqual((target / ".clinerules" / "agentis.md").read_text(encoding="utf-8"), "# USER SEED\ncustom")
            self.assertEqual((target / ".clinerules" / "workflows" / "00-전체업무순서.md").read_text(encoding="utf-8"), "# USER FLOW\ncustom")
            self.assertIn("agentis-kit:", (target / "agentis" / "graph" / "build_flow.py").read_text(encoding="utf-8"))

    def test_safe_kit_upgrade_skips_pycache_and_generated_root_views(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            kit_src = base / "kit-src"
            kit_dst = base / "project" / "agentis"
            (kit_src / "graph" / "__pycache__").mkdir(parents=True)
            (kit_src / "graph" / "__pycache__" / "x.pyc").write_bytes(b"compiled")
            (kit_src / "workflows.html").write_text("TEMPLATE", encoding="utf-8")
            kit_dst.mkdir(parents=True)
            (kit_dst / "workflows.html").write_text("USER VIEW", encoding="utf-8")

            stats = install.safe_upgrade_kit(kit_src, kit_dst, dry_run=False)

            self.assertFalse((kit_dst / "graph" / "__pycache__" / "x.pyc").exists())
            self.assertEqual((kit_dst / "workflows.html").read_text(encoding="utf-8"), "USER VIEW")
            self.assertGreaterEqual(stats["protected_kept"], 1)


class AgentisRootViewTests(unittest.TestCase):
    def test_build_workflows_reads_clinerules_workflows(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            wf = workspace / ".clinerules" / "workflows"
            wf.mkdir(parents=True)
            (wf / "00-전체업무순서.md").write_text("# 전체 업무 순서\n\n- [ ] 확인\n```bash\npython agentis/graph/refresh_views.py --workspace .\n```\n", encoding="utf-8")
            (wf / "보고.md").write_text("# 보고\n\n## 절차\n- 초안\n- 검증\n", encoding="utf-8")
            (wf / "_template.md").write_text("# ignored", encoding="utf-8")
            (workspace / "agentis" / "workflows").mkdir(parents=True)
            (workspace / "agentis" / "workflows" / "보고.py").write_text("print('ok')", encoding="utf-8")

            data = build_workflows.collect(workspace)
            out = workspace / "workflows.html"
            build_workflows.atomic_write(out, build_workflows.render(data))
            text = out.read_text(encoding="utf-8")

            self.assertEqual([x["title"] for x in data["items"]], ["전체 업무 순서", "보고"])
            self.assertTrue(data["items"][1]["has_script"])
            self.assertIn("const DATA =", text)
            self.assertIn("전체 업무 순서", text)

    def test_build_holonomic_brain_writes_root_html_and_json(self):
        with tempfile.TemporaryDirectory() as td:
            workspace = Path(td)
            root = workspace / "agentis"
            (root / "memory" / "concepts").mkdir(parents=True)
            (root / "memory" / "_brain").mkdir(parents=True)
            (root / "agent.md").write_text("# 라대리\n\n[[memory/concepts/업무]]\n", encoding="utf-8")
            (root / "memory" / "hot.md").write_text("[[memory/concepts/업무]]\n", encoding="utf-8")
            (root / "memory" / "concepts" / "업무.md").write_text("# 업무\n", encoding="utf-8")
            (root / "memory" / "_brain" / "holonomic.md").write_text("# Holonomic\n부분이 전체를 담는다.", encoding="utf-8")

            rc = build_holonomic.main(["--root", str(root), "--workspace", str(workspace)])

            self.assertEqual(rc, 0)
            html = (workspace / "holonomic-brain.html").read_text(encoding="utf-8")
            js = (workspace / "holonomic-brain.json").read_text(encoding="utf-8")
            self.assertIn("Holonomic Brain", html)
            self.assertIn("const DATA =", html)
            self.assertIn("memory/concepts/업무", js)


class AgentisFlowGuideTests(unittest.TestCase):
    def test_build_flow_prefers_primary_workflow_lanes_over_history_timeline(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "agentis"
            (root / "memory").mkdir(parents=True)
            (root / "agent.md").write_text(
                """# 라대리\n\n```yaml\nprimary_tasks:\n  - id: 1\n    name: 고객 문의 처리\n    description: 문의 접수부터 답변까지\n    workflow:\n      - 문의 접수\n      - 원인 확인\n      - 답변/기록\n  - id: 2\n    name: 월간 리포트\n    description: 월간 지표 보고\n    workflow:\n      - 데이터 수집\n      - 검증\n      - 보고서 발행\n  - id: 3\n    name: 장애 대응\n    description: 장애 감지와 복구\n```\n""",
                encoding="utf-8",
            )
            (root / "memory" / "log.md").write_text(
                "## [2026-06-04] task [primary:1] | 지난 업무 기록\n- 처리 완료\n",
                encoding="utf-8",
            )

            graph = build_flow.build(root)

            self.assertEqual([t["name"] for t in graph["primary_tasks"]], ["고객 문의 처리", "월간 리포트", "장애 대응"])
            titles = [e["title"] for e in graph["entries"]]
            self.assertIn("고객 문의 처리 · 문의 접수", titles)
            self.assertIn("월간 리포트 · 보고서 발행", titles)
            self.assertIn("장애 대응 · 요청/트리거 확인", titles)
            self.assertNotIn("지난 업무 기록", titles)
            self.assertEqual(graph["counts"]["primary"], 1)


if __name__ == "__main__":
    unittest.main()
