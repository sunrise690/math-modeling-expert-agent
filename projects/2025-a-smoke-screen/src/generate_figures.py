from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Any

from run_identity import RUN_ID


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "figures"
MANIFEST_PATH = FIGURES / "figure_manifest.json"
MATLAB_SCRIPT_DIR = ROOT / "src" / "matlab"

FIGURE_STEMS = (
    "modeling_workflow",
    "finite_sightline_geometry",
    "q1_occlusion_intervals",
    "q2_response_surface",
    "q2_multiseed_stability",
    "q3_interval_union",
    "q4_temporal_synergy",
    "search_quality_diagnostics",
    "q5_xy_strategy",
    "q5_coverage_gantt",
    "q5_per_missile_robustness",
    "criterion_sensitivity",
    "time_step_convergence",
    "q3_q4_multiseed_stability",
)
SUPPORT_FIGURE_STEMS = frozenset(
    {
        "q2_multiseed_stability",
        "search_quality_diagnostics",
        "q5_per_missile_robustness",
        "criterion_sensitivity",
        "q3_q4_multiseed_stability",
    }
)
PAPER_FIGURE_STEMS = frozenset(FIGURE_STEMS) - SUPPORT_FIGURE_STEMS
MATLAB_SCRIPTS = (
    "render_q1_event.m",
    "render_q3_event.m",
    "render_q4_event.m",
    "render_core_figures.m",
    "render_q5_figures.m",
    "render_cross_audits.m",
)
VALIDATION_INPUTS = (
    "q1_q2_independent.json",
    "q2_multiseed.json",
    "q3_q4_multiseed.json",
    "q3_q5_independent.json",
)
TRUE_VALUES = {"1", "true", "yes", "on"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def figure_files(stem: str) -> list[str]:
    return [f"figures/{stem}.{extension}" for extension in ("png", "pdf", "svg")]


def expected_artifacts() -> list[Path]:
    return [ROOT / relative for stem in FIGURE_STEMS for relative in figure_files(stem)]


def _normalize_svg_whitespace(paths: list[Path]) -> None:
    """Remove renderer-only trailing spaces without changing SVG geometry."""

    for path in paths:
        if path.suffix.lower() != ".svg" or not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        normalized = "\n".join(line.rstrip() for line in source.splitlines())
        if source.endswith(("\n", "\r")):
            normalized += "\n"
        if normalized != source:
            path.write_text(normalized, encoding="utf-8", newline="\n")


def _sanitize_matlab_stdout(output: str) -> str:
    """Keep numeric diagnostics while excluding machine-local paths."""

    safe_lines = [
        line.rstrip()
        for line in output.splitlines()
        if ":\\" not in line and ":/" not in line
    ]
    return "\n".join(line for line in safe_lines if line).strip()


def _required_files(paths: list[Path] | tuple[Path, ...], *, label: str) -> None:
    missing = [
        path.relative_to(ROOT).as_posix()
        for path in paths
        if not path.is_file() or path.stat().st_size == 0
    ]
    if missing:
        raise RuntimeError(f"缺少{label}：" + ", ".join(missing))


def _load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        raise RuntimeError(
            "缺少 figures/figure_manifest.json；首次建立正式图件时必须使用 "
            "CUMCM_FORCE_MATLAB_FIGURES=1 运行完整 MATLAB 重绘"
        )
    try:
        loaded = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"无法读取图件清单：{error}") from error
    if not isinstance(loaded, dict):
        raise RuntimeError("图件清单顶层必须是 JSON 对象")
    return loaded


def _dependency_provenance() -> dict[str, Any]:
    scripts = [MATLAB_SCRIPT_DIR / name for name in MATLAB_SCRIPTS]
    inputs = [ROOT / "validation" / name for name in VALIDATION_INPUTS]
    _required_files(scripts, label=" MATLAB 绘图脚本")
    _required_files(inputs, label=" MATLAB 绘图输入")
    return {
        "schema_version": 1,
        "sources_sha256": {
            path.relative_to(ROOT).as_posix(): sha256(path) for path in scripts
        },
        "inputs_sha256": {
            path.relative_to(ROOT).as_posix(): sha256(path) for path in inputs
        },
    }


