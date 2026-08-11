from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "cumcm-expert-agent"
    / "scripts"
    / "workflow_state.py"
)
SPEC = importlib.util.spec_from_file_location("workflow_state", SCRIPT)
assert SPEC and SPEC.loader
workflow_state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow_state)


def state_path(project: Path) -> Path:
    return project / ".modeling-agent" / "workflow-state.json"


def write_evidence(project: Path, name: str, content: str = "ok") -> Path:
    path = project / "evidence" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class WorkflowStateTests(unittest.TestCase):
    def init_project(self, project: Path) -> None:
        result = workflow_state.cmd_init(
            Namespace(project_root=str(project), competition="CUMCM", year="2026", problem_id="A")
        )
        self.assertEqual(result, 0)

    def advance(
        self,
        project: Path,
        *,
        target: str,
        gate: str,
        evidence: Path,
        status: str = "PASS",
        approval: str = "",
    ) -> int:
        return workflow_state.cmd_advance(
            Namespace(
                project_root=str(project),
                to=target,
                gate=gate,
                status=status,
                evidence=[str(evidence)],
                user_approval=approval,
                next_action=None,
            )
        )

    def test_init_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            self.init_project(project)
            result = workflow_state.cmd_init(
                Namespace(project_root=str(project), competition=None, year=None, problem_id=None)
            )
            self.assertEqual(result, 1)

    def test_cannot_skip_stage_or_use_wrong_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            self.init_project(project)
            evidence = write_evidence(project, "input.json")
            with self.assertRaisesRegex(ValueError, "禁止跨阶段"):
                self.advance(project, target="model", gate="problem_contract", evidence=evidence)
            with self.assertRaisesRegex(ValueError, "必须使用门禁"):
                self.advance(project, target="parse", gate="problem_contract", evidence=evidence)

    def test_failed_gate_does_not_advance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            self.init_project(project)
            evidence = write_evidence(project, "input-fail.json")
            result = self.advance(
                project,
                target="parse",
                gate="input_audit",
                evidence=evidence,
                status="FAIL",
            )
            self.assertEqual(result, 2)
            state = json.loads(state_path(project).read_text(encoding="utf-8"))
            self.assertEqual(state["stage"], "intake")

    def test_model_to_prototype_requires_real_approval_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            self.init_project(project)
            first = write_evidence(project, "input.json")
            second = write_evidence(project, "problem.json")
            third = write_evidence(project, "model.json")
            self.advance(project, target="parse", gate="input_audit", evidence=first)
            self.advance(project, target="model", gate="problem_contract", evidence=second)
            with self.assertRaisesRegex(ValueError, "用户.*确认"):
                self.advance(project, target="prototype", gate="model_contract", evidence=third)
            self.advance(
                project,
                target="prototype",
                gate="model_contract",
                evidence=third,
                approval="用户明确确认进入编程",
            )
            state = json.loads(state_path(project).read_text(encoding="utf-8"))
            self.assertEqual(state["stage"], "prototype")
            self.assertEqual(len(state["approvals"]), 1)

    def test_failed_model_gate_can_be_recorded_before_user_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            self.init_project(project)
            first = write_evidence(project, "input.json")
            second = write_evidence(project, "problem.json")
            third = write_evidence(project, "model-fail.json")
            self.advance(project, target="parse", gate="input_audit", evidence=first)
            self.advance(project, target="model", gate="problem_contract", evidence=second)
            result = self.advance(
                project,
                target="prototype",
                gate="model_contract",
                evidence=third,
                status="FAIL",
            )
            self.assertEqual(result, 2)
            state = json.loads(state_path(project).read_text(encoding="utf-8"))
            self.assertEqual(state["stage"], "model")
            self.assertEqual(state["approvals"], [])

    def test_evidence_must_stay_inside_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as outside_dir:
            project = Path(temp_dir)
            self.init_project(project)
            outside = Path(outside_dir) / "outside.json"
            outside.write_text("outside", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PROJECT_ROOT"):
                self.advance(project, target="parse", gate="input_audit", evidence=outside)

    def test_evidence_change_invalidates_gate_and_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            self.init_project(project)
            first = write_evidence(project, "input.json")
            second = write_evidence(project, "problem.json")
            self.advance(project, target="parse", gate="input_audit", evidence=first)
            self.advance(project, target="model", gate="problem_contract", evidence=second)
            first.write_text("changed", encoding="utf-8")
            result = workflow_state.cmd_status(Namespace(project_root=str(project)))
            self.assertEqual(result, 2)
            state = json.loads(state_path(project).read_text(encoding="utf-8"))
            self.assertEqual(state["stage"], "intake")
            self.assertEqual(state["gates"], {})
            self.assertEqual(state["nextAction"], "重新执行 input_audit 门禁")
            self.assertEqual(state["history"][-1]["event"], "evidence_invalidated")

    def test_manual_rollback_keeps_files_and_invalidates_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            self.init_project(project)
            first = write_evidence(project, "input.json")
            second = write_evidence(project, "problem.json")
            self.advance(project, target="parse", gate="input_audit", evidence=first)
            self.advance(project, target="model", gate="problem_contract", evidence=second)
            result = workflow_state.cmd_rollback(
                Namespace(project_root=str(project), to="parse", reason="修正题意", next_action=None)
            )
            self.assertEqual(result, 0)
            state = json.loads(state_path(project).read_text(encoding="utf-8"))
            self.assertEqual(state["stage"], "parse")
            self.assertIn("input_audit", state["gates"])
            self.assertNotIn("problem_contract", state["gates"])
            self.assertTrue(second.exists())


if __name__ == "__main__":
    unittest.main()
