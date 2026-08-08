from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


INSTALL_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("AGENT_MODELING_ROOT", INSTALL_ROOT)).resolve()
RUN_ID = os.environ.get("AGENT_MODELING_RUN_ID", "").strip().lower()
if not re.fullmatch(r"[a-f0-9]{32}", RUN_ID):
    raise RuntimeError("AGENT_MODELING_RUN_ID 无效")

# This server exposes the parent registry through a file broker. Starting its
# own nested MATLAB/Origin MCP clients would recurse and is intentionally
# disabled; high-level MATLAB calls are forwarded to the parent process.
os.environ["AGENT_MCP"] = "0"
if str(INSTALL_ROOT) not in sys.path:
    sys.path.insert(0, str(INSTALL_ROOT))

from agent_tools import ToolRegistry  # noqa: E402
from tool_broker import call_file_tool_broker  # noqa: E402


BROKER_DIR = os.environ.get("AGENT_MODELING_BROKER_DIR", "").strip()
BROKER_TOKEN = os.environ.get("AGENT_MODELING_BROKER_TOKEN", "").strip()


def _env_enabled(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value not in {"0", "false", "no", "off"}


def _bounded_seconds(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(os.environ.get(name, str(default)))))
    except ValueError:
        return default


UNSANDBOXED_MATLAB_ENABLED = _env_enabled("AGENT_UNSANDBOXED_MATLAB")
MATLAB_TIMEOUT_SECONDS = _bounded_seconds("AGENT_MATLAB_TIMEOUT", 180, 1, 600)
BROKER_TIMEOUT_SECONDS = _bounded_seconds(
    "AGENT_MODELING_BROKER_TIMEOUT",
    MATLAB_TIMEOUT_SECONDS + 20,
    2,
    630,
)
registry = None if BROKER_DIR and BROKER_TOKEN else ToolRegistry(ROOT)
mcp = FastMCP(
    "Mathematical Modeling Specialist Tools",
    instructions=(
        "Use these deterministic tools for local contest sources, datasets, Python or MATLAB execution, "
        "optimization, figures, and report exports. Do not claim a numerical result was computed "
        "unless the corresponding execution tool completed successfully."
    ),
)


