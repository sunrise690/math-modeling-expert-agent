from __future__ import annotations

import importlib.metadata
import os
import re
import sys
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    "Origin Plotting MCP Server",
    instructions="Use OriginLab originpro to create editable, publication-ready scientific figures on Windows.",
)

ChartType = Literal["line", "scatter", "bar", "heatmap"]
ExportFormat = Literal["png", "pdf", "svg"]
PALETTE = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000")


def _installed_origin() -> list[dict[str, str]]:
    if os.name != "nt":
        return []
    import winreg

    roots = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    records: list[dict[str, str]] = []
    for hive, key_path in roots:
        try:
            parent = winreg.OpenKey(hive, key_path)
        except OSError:
            continue
        with parent:
            for index in range(winreg.QueryInfoKey(parent)[0]):
                try:
                    child_name = winreg.EnumKey(parent, index)
                    with winreg.OpenKey(parent, child_name) as child:
                        name = str(winreg.QueryValueEx(child, "DisplayName")[0])
                        if not re.search(r"\bOrigin(?:Pro)?\b|OriginLab", name, re.IGNORECASE):
                            continue
                        try:
                            version = str(winreg.QueryValueEx(child, "DisplayVersion")[0])
                        except OSError:
                            version = ""
                        try:
                            location = str(winreg.QueryValueEx(child, "InstallLocation")[0])
                        except OSError:
                            location = ""
                        records.append({"name": name, "version": version, "location": location})
                except OSError:
                    continue
    unique = {(item["name"], item["version"], item["location"]): item for item in records}
    return list(unique.values())


@mcp.tool()
def origin_status() -> dict[str, Any]:
    """Detect the Origin installation and the official OriginLab originpro Python package without launching Origin."""
    try:
        package_version = importlib.metadata.version("originpro")
        package_installed = True
    except importlib.metadata.PackageNotFoundError:
        package_version = ""
        package_installed = False
    installations = _installed_origin()
    return {
        "available": os.name == "nt" and package_installed and bool(installations),
        "platform": sys.platform,
        "originproInstalled": package_installed,
        "originproVersion": package_version,
        "installations": installations,
        "reason": "" if installations else "未检测到 Origin 2021 或更高版本的本机安装与许可证环境",
    }


@mcp.tool()
def origin_create_plot(
    chart_type: ChartType,
    filename: str,
    output_dir: str,
    series: list[dict[str, Any]] | None = None,
    matrix: list[list[float]] | None = None,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    formats: list[ExportFormat] | None = None,
    template: str = "",
    palette: str = "Viridis.pal",
    visible: bool = False,
    save_project: bool = True,
) -> dict[str, Any]:
    """Create a professional Origin graph and export raster/vector figures plus an editable OPJU project."""
    status = origin_status()
    if not status["available"]:
        raise RuntimeError(status["reason"])
    try:
        import numpy as np
        import originpro as op
    except ImportError as error:
        raise RuntimeError("originpro 或 NumPy 未安装") from error

    target_dir = Path(output_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]", "_", Path(filename).stem).strip("._")
    if not safe_stem:
        raise ValueError("filename 无效")
    selected_formats = list(dict.fromkeys(formats or ["png", "pdf"]))
    if any(item not in {"png", "pdf", "svg"} for item in selected_formats):
        raise ValueError("formats 仅支持 png、pdf、svg")

    created: list[str] = []
    try:
        if op.oext:
            op.set_show(visible)
        op.new(asksave=False)
        if chart_type == "heatmap":
            values = np.asarray(matrix, dtype=float)
            if values.ndim != 2 or not values.size or values.shape[0] > 2000 or values.shape[1] > 2000:
                raise ValueError("heatmap matrix 必须是最大 2000x2000 的非空二维数值矩阵")
            sheet = op.new_sheet(type="m", lname="Heatmap Data", hidden=not visible)
            sheet.from_np(values)
            page = op.new_graph(lname=title or safe_stem, template=template or "heatmap", hidden=not visible)
            layer = page[0]
            plot = layer.add_plot(sheet, colz=0)
            try:
                plot.colormap = palette
            except Exception:
                pass
            layer.rescale("z")
        else:
            if not series or len(series) > 20:
                raise ValueError("series 必须包含 1 至 20 组数据")
            sheet = op.new_sheet(type="w", lname="Plot Data", hidden=not visible)
            page = op.new_graph(
                lname=title or safe_stem,
                template=template or {"line": "line", "scatter": "scatter", "bar": "column"}[chart_type],
                hidden=not visible,
            )
            layer = page[0]
            plot_type = {"line": "l", "scatter": "s", "bar": "c"}[chart_type]
            for index, item in enumerate(series):
                if not isinstance(item, dict):
                    raise ValueError("series 项必须是对象")
                y_values = list(item.get("y") or item.get("values") or [])
                x_values = list(item.get("x") or range(1, len(y_values) + 1))
                if not y_values or len(x_values) != len(y_values) or len(y_values) > 200_000:
                    raise ValueError(f"series[{index}] 的 x/y 长度无效")
                x_col = index * 2
                y_col = x_col + 1
                sheet.from_list(x_col, x_values, lname=x_label or "X", axis="X")
                sheet.from_list(y_col, y_values, lname=str(item.get("name") or f"Series {index + 1}"), axis="Y")
                plot = layer.add_plot(sheet, coly=y_col, colx=x_col, type=plot_type)
                plot.color = str(item.get("color") or PALETTE[index % len(PALETTE)])
            if len(series) > 1:
                layer.group(True)
            layer.rescale()

        if x_label:
            layer.axis("x").title = x_label
        if y_label:
            layer.axis("y").title = y_label
        layer.set_int("x.showgrids", 1)
        layer.set_int("y.showgrids", 1)
        layer.set_int("x.opposite", 1)
        layer.set_int("y.opposite", 1)
        try:
            legend = layer.label("Legend")
            legend.set_int("showframe", 0)
        except Exception:
            pass
        page.set_int("aa", 1)
        op.wait()

        for file_format in selected_formats:
            target = target_dir / f"{safe_stem}.{file_format}"
            generated = page.save_fig(
                str(target),
                type=file_format,
                replace=True,
                width=1800 if file_format == "png" else 0,
                ratio=100,
            )
            generated_path = Path(generated or target)
            if generated_path.is_file():
                created.append(str(generated_path.resolve()))
        if save_project:
            project = target_dir / f"{safe_stem}.opju"
            op.save(str(project))
            if project.is_file():
                created.append(str(project.resolve()))
        if not created:
            raise RuntimeError("Origin 未生成任何图形产物")
        return {
            "chartType": chart_type,
            "artifacts": created,
            "editableProject": next((item for item in created if item.lower().endswith(".opju")), ""),
            "visible": visible,
        }
    finally:
        try:
            if op.oext:
                op.exit()
        except Exception:
            pass


if __name__ == "__main__":
    mcp.run(transport="stdio")