def _validate_reusable_manifest(manifest: dict[str, Any]) -> None:
    """Prove that all 42 checked-in artifacts are one coherent MATLAB set."""
    records = manifest.get("figures")
    if not isinstance(records, list):
        raise RuntimeError("图件清单缺少 figures 列表")

    expected_by_id = {
        f"F{index}": figure_files(stem)
        for index, stem in enumerate(FIGURE_STEMS, start=1)
    }
    expected_role_by_id = {
        f"F{index}": "support" if stem in SUPPORT_FIGURE_STEMS else "paper"
        for index, stem in enumerate(FIGURE_STEMS, start=1)
    }
    records_by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("图件清单包含非对象记录")
        figure_id = str(record.get("id", ""))
        if figure_id in records_by_id:
            raise RuntimeError(f"图件清单存在重复 ID：{figure_id}")
        records_by_id[figure_id] = record
    if set(records_by_id) != set(expected_by_id):
        raise RuntimeError("图件清单必须且只能登记 F1–F14")

    verified_paths: set[str] = set()
    problems: list[str] = []
    for figure_id, expected_files in expected_by_id.items():
        record = records_by_id[figure_id]
        if record.get("role") != expected_role_by_id[figure_id]:
            problems.append(f"{figure_id}:role")
        if not str(record.get("renderer", "")).startswith("MATLAB "):
            problems.append(f"{figure_id}:renderer")
        files = record.get("files")
        if files != expected_files:
            problems.append(f"{figure_id}:files")
            continue
        recorded_hashes = record.get("sha256")
        if not isinstance(recorded_hashes, dict):
            problems.append(f"{figure_id}:sha256")
            continue
        for relative_path in expected_files:
            if relative_path in verified_paths:
                problems.append(f"{figure_id}:duplicate:{relative_path}")
                continue
            verified_paths.add(relative_path)
            artifact = ROOT / relative_path
            if not artifact.is_file() or artifact.stat().st_size == 0:
                problems.append(f"{figure_id}:missing:{relative_path}")
                continue
            expected_hash = str(recorded_hashes.get(relative_path, "")).lower()
            if len(expected_hash) != 64 or sha256(artifact) != expected_hash:
                problems.append(f"{figure_id}:hash:{relative_path}")

    expected_paths = {
        relative for paths in expected_by_id.values() for relative in paths
    }
    if verified_paths != expected_paths:
        problems.append("manifest:artifact-set")
    if problems:
        raise RuntimeError(
            "现有 MATLAB 图件未通过整批复用验证，拒绝重新背书："
            + ", ".join(problems)
            + "。请设置 CUMCM_FORCE_MATLAB_FIGURES=1 完整重绘。"
        )


def _validate_dependency_provenance(
    manifest: dict[str, Any], current: dict[str, Any]
) -> None:
    """Require an exact source/input binding before reusing checked-in figures."""
    if "matlab_provenance" not in manifest:
        raise RuntimeError(
            "图件清单缺少 MATLAB 脚本与验证输入的依赖哈希，拒绝为既有图件重新背书。"
            "请通过 --recompute，或设置 CUMCM_FORCE_MATLAB_FIGURES=1，"
            "完整执行六个 MATLAB 脚本。"
        )
    recorded = manifest.get("matlab_provenance")
    if recorded != current:
        raise RuntimeError(
            "MATLAB 绘图脚本或验证 JSON 已变化，旧图件不得复用。"
            "请通过 --recompute，或设置 CUMCM_FORCE_MATLAB_FIGURES=1，"
            "完整执行六个 MATLAB 脚本。"
        )


def find_matlab_executable() -> Path | None:
    candidates: list[Path] = []
    configured = os.environ.get("MATLAB_ROOT", "").strip()
    if configured:
        configured_path = Path(configured).expanduser()
        candidates.extend(
            [
                configured_path
                if configured_path.is_file()
                else configured_path / "bin" / "matlab.exe",
                configured_path / "bin" / "matlab",
            ]
        )
    discovered = shutil.which("matlab")
    if discovered:
        candidates.append(Path(discovered))
    if os.name == "nt":
        candidates.append(Path(r"D:\matlab\bin\matlab.exe"))
        program_files = os.environ.get("ProgramFiles", "").strip()
        if program_files:
            candidates.extend(
                sorted(
                    (Path(program_files) / "MATLAB").glob("R*/bin/matlab.exe"),
                    reverse=True,
                )
            )
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file():
            return resolved
    return None


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
                shell=False,
            )
            if result.returncode == 0 and process.poll() is not None:
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except OSError:
            pass
    try:
        process.kill()
    except OSError:
        pass