def execute(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "run_matlab" and not UNSANDBOXED_MATLAB_ENABLED:
        raise RuntimeError(
            "run_matlab 是非沙箱本机任意代码执行；仅可由操作员显式设置 "
            "AGENT_UNSANDBOXED_MATLAB=1 后启用"
        )
    if BROKER_DIR and BROKER_TOKEN:
        result = call_file_tool_broker(
            Path(BROKER_DIR),
            BROKER_TOKEN,
            name,
            arguments,
            timeout=BROKER_TIMEOUT_SECONDS,
            allow_unsandboxed_matlab=UNSANDBOXED_MATLAB_ENABLED,
        )
    else:
        if registry is None:
            raise RuntimeError("本地工具注册表未初始化")
        result = registry.execute(name, arguments, RUN_ID)
    result.setdefault("ok", True)
    return result


@mcp.tool()
def search_materials(query: str, limit: int = 5, extensions: list[str] | None = None) -> dict[str, Any]:
    """Search the indexed local modeling library and return page/sheet-grounded excerpts."""
    return execute("search_materials", {"query": query, "limit": limit, "extensions": extensions})


@mcp.tool()
def read_material(document_id: str, chunk_id: int | None = None, max_chars: int = 6000) -> dict[str, Any]:
    """Read a selected local source chunk before using detailed claims, formulas, or procedures."""
    return execute(
        "read_material",
        {"document_id": document_id, "chunk_id": chunk_id, "max_chars": max_chars},
    )


@mcp.tool()
def search_skills(query: str, limit: int = 3) -> dict[str, Any]:
    """Select relevant mathematical-modeling, statistics, optimization, plotting, or writing skills."""
    return execute("search_skills", {"query": query, "limit": limit})


@mcp.tool()
def read_skill(name: str) -> dict[str, Any]:
    """Read one approved specialist skill selected by search_skills."""
    return execute("read_skill", {"name": name})


@mcp.tool()
def read_skill_reference(name: str, relative_path: str, max_chars: int = 30000) -> dict[str, Any]:
    """Read a references/ file explicitly linked by an approved specialist skill."""
    return execute(
        "read_skill_reference",
        {"name": name, "relative_path": relative_path, "max_chars": max_chars},
    )


@mcp.tool()
def inspect_dataset(upload_id: str, sheet_name: str | int | None = None, sample_rows: int = 5) -> dict[str, Any]:
    """Inspect an uploaded CSV, TSV, XLSX, or JSON file before modeling."""
    return execute(
        "inspect_dataset",
        {"upload_id": upload_id, "sheet_name": sheet_name, "sample_rows": sample_rows},
    )


@mcp.tool()
def run_python(
    code: str,
    input_upload_ids: list[str] | None = None,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Run reproducible Python analysis in a restricted per-task workspace; write deliverables to outputs/."""
    return execute(
        "run_python",
        {
            "code": code,
            "input_upload_ids": input_upload_ids or [],
            "timeout_seconds": timeout_seconds,
        },
    )


@mcp.tool()
def matlab_status() -> dict[str, Any]:
    """Check whether the local MATLAB batch runtime and official MATLAB MCP are available."""
    return execute("matlab_status", {})


if UNSANDBOXED_MATLAB_ENABLED:
    @mcp.tool()
    def run_matlab(
        code: str,
        input_upload_ids: list[str] | None = None,
        timeout_seconds: int = MATLAB_TIMEOUT_SECONDS,
        filename: str = "matlab-analysis",
    ) -> dict[str, Any]:
        """Run non-sandboxed MATLAB code after explicit operator opt-in."""
        return execute(
            "run_matlab",
            {
                "code": code,
                "input_upload_ids": input_upload_ids or [],
                "timeout_seconds": timeout_seconds,
                "filename": filename,
            },
        )


@mcp.tool()
def solve_linear_program(
    objective: list[float],
    sense: str = "min",
    A_ub: list[list[float]] | None = None,
    b_ub: list[float] | None = None,
    A_eq: list[list[float]] | None = None,
    b_eq: list[float] | None = None,
    bounds: list[list[float | None]] | None = None,
) -> dict[str, Any]:
    """Solve a continuous linear program with SciPy HiGHS and return diagnostics."""
    return execute(
        "solve_linear_program",
        {
            "objective": objective,
            "sense": sense,
            "A_ub": A_ub,
            "b_ub": b_ub,
            "A_eq": A_eq,
            "b_eq": b_eq,
            "bounds": bounds,
        },
    )


@mcp.tool()
def create_plot_from_dataset(
    upload_id: str,
    chart_type: str,
    filename: str,
    sheet_name: str | int | None = None,
    x_column: str = "",
    y_columns: list[str] | None = None,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    formats: list[str] | None = None,
) -> dict[str, Any]:
    """Create a publication-ready plot from inspected uploaded dataset columns."""
    return execute(
        "create_plot_from_dataset",
        {
            "upload_id": upload_id,
            "sheet_name": sheet_name,
            "chart_type": chart_type,
            "x_column": x_column,
            "y_columns": y_columns or [],
            "title": title,
            "x_label": x_label,
            "y_label": y_label,
            "filename": filename,
            "formats": formats or ["png", "pdf", "svg"],
        },
    )


@mcp.tool()
def create_plot(
    chart_type: str,
    filename: str,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    series: list[dict[str, Any]] | None = None,
    matrix: list[list[float]] | None = None,
    x_ticks: list[str] | None = None,
    y_ticks: list[str] | None = None,
    panels: list[dict[str, Any]] | None = None,
    formats: list[str] | None = None,
    figsize: list[float] | None = None,
    dpi: int = 600,
    cmap: str = "viridis",
    center: float | None = None,
    annotate_heatmap: bool = False,
    panel_labels: bool = True,
    save_spec: bool = True,
) -> dict[str, Any]:
    """Create a publication-ready inline-data or multi-panel figure with vector exports and reproducibility spec."""
    return execute(
        "create_plot",
        {
            "chart_type": chart_type,
            "filename": filename,
            "title": title,
            "x_label": x_label,
            "y_label": y_label,
            "series": series or [],
            "matrix": matrix or [],
            "x_ticks": x_ticks or [],
            "y_ticks": y_ticks or [],
            "panels": panels or [],
            "formats": formats or ["png", "pdf", "svg"],
            "figsize": figsize or [],
            "dpi": dpi,
            "cmap": cmap,
            "center": center,
            "annotate_heatmap": annotate_heatmap,
            "panel_labels": panel_labels,
            "save_spec": save_spec,
        },
    )


@mcp.tool()
def create_matlab_plot(
    chart_type: str,
    filename: str,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    series: list[dict[str, Any]] | None = None,
    matrix: list[list[float]] | None = None,
    formats: list[str] | None = None,
    template: str = "",
) -> dict[str, Any]:
    """Create a structured MATLAB figure and retain PNG/PDF/SVG, FIG, and M artifacts."""
    return execute(
        "create_matlab_plot",
        {
            "chart_type": chart_type,
            "filename": filename,
            "title": title,
            "x_label": x_label,
            "y_label": y_label,
            "series": series or [],
            "matrix": matrix or [],
            "formats": formats or ["png", "pdf", "svg"],
            "template": template,
        },
    )


@mcp.tool()
def create_matlab_plot_from_dataset(
    upload_id: str,
    chart_type: str,
    filename: str,
    sheet_name: str | int | None = None,
    x_column: str = "",
    y_columns: list[str] | None = None,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    formats: list[str] | None = None,
    template: str = "",
) -> dict[str, Any]:
    """Create a structured MATLAB figure from inspected uploaded dataset columns."""
    return execute(
        "create_matlab_plot_from_dataset",
        {
            "upload_id": upload_id,
            "sheet_name": sheet_name,
            "chart_type": chart_type,
            "x_column": x_column,
            "y_columns": y_columns or [],
            "title": title,
            "x_label": x_label,
            "y_label": y_label,
            "filename": filename,
            "formats": formats or ["png", "pdf", "svg"],
            "template": template,
        },
    )


@mcp.tool()
def export_report(title: str, markdown: str, filename: str, formats: list[str] | None = None) -> dict[str, Any]:
    """Export a verified report to editable Markdown and DOCX artifacts."""
    return execute(
        "export_report",
        {
            "title": title,
            "markdown": markdown,
            "filename": filename,
            "formats": formats or ["md", "docx"],
        },
    )


if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    finally:
        if registry is not None:
            registry.mcp.close()
