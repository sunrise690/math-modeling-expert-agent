#!/usr/bin/env python3
"""Manage resumable, evidence-gated mathematical-modeling workflow state."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
STAGES = (
    "intake",
    "parse",
    "model",
    "prototype",
    "solve",
    "validate",
    "evidence",
    "write",
    "package",
    "complete",
)
TRANSITION_GATES = {
    ("intake", "parse"): "input_audit",
    ("parse", "model"): "problem_contract",
    ("model", "prototype"): "model_contract",
    ("prototype", "solve"): "prototype_run",
    ("solve", "validate"): "full_solution",
    ("validate", "evidence"): "validation",
    ("evidence", "write"): "claim_evidence",
    ("write", "package"): "paper_audit",
    ("package", "complete"): "package_rebuild",
}
GATE_STATUSES = ("PASS", "FAIL", "BLOCKED")
SKILL_ROOT = Path(__file__).resolve().parents[1]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_paths(project_root: str, *, create: bool = False) -> tuple[Path, Path]:
    project = Path(project_root).expanduser().resolve()
    if is_within(project, SKILL_ROOT) or is_within(SKILL_ROOT, project):
        raise ValueError("PROJECT_ROOT 不得与 Skill 目录重叠")
    if create:
        project.mkdir(parents=True, exist_ok=True)
    elif not project.is_dir():
        raise FileNotFoundError(f"PROJECT_ROOT 不存在: {project}")
    return project, project / ".modeling-agent" / "workflow-state.json"


def load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.is_file():
        raise FileNotFoundError(f"状态文件不存在: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("状态文件版本不受支持")
    if state.get("stage") not in STAGES:
        raise ValueError("状态文件 stage 无效")
    if not isinstance(state.get("gates"), dict) or not isinstance(state.get("history"), list):
        raise ValueError("状态文件结构无效")
    return state


def save_state(state_path: Path, state: dict[str, Any]) -> None:
    state["updatedAtUtc"] = now_utc()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(state_path)


def evidence_snapshot(project: Path, raw_paths: list[str]) -> list[dict[str, Any]]:
    if not raw_paths:
        raise ValueError("门禁至少需要一个项目内证据文件")
    snapshots: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_path in raw_paths:
        candidate = Path(raw_path)
        path = (project / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
        if not is_within(path, project) or not path.is_file():
            raise ValueError(f"证据必须是 PROJECT_ROOT 内的现有文件: {path}")
        relative = path.relative_to(project).as_posix()
        if relative in seen:
            continue
        seen.add(relative)
        snapshots.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return snapshots


def stale_evidence(project: Path, gate: dict[str, Any]) -> list[str]:
    stale: list[str] = []
    evidence = gate.get("evidence", [])
    if not isinstance(evidence, list) or not evidence:
        return ["<missing-evidence>"]
    for item in evidence:
        if not isinstance(item, dict):
            stale.append("<invalid-evidence>")
            continue
        path = (project / str(item.get("path", ""))).resolve()
        if (
            not is_within(path, project)
            or not path.is_file()
            or sha256_file(path) != item.get("sha256")
            or path.stat().st_size != item.get("bytes")
        ):
            stale.append(str(item.get("path", "")))
    return stale


def invalidate_stale(state: dict[str, Any], project: Path) -> list[dict[str, Any]]:
    stale_gates: list[tuple[str, dict[str, Any], list[str]]] = []
    for gate_name, gate in state["gates"].items():
        if gate.get("status") != "PASS":
            continue
        changed = stale_evidence(project, gate)
        if changed:
            stale_gates.append((gate_name, gate, changed))
    if not stale_gates:
        return []

    earliest_name, earliest_gate, _ = min(
        stale_gates,
        key=lambda item: STAGES.index(str(item[1].get("fromStage"))),
    )
    rollback_stage = str(earliest_gate["fromStage"])
    rollback_index = STAGES.index(rollback_stage)
    invalidated: list[dict[str, Any]] = []
    for gate_name, gate in list(state["gates"].items()):
        from_stage = str(gate.get("fromStage", ""))
        if from_stage in STAGES and STAGES.index(from_stage) >= rollback_index:
            invalidated.append(
                {
                    "gate": gate_name,
                    "changedEvidence": stale_evidence(project, gate),
                }
            )
            del state["gates"][gate_name]

    if STAGES.index(state["stage"]) > rollback_index:
        state["stage"] = rollback_stage
    state["nextAction"] = f"重新执行 {earliest_name} 门禁"
    state["history"].append(
        {
            "atUtc": now_utc(),
            "event": "evidence_invalidated",
            "triggerGate": earliest_name,
            "rollbackTo": rollback_stage,
            "invalidated": invalidated,
        }
    )
    return invalidated


def next_transition(stage: str) -> tuple[str, str] | None:
    index = STAGES.index(stage)
    if index == len(STAGES) - 1:
        return None
    target = STAGES[index + 1]
    return target, TRANSITION_GATES[(stage, target)]


def cmd_init(args: argparse.Namespace) -> int:
    project, state_path = project_paths(args.project_root, create=True)
    if state_path.exists():
        print(f"状态已存在，拒绝覆盖: {state_path}", file=sys.stderr)
        return 1
    timestamp = now_utc()
    state: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "stage": "intake",
        "competition": args.competition,
        "year": args.year,
        "problemId": args.problem_id,
        "createdAtUtc": timestamp,
        "updatedAtUtc": timestamp,
        "gates": {},
        "approvals": [],
        "history": [{"atUtc": timestamp, "event": "init", "stage": "intake"}],
        "nextAction": "完成题目、附件、模板和规则盘点",
    }
    save_state(state_path, state)
    print(state_path)
    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    project, state_path = project_paths(args.project_root)
    state = load_state(state_path)
    invalidated = invalidate_stale(state, project)
    transition = next_transition(state["stage"])
    if transition is None:
        raise ValueError("流程已经 complete")
    expected_target, expected_gate = transition
    if args.to != expected_target:
        raise ValueError(f"禁止跨阶段推进；当前只能进入 {expected_target}")
    if args.gate != expected_gate:
        raise ValueError(f"阶段 {state['stage']} -> {expected_target} 必须使用门禁 {expected_gate}")
    if (
        args.status == "PASS"
        and state["stage"] == "model"
        and expected_target == "prototype"
        and not args.user_approval.strip()
    ):
        raise ValueError("进入 prototype 前必须记录用户对模型方案的明确确认")

    evidence = evidence_snapshot(project, args.evidence)
    timestamp = now_utc()
    gate = {
        "status": args.status,
        "fromStage": state["stage"],
        "toStage": expected_target,
        "evidence": evidence,
        "recordedAtUtc": timestamp,
    }
    state["gates"][expected_gate] = gate
    event: dict[str, Any] = {
        "atUtc": timestamp,
        "event": "advance" if args.status == "PASS" else "gate_blocked",
        "from": state["stage"],
        "to": expected_target,
        "gate": expected_gate,
        "status": args.status,
    }
    if args.status == "PASS":
        if args.user_approval.strip():
            approval = {
                "atUtc": timestamp,
                "transition": "model->prototype",
                "detail": args.user_approval.strip(),
            }
            state["approvals"].append(approval)
            event["approval"] = approval["detail"]
        state["stage"] = expected_target
        state["nextAction"] = args.next_action or f"执行 {expected_target} 阶段"
    else:
        state["nextAction"] = args.next_action or f"修复 {expected_gate} 门禁"
    state["history"].append(event)
    save_state(state_path, state)
    print(
        json.dumps(
            {
                "stage": state["stage"],
                "gate": expected_gate,
                "status": args.status,
                "invalidated": invalidated,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if args.status == "PASS" else 2


def cmd_rollback(args: argparse.Namespace) -> int:
    project, state_path = project_paths(args.project_root)
    state = load_state(state_path)
    target_index = STAGES.index(args.to)
    current_index = STAGES.index(state["stage"])
    if target_index >= current_index:
        raise ValueError("rollback 目标必须早于当前阶段")
    invalidated = []
    for gate_name, gate in list(state["gates"].items()):
        from_stage = str(gate.get("fromStage", ""))
        if from_stage in STAGES and STAGES.index(from_stage) >= target_index:
            invalidated.append(gate_name)
            del state["gates"][gate_name]
    previous = state["stage"]
    state["stage"] = args.to
    state["nextAction"] = args.next_action or f"按回退原因修复 {args.to} 阶段"
    state["history"].append(
        {
            "atUtc": now_utc(),
            "event": "rollback",
            "from": previous,
            "to": args.to,
            "reason": args.reason.strip(),
            "invalidatedGates": invalidated,
        }
    )
    save_state(state_path, state)
    print(json.dumps({"stage": args.to, "invalidatedGates": invalidated}, ensure_ascii=False, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    project, state_path = project_paths(args.project_root)
    state = load_state(state_path)
    invalidated = invalidate_stale(state, project)
    if invalidated:
        save_state(state_path, state)
    transition = next_transition(state["stage"])
    report = {
        "stage": state["stage"],
        "nextStage": transition[0] if transition else None,
        "requiredGate": transition[1] if transition else None,
        "nextAction": state.get("nextAction"),
        "gates": {name: gate.get("status") for name, gate in state["gates"].items()},
        "invalidated": invalidated,
        "complete": state["stage"] == "complete",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if invalidated else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="管理数学建模任务的可恢复阶段与证据门禁")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="初始化项目状态；拒绝覆盖已有状态")
    init.add_argument("--project-root", required=True)
    init.add_argument("--competition")
    init.add_argument("--year")
    init.add_argument("--problem-id")
    init.set_defaults(func=cmd_init)

    advance = commands.add_parser("advance", help="通过当前阶段门禁并推进一个相邻阶段")
    advance.add_argument("--project-root", required=True)
    advance.add_argument("--to", choices=STAGES, required=True)
    advance.add_argument("--gate", required=True)
    advance.add_argument("--status", choices=GATE_STATUSES, required=True)
    advance.add_argument("--evidence", action="append", default=[])
    advance.add_argument("--user-approval", default="")
    advance.add_argument("--next-action")
    advance.set_defaults(func=cmd_advance)

    rollback = commands.add_parser("rollback", help="显式回退并使下游门禁失效")
    rollback.add_argument("--project-root", required=True)
    rollback.add_argument("--to", choices=STAGES, required=True)
    rollback.add_argument("--reason", required=True)
    rollback.add_argument("--next-action")
    rollback.set_defaults(func=cmd_rollback)

    status = commands.add_parser("status", help="检查状态、证据漂移和下一门禁")
    status.add_argument("--project-root", required=True)
    status.set_defaults(func=cmd_status)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