def run_matlab_batch(
    executable: Path,
    batch_code: str,
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    # The render scripts already set all figures invisible.  On Windows,
    # combining ``-noFigureWindows`` with SVG/PDF export can leave MATLAB
    # idle without producing an artifact, so use the supported batch mode
    # alone and keep the explicit per-script timeout below.
    command = [str(executable), "-batch", batch_code]
    creation_flags = 0
    start_new_session = False
    if os.name == "nt":
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        start_new_session = True
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        creationflags=creation_flags,
        start_new_session=start_new_session,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as error:
        terminate_process_tree(process)
        try:
            tail_stdout, tail_stderr = process.communicate(timeout=20)
        except subprocess.TimeoutExpired as cleanup_error:
            try:
                process.kill()
            except OSError:
                pass
            try:
                tail_stdout, tail_stderr = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                tail_stdout = cleanup_error.stdout or ""
                tail_stderr = cleanup_error.stderr or ""
        stdout = (error.stdout or "") + (tail_stdout or "")
        stderr = (error.stderr or "") + (tail_stderr or "")
        raise RuntimeError(
            f"MATLAB 批处理超过 {timeout_seconds} 秒，已终止整棵进程树："
            f"{(stderr or stdout or '无诊断')[-2000:]}"
        ) from error
    return subprocess.CompletedProcess(
        args=command,
        returncode=process.returncode if process.returncode is not None else -1,
        stdout=stdout,
        stderr=stderr,
    )


def _matlab_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in list(environment):
        upper = name.upper()
        if (
            upper.endswith("_API_KEY")
            or "PASSWORD" in upper
            or "SECRET" in upper
            or "TOKEN" in upper
        ):
            environment.pop(name, None)
    return environment


def _render_all_with_matlab() -> dict[str, Any]:
    executable = find_matlab_executable()
    if executable is None:
        raise RuntimeError("MATLAB 不可用，无法执行强制整批重绘")

    expected = expected_artifacts()
    previous = {
        path: (path.stat().st_mtime_ns, sha256(path)) if path.is_file() else None
        for path in expected
    }
    script_dir_literal = str(MATLAB_SCRIPT_DIR).replace("'", "''")
    script_runs: list[dict[str, Any]] = []
    stdout_parts: list[str] = []
    for script_name in MATLAB_SCRIPTS:
        function_name = Path(script_name).stem
        completed = run_matlab_batch(
            executable,
            "set(groot,'defaultFigureVisible','off'); "
            f"addpath('{script_dir_literal}'); {function_name};",
            cwd=ROOT,
            environment=_matlab_environment(),
            timeout_seconds=900,
        )
        safe_stdout = _sanitize_matlab_stdout(completed.stdout)
        stdout_parts.append(safe_stdout)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "MATLAB 未返回诊断")[-3000:]
            raise RuntimeError(f"MATLAB 正式图生成失败（{script_name}）：{detail}")
        script_runs.append(
            {
                "script": f"src/matlab/{script_name}",
                "returncode": completed.returncode,
                "stdout_tail": safe_stdout[-500:],
            }
        )

    _required_files(expected, label=" MATLAB 正式图件")
    _normalize_svg_whitespace(expected)
    stale: list[str] = []
    for path in expected:
        before = previous[path]
        if before is None:
            continue
        old_mtime, old_hash = before
        if path.stat().st_mtime_ns <= old_mtime and sha256(path) == old_hash:
            stale.append(path.name)
    if stale:
        raise RuntimeError(
            "本轮 MATLAB 强制重绘未刷新全部正式图件：" + ", ".join(stale)
        )
    return {
        "executed": True,
        "runtime": str(executable),
        "scripts": script_runs,
        "stdout_tail": "\n".join(stdout_parts)[-1800:],
    }


def _reuse_checked_in_artifacts(
    manifest: dict[str, Any], provenance: dict[str, Any]
) -> dict[str, Any]:
    _validate_reusable_manifest(manifest)
    _validate_dependency_provenance(manifest, provenance)
    executable = find_matlab_executable()
    return {
        "executed": False,
        "runtime": str(executable) if executable else "checked-in MATLAB artifacts",
        "reason": "已通过清单哈希、MATLAB renderer 和依赖哈希校验复用 42 个正式产物",
        "sources": [f"src/matlab/{name}" for name in MATLAB_SCRIPTS],
    }


def _updated_manifest(
    template: dict[str, Any],
    matlab_render: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    manifest = dict(template)
    manifest["schema_version"] = max(4, int(manifest.get("schema_version", 0)))
    manifest["run_id"] = RUN_ID
    manifest["generated_by"] = (
        "src/generate_figures.py orchestrating six src/matlab/render_*.m figure scripts"
    )
    manifest["matlab_render"] = matlab_render
    manifest["matlab_provenance"] = provenance
    manifest["paper_figure_count"] = len(PAPER_FIGURE_STEMS)
    manifest["support_figure_count"] = len(SUPPORT_FIGURE_STEMS)

    records = manifest.get("figures")
    if not isinstance(records, list):
        raise RuntimeError("图件清单缺少 figures 列表")
    expected_by_id = {
        f"F{index}": (stem, figure_files(stem))
        for index, stem in enumerate(FIGURE_STEMS, start=1)
    }
    for record in records:
        figure_id = str(record.get("id", ""))
        expected = expected_by_id.get(figure_id)
        if expected is None:
            raise RuntimeError(f"图件清单包含未知 ID：{figure_id}")
        stem, files = expected
        if not str(record.get("renderer", "")).startswith("MATLAB "):
            record["renderer"] = "MATLAB R2026a"
        record["role"] = "support" if stem in SUPPORT_FIGURE_STEMS else "paper"
        record["files"] = files
        record["sha256"] = {
            relative_path: sha256(ROOT / relative_path) for relative_path in files
        }
    return manifest


def main() -> None:
    template = _load_manifest()
    provenance = _dependency_provenance()
    force_render = os.environ.get("CUMCM_FORCE_MATLAB_FIGURES", "").strip().lower() in TRUE_VALUES
    if force_render:
        matlab_render = _render_all_with_matlab()
    else:
        matlab_render = _reuse_checked_in_artifacts(template, provenance)

    manifest = _updated_manifest(template, matlab_render, provenance)
    _validate_reusable_manifest(manifest)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    artifacts = {
        f"F{index}": figure_files(stem)
        for index, stem in enumerate(FIGURE_STEMS, start=1)
    }
    print(json.dumps({"ok": True, "artifacts": artifacts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
