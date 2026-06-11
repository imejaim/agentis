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
