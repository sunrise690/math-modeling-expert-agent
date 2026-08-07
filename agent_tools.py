from __future__ import annotations

import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from knowledge_base import KnowledgeBase, KnowledgeError, SUPPORTED_MATERIAL_EXTENSIONS
from mcp_bridge import MCPBridgeError, MCPServerConfig, MCPToolManager


TOOLKIT_ROOT = Path.home() / ".codex/skills/math-modeling-toolkit"
SKILL_ROOT = Path.home() / ".codex/skills"
SOURCE_ROOT = Path(__file__).resolve().parent
ALLOWED_DATA_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".json"}
MCP_ARTIFACT_EXTENSIONS = {".csv", ".fig", ".json", ".m", ".mat", ".opju", ".pdf", ".png", ".svg", ".xlsx"}
PYTHON_ARTIFACT_EXTENSIONS = {
    ".csv",
    ".docx",
    ".html",
    ".json",
    ".mat",
    ".md",
    ".npy",
    ".npz",
    ".pdf",
    ".png",
    ".svg",
    ".tex",
    ".txt",
    ".xlsx",
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_DATA_ROWS = 200_000
MAX_PYTHON_CODE_CHARS = 100_000
MAX_PYTHON_OUTPUT_CHARS = 32_000
MAX_PYTHON_ARTIFACT_BYTES = 100 * 1024 * 1024
AVAILABLE_SKILLS = (
    "cumcm-expert-agent",
    "math-modeling-toolkit",
    "math-modeling-solver",
    "cumcm-modeling",
    "math-modeling-paper",
    "statistical-analysis",
    "exploratory-data-analysis",
    "statsmodels",
    "sympy",
    "networkx",
    "pymoo",
    "simpy",
    "scikit-learn",
    "matplotlib",
    "seaborn",
    "scientific-visualization",
    "scientific-writing",
    "citation-management",
)
SKILL_ALIASES = {
    "专家": ("cumcm-expert-agent",),
    "全流程": ("cumcm-expert-agent", "cumcm-modeling"),
    "验证": ("cumcm-expert-agent", "statistical-analysis"),
    "鲁棒": ("cumcm-expert-agent", "statistical-analysis"),
    "拆题": ("cumcm-expert-agent", "math-modeling-solver"),
    "建模": ("cumcm-expert-agent", "math-modeling-solver", "cumcm-modeling"),
    "整题": ("cumcm-expert-agent", "cumcm-modeling"),
    "一等奖": ("cumcm-expert-agent",),
    "优秀论文": ("cumcm-expert-agent",),
    "获奖论文": ("cumcm-expert-agent",),
    "论文复盘": ("cumcm-expert-agent",),
    "论文": ("math-modeling-paper", "scientific-writing"),
    "写作": ("scientific-writing", "math-modeling-paper"),
    "引用": ("citation-management",),
    "统计": ("statistical-analysis", "statsmodels"),
    "回归": ("statsmodels", "scikit-learn"),
    "预测": ("scikit-learn", "statsmodels"),
    "分类": ("scikit-learn",),
    "聚类": ("scikit-learn",),
    "符号": ("sympy",),
    "公式": ("sympy",),
    "图论": ("networkx",),
    "路径": ("networkx",),
    "网络": ("networkx",),
    "多目标": ("pymoo",),
    "优化": ("pymoo", "math-modeling-solver"),
    "仿真": ("simpy",),
    "排队": ("simpy",),
    "轨迹": ("cumcm-expert-agent", "math-modeling-solver"),
    "几何": ("cumcm-expert-agent", "math-modeling-solver"),
    "遮蔽": ("cumcm-expert-agent",),
    "碰撞": ("cumcm-expert-agent",),
    "连续事件": ("cumcm-expert-agent",),
    "绘图": ("scientific-visualization", "matplotlib", "seaborn"),
    "图表": ("scientific-visualization", "matplotlib", "seaborn"),
    "可视化": ("scientific-visualization", "matplotlib", "seaborn"),
    "eda": ("exploratory-data-analysis",),
}


class ToolError(RuntimeError):
    pass


class ToolRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.artifact_root = root / ".agent-data/artifacts"
        self.upload_root = root / ".agent-data/uploads"
        self.mcp_workspace_root = root / ".agent-data/mcp-workspaces"
        self.python_workspace_root = root / ".agent-data/python-workspaces"
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self.upload_root.mkdir(parents=True, exist_ok=True)
        self.mcp_workspace_root.mkdir(parents=True, exist_ok=True)
        self.python_workspace_root.mkdir(parents=True, exist_ok=True)
        self._env_values = self._read_local_env()
        self.knowledge = KnowledgeBase(root / ".agent-data/knowledge.db", self._knowledge_roots())
        self.mcp = MCPToolManager(self._mcp_configs(), root / ".agent-data/mcp/logs")
        self._mcp_tool_names: set[str] = set()

    def definitions(self) -> list[dict[str, Any]]:
        definitions = self._local_definitions()
        definitions.extend(self._mcp_plot_definitions())
        mcp_definitions = self.mcp.definitions()
        self._mcp_tool_names = {
            str(item.get("function", {}).get("name", ""))
            for item in mcp_definitions
            if isinstance(item, dict)
        }
        definitions.extend(mcp_definitions)
        return definitions

    def _local_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_skills",
                    "description": "Search installed mathematical modeling, analysis, visualization, and writing skills. Use before choosing a specialized workflow.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Problem type or capability to search for."},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 6, "default": 3},
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_materials",
                    "description": "Search the indexed local mathematical-modeling reference library. Returns source file, page or sheet location, and an exact excerpt suitable for grounded citation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Method, topic, contest problem, or phrase to find."},
                            "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                            "extensions": {
                                "type": "array",
                                "items": {"type": "string", "enum": sorted(SUPPORTED_MATERIAL_EXTENSIONS)},
                                "maxItems": len(SUPPORTED_MATERIAL_EXTENSIONS),
                            },
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_material",
                    "description": "Read a source or a specific source chunk returned by search_materials. Use it before relying on detailed claims, formulas, or procedures from that source.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "document_id": {"type": "string", "description": "documentId returned by search_materials."},
                            "chunk_id": {"type": "integer", "minimum": 1, "description": "Optional chunkId returned by search_materials."},
                            "max_chars": {"type": "integer", "minimum": 1000, "maximum": 20000, "default": 6000},
                        },
                        "required": ["document_id"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_skill",
                    "description": "Read one approved local skill after search_skills selects it.",
                    "parameters": {
                        "type": "object",
                        "properties": {"name": {"type": "string", "enum": list(AVAILABLE_SKILLS)}},
                        "required": ["name"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_skill_reference",
                    "description": "Read one references/ file explicitly linked by an approved specialist skill. Skill references stay separate from contest-source search results.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "enum": list(AVAILABLE_SKILLS)},
                            "relative_path": {"type": "string", "description": "Path under the selected skill's references/ directory."},
                            "max_chars": {"type": "integer", "minimum": 1000, "maximum": 50000, "default": 30000},
                        },
                        "required": ["name", "relative_path"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "summarize_data",
                    "description": "Compute deterministic table shape, missingness, numeric summaries, and correlations from inline columns.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "columns": {
                                "type": "object",
                                "description": "Column-name to equal-length arrays of numbers, strings, booleans, or nulls.",
                                "additionalProperties": {"type": "array", "maxItems": 20000},
                            }
                        },
                        "required": ["columns"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "inspect_dataset",
                    "description": "Inspect an uploaded CSV, TSV, XLSX, or JSON dataset before modeling. Returns sheets, shape, columns, types, missingness, summaries, correlations, and sample rows.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "upload_id": {"type": "string", "description": "Upload ID shown in the user prompt."},
                            "sheet_name": {
                                "type": ["string", "integer"],
                                "description": "XLSX sheet name or zero-based sheet index. Defaults to the first sheet.",
                            },
                            "sample_rows": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                        },
                        "required": ["upload_id"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_python",
                    "description": "Run reproducible Python analysis in the current task's restricted local workspace. Uploaded datasets are copied into inputs/ and generated deliverables must be written to outputs/. Network and child-process operations are blocked; execution is time- and size-limited.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Complete Python program. Read copied files from inputs/ and write deliverables under outputs/.",
                                "maxLength": MAX_PYTHON_CODE_CHARS,
                            },
                            "input_upload_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "maxItems": 10,
                                "description": "Optional upload IDs to copy into inputs/ before execution.",
                            },
                            "timeout_seconds": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 120,
                                "default": 60,
                            },
                        },
                        "required": ["code"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "solve_linear_program",
                    "description": "Solve a continuous linear program with SciPy HiGHS and return solver status, optimum, variables, and residuals.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "objective": {"type": "array", "items": {"type": "number"}, "minItems": 1, "maxItems": 200},
                            "sense": {"type": "string", "enum": ["min", "max"], "default": "min"},
                            "A_ub": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
                            "b_ub": {"type": "array", "items": {"type": "number"}},
                            "A_eq": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
                            "b_eq": {"type": "array", "items": {"type": "number"}},
                            "bounds": {
                                "type": "array",
                                "description": "One [lower, upper] pair per variable; null means unbounded.",
                                "items": {
                                    "type": "array",
                                    "items": {"type": ["number", "null"]},
                                    "minItems": 2,
                                    "maxItems": 2,
                                },
                            },
                        },
                        "required": ["objective"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_plot_from_dataset",
                    "description": "Create a publication-ready figure directly from selected columns of an uploaded dataset after inspection.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "upload_id": {"type": "string"},
                            "sheet_name": {"type": ["string", "integer"]},
                            "chart_type": {"type": "string", "enum": ["line", "scatter", "bar", "histogram", "box", "heatmap", "multi_panel"]},
                            "x_column": {"type": "string"},
                            "y_columns": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
                            "title": {"type": "string"},
                            "x_label": {"type": "string"},
                            "y_label": {"type": "string"},
                            "filename": {"type": "string"},
                            "formats": {"type": "array", "items": {"type": "string", "enum": ["png", "pdf", "svg"]}},
                        },
                        "required": ["upload_id", "chart_type", "filename"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_plot",
                    "description": "Create publication-ready PNG, PDF, or SVG figures from verified inline data.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chart_type": {"type": "string", "enum": ["line", "scatter", "bar", "histogram", "box", "heatmap"]},
                            "title": {"type": "string"},
                            "x_label": {"type": "string"},
                            "y_label": {"type": "string"},
                            "filename": {"type": "string"},
                            "formats": {"type": "array", "items": {"type": "string", "enum": ["png", "pdf", "svg"]}},
                            "series": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "x": {"type": "array", "items": {"type": ["number", "string"]}},
                                        "y": {"type": "array", "items": {"type": "number"}},
                                        "values": {"type": "array", "items": {"type": "number"}},
                                        "y_error": {"type": "array", "items": {"type": "number"}},
                                        "ci_lower": {"type": "array", "items": {"type": "number"}},
                                        "ci_upper": {"type": "array", "items": {"type": "number"}},
                                        "linestyle": {"type": "string", "enum": ["-", "--", "-.", ":"]},
                                        "marker": {"type": "string"},
                                        "bins": {"type": "integer"},
                                    },
                                },
                            },
                            "matrix": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
                            "x_ticks": {"type": "array", "items": {"type": "string"}},
                            "y_ticks": {"type": "array", "items": {"type": "string"}},
                            "cmap": {"type": "string"},
                            "center": {"type": "number"},
                            "annotate_heatmap": {"type": "boolean"},
                            "panels": {"type": "array", "items": {"type": "object"}, "maxItems": 6},
                            "panel_labels": {"type": "boolean"},
                            "figsize": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                            "dpi": {"type": "integer", "minimum": 300, "maximum": 1200},
                            "save_spec": {"type": "boolean"},
                        },
                        "required": ["chart_type", "filename"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "export_report",
                    "description": "Export final Markdown content to editable Markdown and DOCX files after evidence and reviewer checks pass.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "markdown": {"type": "string", "maxLength": 500000},
                            "filename": {"type": "string"},
                            "formats": {"type": "array", "items": {"type": "string", "enum": ["md", "docx"]}},
                        },
                        "required": ["markdown", "filename"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

    def _mcp_configs(self) -> list[MCPServerConfig]:
        mcp_enabled = self._env_enabled("AGENT_MCP", True)
        matlab_binary = self.root / ".agent-data/mcp/matlab-mcp-server-windows-x64.exe"
        matlab_command = shutil.which("matlab")
        configured_matlab_root = self._config_value("MATLAB_ROOT")
        matlab_root = Path(configured_matlab_root).expanduser() if configured_matlab_root else None
        if matlab_root is None and matlab_command:
            matlab_root = Path(matlab_command).resolve().parent.parent
        origin_server = SOURCE_ROOT / "mcp_servers/origin_server.py"
        matlab_args = [
            f"--initial-working-folder={self.mcp_workspace_root}",
            "--matlab-display-mode=nodesktop",
            "--matlab-session-mode=new",
            "--disable-telemetry=true",
        ]
        if matlab_root:
            matlab_args.insert(0, f"--matlab-root={matlab_root}")
        return [
            MCPServerConfig(
                name="matlab",
                command=str(matlab_binary),
                args=tuple(matlab_args),
                cwd=str(self.root),
                enabled=mcp_enabled
                and self._env_enabled("AGENT_MATLAB_MCP", True)
                and matlab_binary.is_file()
                and bool(matlab_root),
                startup_timeout=20,
                call_timeout=300,
            ),
            MCPServerConfig(
                name="origin",
                command=sys.executable,
                args=(str(origin_server),),
                cwd=str(self.root),
                enabled=mcp_enabled and self._env_enabled("AGENT_ORIGIN_MCP", True) and origin_server.is_file(),
                exposed_tools=frozenset({"origin_status"}),
                startup_timeout=15,
                call_timeout=180,
            ),
        ]

    def _config_value(self, name: str) -> str:
        return os.environ.get(name, self._env_values.get(name, "")).strip()

    def _knowledge_roots(self) -> list[Path]:
        configured = self._config_value("AGENT_KNOWLEDGE_ROOTS")
        roots: list[Path] = []
        if configured:
            roots.extend(Path(item.strip()) for item in configured.split(os.pathsep) if item.strip())
        else:
            default_root = Path(r"D:\codexxiangmu\shumo")
            if default_root.is_dir():
                roots.append(default_root)
        if self._env_enabled("AGENT_KNOWLEDGE_INCLUDE_SKILLS", False):
            roots.extend(
                skill_root / name
                for skill_root in self._skill_roots()
                for name in AVAILABLE_SKILLS
                if (skill_root / name).is_dir()
            )
        return roots

    def _env_enabled(self, name: str, default: bool) -> bool:
        value = self._config_value(name)
        if not value:
            return default
        return value.lower() not in {"0", "false", "no", "off"}

    def _read_local_env(self) -> dict[str, str]:
        path = self.root / ".env"
        if not path.is_file():
            return {}
        values: dict[str, str] = {}
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            values[key.strip()] = value
        return values

    def _mcp_plot_definitions(self) -> list[dict[str, Any]]:
        inline_properties = {
            "chart_type": {"type": "string", "enum": ["line", "scatter", "bar", "histogram", "box", "heatmap"]},
            "title": {"type": "string"},
            "x_label": {"type": "string"},
            "y_label": {"type": "string"},
            "filename": {"type": "string"},
            "formats": {"type": "array", "items": {"type": "string", "enum": ["png", "pdf", "svg"]}},
            "series": {
                "type": "array",
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "x": {"type": "array", "items": {"type": ["number", "string"]}, "maxItems": 200000},
                        "y": {"type": "array", "items": {"type": "number"}, "maxItems": 200000},
                        "values": {"type": "array", "items": {"type": "number"}, "maxItems": 200000},
                    },
                },
            },
            "matrix": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}},
            "template": {"type": "string"},
        }
        dataset_properties = {
            "upload_id": {"type": "string"},
            "sheet_name": {"type": ["string", "integer"]},
            "chart_type": {"type": "string", "enum": ["line", "scatter", "bar", "histogram", "box", "heatmap"]},
            "x_column": {"type": "string"},
            "y_columns": {"type": "array", "items": {"type": "string"}, "maxItems": 30},
            "title": {"type": "string"},
            "x_label": {"type": "string"},
            "y_label": {"type": "string"},
            "filename": {"type": "string"},
            "formats": {"type": "array", "items": {"type": "string", "enum": ["png", "pdf", "svg"]}},
            "template": {"type": "string"},
        }
        definitions = []
        enabled_servers = {item["name"] for item in self.mcp.status() if item["enabled"]}
        for engine, label in (("matlab", "MATLAB"), ("origin", "Origin")):
            if engine not in enabled_servers:
                continue
            definitions.extend(
                [
                    {
                        "type": "function",
                        "function": {
                            "name": f"create_{engine}_plot",
                            "description": f"Create a publication-ready {label} figure through MCP from verified inline data. Returns editable and export artifacts.",
                            "parameters": {
                                "type": "object",
                                "properties": inline_properties,
                                "required": ["chart_type", "filename"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": f"create_{engine}_plot_from_dataset",
                            "description": f"Create a publication-ready {label} figure through MCP from inspected uploaded dataset columns.",
                            "parameters": {
                                "type": "object",
                                "properties": dataset_properties,
                                "required": ["upload_id", "chart_type", "filename"],
                                "additionalProperties": False,
                            },
                        },
                    },
                ]
            )
        return definitions

    def execute(self, name: str, arguments: dict[str, Any], run_id: str) -> dict[str, Any]:
        handlers = {
            "search_skills": self._search_skills,
            "read_skill": self._read_skill,
            "read_skill_reference": self._read_skill_reference,
            "search_materials": self._search_materials,
            "read_material": self._read_material,
            "summarize_data": self._summarize_data,
            "inspect_dataset": self._inspect_dataset,
            "run_python": lambda args: self._run_python(args, run_id),
            "solve_linear_program": self._solve_linear_program,
            "create_plot": lambda args: self._run_script("plot_figure.py", args, run_id),
            "create_plot_from_dataset": lambda args: self._create_plot_from_dataset(args, run_id),
            "create_matlab_plot": lambda args: self._create_mcp_plot("matlab", args, run_id),
            "create_matlab_plot_from_dataset": lambda args: self._create_mcp_plot_from_dataset("matlab", args, run_id),
            "create_origin_plot": lambda args: self._create_mcp_plot("origin", args, run_id),
            "create_origin_plot_from_dataset": lambda args: self._create_mcp_plot_from_dataset("origin", args, run_id),
            "export_report": lambda args: self._run_script("export_report.py", args, run_id),
        }
        handler = handlers.get(name)
        if handler is None and name in self._mcp_tool_names:
            handler = lambda args: self._execute_mcp(name, args, run_id)
        if handler is None:
            raise ToolError(f"未知工具：{name}")
        try:
            result = handler(arguments)
        except ToolError:
            raise
        except Exception as error:
            raise ToolError(str(error).strip() or f"工具 {name} 执行失败") from error
        if not isinstance(result, dict):
            raise ToolError(f"工具 {name} 返回格式无效")
        return result

    def knowledge_status(self) -> dict[str, Any]:
        return self.knowledge.status()

    def reindex_knowledge(self) -> dict[str, Any]:
        try:
            return self.knowledge.reindex()
        except KnowledgeError as error:
            raise ToolError(str(error)) from error

    def start_knowledge_reindex(self) -> dict[str, Any]:
        return self.knowledge.start_reindex()

    def search_knowledge(
        self,
        query: str,
        limit: int = 5,
        extensions: list[str] | None = None,
    ) -> dict[str, Any]:
        status = self.knowledge.status()
        if not status["lastIndexedAt"]:
            raise ToolError("资料库尚未建立索引，请先通过本地管理接口执行资料索引")
        try:
            return self.knowledge.search(query, limit, extensions)
        except KnowledgeError as error:
            raise ToolError(str(error)) from error

    def mcp_status(self, probe: bool = False) -> list[dict[str, Any]]:
        statuses = self.mcp.status(probe=probe)
        if probe:
            origin = next((item for item in statuses if item["name"] == "origin" and item["available"]), None)
            if origin is not None:
                try:
                    result = self.mcp.call_server_tool("origin", "origin_status", {})
                    origin["capability"] = result.get("structured", {})
                except MCPBridgeError as error:
                    origin["capability"] = {"available": False, "reason": str(error)}
        return statuses

    def list_artifacts(self, run_id: str) -> list[dict[str, str]]:
        artifact_dir = self._artifact_dir(run_id)
        if not artifact_dir.is_dir():
            return []
        return [self._artifact_record(path, run_id) for path in sorted(artifact_dir.iterdir()) if path.is_file()]

    def artifact_path(self, run_id: str, filename: str) -> Path:
        artifact_dir = self._artifact_dir(run_id)
        target = (artifact_dir / filename).resolve()
        if target.parent != artifact_dir.resolve() or not target.is_file():
            raise ToolError("产物不存在")
        return target

    def delete_artifacts(self, run_id: str) -> None:
        artifact_dir = self._artifact_dir(run_id).resolve()
        if artifact_dir.parent != self.artifact_root.resolve():
            raise ToolError("产物目录无效")
        if artifact_dir.is_dir():
            shutil.rmtree(artifact_dir)
        python_workspace = (self.python_workspace_root / run_id).resolve()
        if python_workspace.parent != self.python_workspace_root.resolve():
            raise ToolError("Python 工作区无效")
        if python_workspace.is_dir():
            shutil.rmtree(python_workspace)

    def save_upload(self, filename: str, content_type: str, content: bytes) -> dict[str, Any]:
        safe_name = self._safe_filename(filename)
        extension = Path(safe_name).suffix.lower()
        if extension not in ALLOWED_DATA_EXTENSIONS:
            raise ToolError("仅支持 CSV、TSV、XLSX 和 JSON 数据文件")
        if not content:
            raise ToolError("上传文件为空")
        if len(content) > MAX_UPLOAD_BYTES:
            raise ToolError("单个附件不能超过 25 MB")

        upload_id = uuid.uuid4().hex
        upload_dir = self.upload_root / upload_id
        upload_dir.mkdir(parents=True, exist_ok=False)
        target = upload_dir / safe_name
        target.write_bytes(content)
        record = {
            "id": upload_id,
            "name": safe_name,
            "size": len(content),
            "mimeType": content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream",
            "extension": extension,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        (upload_dir / "metadata.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return record

    def get_upload(self, upload_id: str) -> dict[str, Any]:
        upload_dir = self._upload_dir(upload_id)
        metadata_path = upload_dir / "metadata.json"
        if not metadata_path.is_file():
            raise ToolError("附件不存在")
        try:
            record = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as error:
            raise ToolError("附件元数据无效") from error
        if not isinstance(record, dict) or record.get("id") != upload_id:
            raise ToolError("附件元数据无效")
        return record

    def list_uploads(self, upload_ids: list[str]) -> list[dict[str, Any]]:
        records = []
        seen = set()
        for upload_id in upload_ids:
            if upload_id in seen:
                continue
            seen.add(upload_id)
            records.append(self.get_upload(upload_id))
        return records

    def upload_path(self, upload_id: str) -> Path:
        record = self.get_upload(upload_id)
        upload_dir = self._upload_dir(upload_id).resolve()
        target = (upload_dir / str(record["name"])).resolve()
        if target.parent != upload_dir or not target.is_file():
            raise ToolError("附件不存在")
        return target

    def delete_upload(self, upload_id: str) -> None:
        upload_dir = self._upload_dir(upload_id).resolve()
        if upload_dir.parent != self.upload_root.resolve():
            raise ToolError("附件目录无效")
        if upload_dir.is_dir():
            shutil.rmtree(upload_dir)

    def _search_skills(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query", "")).strip().lower()
        if not query:
            raise ToolError("query 不能为空")
        limit = max(1, min(6, int(arguments.get("limit", 3))))
        scores: dict[str, int] = {name: 0 for name in AVAILABLE_SKILLS}
        for alias, names in SKILL_ALIASES.items():
            if alias in query:
                for rank, name in enumerate(names):
                    scores[name] += 20 - rank
        tokens = [token for token in re.split(r"[\s,，。;；:/]+", query) if token]
        results = []
        for name in AVAILABLE_SKILLS:
            text = self._skill_text(name)
            searchable = f"{name}\n{text[:5000]}".lower()
            scores[name] += sum(3 for token in tokens if token in searchable)
            if scores[name] > 0:
                description = self._frontmatter_value(text, "description")
                results.append({"name": name, "score": scores[name], "description": description[:500]})
        results.sort(key=lambda item: (-item["score"], item["name"]))
        return {"query": query, "skills": results[:limit]}

    def _read_skill(self, arguments: dict[str, Any]) -> dict[str, Any]:
        name = str(arguments.get("name", ""))
        if name not in AVAILABLE_SKILLS:
            raise ToolError("该 skill 未获准读取")
        text = self._skill_text(name)
        if not text:
            raise ToolError(f"skill 不存在：{name}")
        return {"name": name, "content": text[:30_000], "truncated": len(text) > 30_000}

    def _read_skill_reference(self, arguments: dict[str, Any]) -> dict[str, Any]:
        name = str(arguments.get("name", ""))
        if name not in AVAILABLE_SKILLS:
            raise ToolError("该 skill 未获准读取")
        relative_path = str(arguments.get("relative_path", "")).strip().replace("\\", "/")
        parts = [part for part in relative_path.split("/") if part]
        if not parts or parts[0] != "references" or any(part in {".", ".."} for part in parts):
            raise ToolError("只能读取 skill 的 references/ 文件")
        skill_dir = self._skill_dir(name)
        if skill_dir is None:
            raise ToolError(f"skill 不存在：{name}")
        target = (skill_dir / Path(*parts)).resolve()
        if skill_dir not in target.parents or not target.is_file():
            raise ToolError("skill reference 不存在或路径无效")
        if target.suffix.lower() not in {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".py", ".m", ".tex"}:
            raise ToolError("不支持读取该 skill reference 类型")
        max_chars = max(1000, min(50_000, int(arguments.get("max_chars", 30_000))))
        content = target.read_text(encoding="utf-8-sig")
        return {
            "name": name,
            "relativePath": "/".join(parts),
            "content": content[:max_chars],
            "truncated": len(content) > max_chars,
        }

    def _search_materials(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.search_knowledge(
            str(arguments.get("query", "")),
            int(arguments.get("limit", 5)),
            arguments.get("extensions"),
        )

    def _read_material(self, arguments: dict[str, Any]) -> dict[str, Any]:
        raw_chunk_id = arguments.get("chunk_id")
        try:
            return self.knowledge.read(
                str(arguments.get("document_id", "")),
                None if raw_chunk_id is None else int(raw_chunk_id),
                int(arguments.get("max_chars", 6000)),
            )
        except KnowledgeError as error:
            raise ToolError(str(error)) from error

    def _summarize_data(self, arguments: dict[str, Any]) -> dict[str, Any]:
        import pandas as pd

        columns = arguments.get("columns")
        if not isinstance(columns, dict) or not columns or len(columns) > 100:
            raise ToolError("columns 必须是包含 1-100 列的对象")
        lengths = {len(value) for value in columns.values() if isinstance(value, list)}
        if len(lengths) != 1 or any(not isinstance(value, list) for value in columns.values()):
            raise ToolError("所有列必须是等长数组")
        if next(iter(lengths)) > 20_000:
            raise ToolError("数据行数不能超过 20000")
        frame = pd.DataFrame(columns)
        return self._summarize_frame(frame)

    def _inspect_dataset(self, arguments: dict[str, Any]) -> dict[str, Any]:
        upload_id = str(arguments.get("upload_id", "")).strip()
        frame, context = self._load_dataset(upload_id, arguments.get("sheet_name"))
        sample_rows = max(1, min(20, int(arguments.get("sample_rows", 5))))
        result = self._summarize_frame(frame)
        sample_json = frame.head(sample_rows).to_json(orient="records", force_ascii=False, date_format="iso")
        result.update(
            {
                "file": self.get_upload(upload_id),
                "sheets": context["sheets"],
                "selectedSheet": context["selectedSheet"],
                "sample": json.loads(sample_json),
            }
        )
        return result

    def _summarize_frame(self, frame: Any) -> dict[str, Any]:
        import pandas as pd

        numeric = frame.select_dtypes(include="number")
        summaries: dict[str, Any] = {}
        for column in numeric.columns:
            series = numeric[column].dropna()
            summaries[str(column)] = {
                "count": int(series.count()),
                "mean": self._finite(series.mean()),
                "std": self._finite(series.std()),
                "min": self._finite(series.min()),
                "median": self._finite(series.median()),
                "max": self._finite(series.max()),
            }
        correlations = numeric.corr().round(6).where(pd.notna(numeric.corr()), None).to_dict() if len(numeric.columns) > 1 else {}
        return {
            "rows": int(len(frame)),
            "columns": [str(column) for column in frame.columns],
            "dtypes": {str(key): str(value) for key, value in frame.dtypes.items()},
            "missing": {str(key): int(value) for key, value in frame.isna().sum().items()},
            "duplicates": int(frame.duplicated().sum()),
            "numericSummary": summaries,
            "correlations": correlations,
        }

    def _create_mcp_plot_from_dataset(self, engine: str, arguments: dict[str, Any], run_id: str) -> dict[str, Any]:
        spec, upload_id, context = self._dataset_plot_spec(arguments)
        result = self._create_mcp_plot(engine, spec, run_id)
        result.update({"source": self.get_upload(upload_id), "selectedSheet": context["selectedSheet"]})
        return result

    def _create_mcp_plot(self, engine: str, arguments: dict[str, Any], run_id: str) -> dict[str, Any]:
        if engine not in {"matlab", "origin"}:
            raise ToolError("未知 MCP 绘图引擎")
        chart_type = str(arguments.get("chart_type", "")).strip().lower()
        allowed = {"line", "scatter", "bar", "histogram", "box", "heatmap"}
        if chart_type not in allowed:
            raise ToolError("图表类型无效")
        if engine == "origin" and chart_type not in {"line", "scatter", "bar", "heatmap"}:
            raise ToolError("Origin MCP 当前支持 line、scatter、bar 和 heatmap")
        filename = self._safe_filename(str(arguments.get("filename", "")))
        spec = dict(arguments)
        spec["chart_type"] = chart_type
        spec["filename"] = filename
        output_dir = self._artifact_dir(run_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        if engine == "matlab":
            script_name = f"{Path(filename).stem}_matlab.m"
            script_path = output_dir / self._safe_filename(script_name)
            script_path.write_text(self._matlab_plot_script(spec, output_dir), encoding="utf-8")
            try:
                response = self.mcp.call_server_tool(
                    "matlab",
                    "run_matlab_file",
                    {"script_path": str(script_path.resolve())},
                )
            except MCPBridgeError as error:
                raise ToolError(f"MATLAB MCP 调用失败：{error}") from error
        else:
            payload = {
                "chart_type": chart_type,
                "filename": filename,
                "output_dir": str(output_dir.resolve()),
                "series": spec.get("series"),
                "matrix": spec.get("matrix"),
                "title": str(spec.get("title", "")),
                "x_label": str(spec.get("x_label", "")),
                "y_label": str(spec.get("y_label", "")),
                "formats": spec.get("formats") or ["png", "pdf"],
                "template": str(spec.get("template", "")),
                "visible": bool(spec.get("visible", False)),
                "save_project": True,
            }
            try:
                response = self.mcp.call_server_tool("origin", "origin_create_plot", payload)
            except MCPBridgeError as error:
                raise ToolError(f"Origin MCP 调用失败：{error}") from error
        if not response.get("ok"):
            raise ToolError(str(response.get("error") or response.get("content") or f"{engine} MCP 绘图失败"))
        return {
            "engine": engine,
            "chartType": chart_type,
            "mcpServer": response.get("mcpServer", engine),
            "mcpTool": response.get("mcpTool", ""),
            "output": response.get("content", ""),
            "structured": response.get("structured", {}),
            "artifacts": self.list_artifacts(run_id),
        }

    def _execute_mcp(self, name: str, arguments: dict[str, Any], run_id: str) -> dict[str, Any]:
        payload = dict(arguments)
        workspace = self._mcp_workspace(run_id)
        if name == "evaluate_matlab_code":
            payload["project_path"] = str(workspace)
        if name in {"check_matlab_code", "run_matlab_file", "run_matlab_test_file"}:
            raw_path = str(payload.get("script_path", "")).strip()
            script_path = Path(raw_path).expanduser().resolve() if raw_path else Path()
            allowed_roots = (workspace.resolve(), self._artifact_dir(run_id).resolve())
            if not raw_path or script_path.suffix.lower() != ".m" or not any(
                script_path == root or root in script_path.parents for root in allowed_roots
            ):
                raise ToolError("MATLAB 脚本必须位于当前任务的 MCP 工作区或产物目录")
            payload["script_path"] = str(script_path)
        try:
            result = self.mcp.call(name, payload)
        except MCPBridgeError as error:
            raise ToolError(str(error)) from error
        if not result.get("ok"):
            raise ToolError(str(result.get("error") or result.get("content") or "MCP 工具执行失败"))
        self._collect_mcp_artifacts(run_id)
        result["artifacts"] = self.list_artifacts(run_id)
        return result

    def _mcp_workspace(self, run_id: str) -> Path:
        self._artifact_dir(run_id)
        workspace = self.mcp_workspace_root / run_id
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace.resolve()

    def _collect_mcp_artifacts(self, run_id: str) -> None:
        workspace = self._mcp_workspace(run_id)
        output_dir = self._artifact_dir(run_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        for source in workspace.rglob("*"):
            if not source.is_file() or source.suffix.lower() not in MCP_ARTIFACT_EXTENSIONS:
                continue
            if source.stat().st_size > MAX_UPLOAD_BYTES:
                continue
            target = output_dir / self._safe_filename(source.name)
            if source.resolve() != target.resolve():
                shutil.copy2(source, target)

    def _matlab_plot_script(self, spec: dict[str, Any], output_dir: Path) -> str:
        chart_type = str(spec["chart_type"])
        stem = self._safe_filename(str(spec["filename"]))
        stem = Path(stem).stem
        formats = list(dict.fromkeys(str(item).lower() for item in (spec.get("formats") or ["png", "pdf"])))
        if any(item not in {"png", "pdf", "svg"} for item in formats):
            raise ToolError("MATLAB 图形格式仅支持 png、pdf、svg")
        series = spec.get("series") or []
        matrix = spec.get("matrix") or []
        if chart_type == "heatmap":
            if not isinstance(matrix, list) or not matrix or len(matrix) > 2000:
                raise ToolError("heatmap 需要最大 2000x2000 的二维矩阵")
            width = len(matrix[0]) if isinstance(matrix[0], list) else 0
            if not width or width > 2000 or any(not isinstance(row, list) or len(row) != width for row in matrix):
                raise ToolError("heatmap 矩阵行长度不一致")
        else:
            if not isinstance(series, list) or not 1 <= len(series) <= 20:
                raise ToolError("series 必须包含 1 至 20 组数据")

        lines = [
            "% Generated by the Math Modeling Agent through MATLAB MCP.",
            "f = figure('Visible','off','Color','w','InvertHardcopy','off','Units','pixels','Position',[100 100 1400 900]);",
            "ax = axes(f,'Position',[0.09 0.11 0.86 0.82],'Color','w'); hold(ax,'on');",
            "colors = [0.0000 0.4470 0.6980; 0.8350 0.3690 0.0000; 0.0000 0.6190 0.4510; 0.8000 0.4750 0.6550; 0.9410 0.7060 0.0000; 0.3370 0.7060 0.9140; 0 0 0];",
        ]
        labels: list[str] = []
        categorical_ticks: list[Any] = []
        if chart_type == "heatmap":
            rows = [self._matlab_vector(row) for row in matrix]
            lines.append(f"M = [{' ; '.join(row.strip('[]') for row in rows)}];")
            lines.extend(["imagesc(ax,M); axis(ax,'tight'); axis(ax,'xy');", "colormap(ax,parula(256)); cb=colorbar(ax); set(cb,'Color',[0.18 0.18 0.18]);"])
            x_ticks = spec.get("x_ticks") or []
            y_ticks = spec.get("y_ticks") or []
            if x_ticks:
                lines.append(f"xticks(ax,1:{len(x_ticks)}); xticklabels(ax,{self._matlab_strings(x_ticks)});")
            if y_ticks:
                lines.append(f"yticks(ax,1:{len(y_ticks)}); yticklabels(ax,{self._matlab_strings(y_ticks)});")
        else:
            normalized = []
            total_points = 0
            for index, item in enumerate(series):
                if not isinstance(item, dict):
                    raise ToolError("series 项必须是对象")
                y_values = list(item.get("y") or item.get("values") or [])
                x_values = list(item.get("x") or range(1, len(y_values) + 1))
                if not y_values or len(x_values) != len(y_values):
                    raise ToolError(f"series[{index}] 的 x/y 长度无效")
                total_points += len(y_values)
                if total_points > 100_000:
                    raise ToolError("MATLAB MCP 单图总数据点不能超过 100000")
                y_literal = self._matlab_vector(y_values)
                numeric_x = all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in x_values)
                x_literal = self._matlab_vector(x_values) if numeric_x else f"1:{len(x_values)}"
                if not numeric_x and not categorical_ticks:
                    categorical_ticks = x_values
                name = str(item.get("name") or f"Series {index + 1}")
                labels.append(name)
                normalized.append((index, x_literal, y_literal, name))
            if chart_type == "bar":
                lengths = {len(list(item.get("y") or item.get("values") or [])) for item in series}
                if len(lengths) != 1:
                    raise ToolError("分组柱状图的系列长度必须一致")
                lines.append(f"X = {normalized[0][1]};")
                for index, _, y_literal, _ in normalized:
                    lines.append(f"Y{index + 1} = {y_literal};")
                columns = " ".join(f"Y{index + 1}(:)" for index, *_ in normalized)
                lines.append(f"b = bar(ax,X,[{columns}],'grouped');")
                lines.append("for k=1:numel(b), b(k).FaceColor=colors(mod(k-1,size(colors,1))+1,:); b(k).EdgeColor='none'; end")
            elif chart_type == "box":
                y_parts = []
                group_parts = []
                for index, _, y_literal, label in normalized:
                    lines.append(f"Y{index + 1} = {y_literal};")
                    y_parts.append(f"Y{index + 1}(:)")
                    group_parts.append(f"repmat(\"{self._matlab_double_quote(label)}\",numel(Y{index + 1}),1)")
                lines.append(f"boxchart(ax,categorical([{' ; '.join(group_parts)}]),[{' ; '.join(y_parts)}]);")
            else:
                for index, x_literal, y_literal, _ in normalized:
                    lines.extend([f"X{index + 1} = {x_literal};", f"Y{index + 1} = {y_literal};"])
                    color = f"colors(mod({index},size(colors,1))+1,:)"
                    if chart_type == "line":
                        lines.append(f"plot(ax,X{index + 1},Y{index + 1},'LineWidth',1.8,'Color',{color});")
                    elif chart_type == "scatter":
                        lines.append(f"scatter(ax,X{index + 1},Y{index + 1},42,{color},'filled','MarkerFaceAlpha',0.82);")
                    else:
                        lines.append(f"histogram(ax,Y{index + 1},'Normalization','probability','FaceColor',{color},'FaceAlpha',0.55,'EdgeColor','none');")
            if categorical_ticks:
                lines.append(f"xticks(ax,1:{len(categorical_ticks)}); xticklabels(ax,{self._matlab_strings(categorical_ticks)});")
            if labels and chart_type != "box":
                lines.append(f"lgd=legend(ax,{self._matlab_strings(labels)},'Location','best','Box','off','Interpreter','none'); set(lgd,'TextColor',[0.18 0.18 0.18],'Color','none');")

        title = self._matlab_single_quote(str(spec.get("title", "")))
        x_label = self._matlab_single_quote(str(spec.get("x_label", "")))
        y_label = self._matlab_single_quote(str(spec.get("y_label", "")))
        lines.extend(
            [
                f"title(ax,'{title}','Interpreter','none','FontWeight','bold','FontSize',15,'Color',[0.12 0.12 0.12]);",
                f"xlabel(ax,'{x_label}','Interpreter','none','Color',[0.15 0.15 0.15]); ylabel(ax,'{y_label}','Interpreter','none','Color',[0.15 0.15 0.15]);",
                "grid(ax,'on'); box(ax,'on'); set(ax,'FontName','Arial','FontSize',12,'LineWidth',1.0,'TickDir','out','XColor',[0.18 0.18 0.18],'YColor',[0.18 0.18 0.18],'GridColor',[0.72 0.72 0.72],'GridAlpha',0.32,'Layer','top');",
            ]
        )
        base = (output_dir / stem).resolve().as_posix()
        for file_format in formats:
            path = self._matlab_single_quote(f"{base}.{file_format}")
            if file_format == "png":
                lines.append(f"exportgraphics(f,'{path}','Resolution',300,'BackgroundColor','white');")
            else:
                lines.append(f"exportgraphics(f,'{path}','ContentType','vector','BackgroundColor','white');")
        fig_path = self._matlab_single_quote(f"{base}.fig")
        lines.extend([f"savefig(f,'{fig_path}');", "close(f);", "disp('MATLAB_MCP_PLOT_OK');"])
        return "\n".join(lines) + "\n"

    @staticmethod
    def _matlab_vector(values: list[Any]) -> str:
        rendered = []
        for value in values:
            try:
                number = float(value)
            except (TypeError, ValueError) as error:
                raise ToolError("MATLAB 数值序列包含非数值") from error
            if not math.isfinite(number):
                raise ToolError("MATLAB 数值序列包含 NaN 或无穷值")
            rendered.append(format(number, ".15g"))
        return f"[{' '.join(rendered)}]"

    @classmethod
    def _matlab_strings(cls, values: list[Any]) -> str:
        return "[" + ",".join(f'"{cls._matlab_double_quote(str(value))}"' for value in values) + "]"

    @staticmethod
    def _matlab_double_quote(value: str) -> str:
        return value.replace('"', '""').replace("\r", " ").replace("\n", " ")

    @staticmethod
    def _matlab_single_quote(value: str) -> str:
        return value.replace("'", "''").replace("\r", " ").replace("\n", " ")

    def _create_plot_from_dataset(self, arguments: dict[str, Any], run_id: str) -> dict[str, Any]:
        spec, upload_id, context = self._dataset_plot_spec(arguments)
        result = self._run_script("plot_figure.py", spec, run_id)
        result.update({"source": self.get_upload(upload_id), "selectedSheet": context["selectedSheet"]})
        return result

    def _dataset_plot_spec(self, arguments: dict[str, Any]) -> tuple[dict[str, Any], str, dict[str, Any]]:
        import pandas as pd

        upload_id = str(arguments.get("upload_id", "")).strip()
        frame, context = self._load_dataset(upload_id, arguments.get("sheet_name"))
        chart_type = str(arguments.get("chart_type", "")).strip()
        x_column = str(arguments.get("x_column", "")).strip()
        raw_y_columns = arguments.get("y_columns", [])
        if not isinstance(raw_y_columns, list):
            raise ToolError("y_columns 必须是列名数组")
        y_columns = list(dict.fromkeys(str(item) for item in raw_y_columns if str(item) in frame.columns))
        if x_column and x_column not in frame.columns:
            raise ToolError(f"数据列不存在：{x_column}")

        spec: dict[str, Any] = {
            "chart_type": chart_type,
            "title": str(arguments.get("title", "")).strip(),
            "x_label": str(arguments.get("x_label", x_column)).strip(),
            "y_label": str(arguments.get("y_label", "")).strip(),
            "filename": arguments.get("filename"),
            "formats": arguments.get("formats", ["png"]),
        }

        if chart_type == "heatmap":
            selected = y_columns or [str(column) for column in frame.select_dtypes(include="number").columns]
            if not 2 <= len(selected) <= 30:
                raise ToolError("热力图需要选择 2-30 个数值列")
            numeric = frame[selected].apply(pd.to_numeric, errors="coerce")
            constant_columns = [column for column in selected if numeric[column].nunique(dropna=True) < 2]
            if constant_columns:
                raise ToolError(f"以下列无法计算相关系数：{'、'.join(constant_columns)}")
            correlations = numeric.corr()
            if correlations.isna().any().any():
                raise ToolError("相关矩阵包含未定义值，请检查缺失或样本量")
            matrix = correlations.values.tolist()
            spec.update({"matrix": matrix, "x_ticks": selected, "y_ticks": selected})
        elif chart_type in {"histogram", "box"}:
            if not y_columns:
                raise ToolError("直方图或箱线图至少需要一个数值列")
            series = []
            for column in y_columns:
                values = pd.to_numeric(frame[column], errors="coerce").dropna()
                if values.empty:
                    raise ToolError(f"数据列没有可用数值：{column}")
                if len(values) > 20_000:
                    values = values.iloc[:: max(1, len(values) // 20_000)]
                series.append({"name": column, "values": [float(value) for value in values]})
            spec["series"] = series
        else:
            if chart_type not in {"line", "scatter", "bar"}:
                raise ToolError("图表类型无效")
            if not y_columns:
                raise ToolError("折线图、散点图或柱状图至少需要一个数值列")
            x_values = frame[x_column] if x_column else pd.Series(range(1, len(frame) + 1), index=frame.index)
            series = []
            limit = 200 if chart_type == "bar" else 5_000
            for column in y_columns:
                y_values = pd.to_numeric(frame[column], errors="coerce")
                selected = pd.DataFrame({"x": x_values, "y": y_values}).dropna()
                if selected.empty:
                    raise ToolError(f"数据列没有可用数值：{column}")
                if len(selected) > limit:
                    selected = selected.iloc[:: max(1, len(selected) // limit)].head(limit)
                x_json = json.loads(selected[["x"]].to_json(orient="records", force_ascii=False, date_format="iso"))
                series.append(
                    {
                        "name": column,
                        "x": [item["x"] for item in x_json],
                        "y": [float(value) for value in selected["y"]],
                    }
                )
            spec["series"] = series

        if arguments.get("template"):
            spec["template"] = str(arguments["template"])
        return spec, upload_id, context

    def _load_dataset(self, upload_id: str, sheet_name: Any = None) -> tuple[Any, dict[str, Any]]:
        import pandas as pd

        path = self.upload_path(upload_id)
        extension = path.suffix.lower()
        sheets: list[str] = []
        selected_sheet: str | int | None = None
        if extension == ".xlsx":
            with pd.ExcelFile(path) as workbook:
                sheets = [str(name) for name in workbook.sheet_names]
                selected_sheet = 0 if sheet_name is None else sheet_name
                frame = pd.read_excel(workbook, sheet_name=selected_sheet)
            if isinstance(selected_sheet, int):
                if selected_sheet < 0 or selected_sheet >= len(sheets):
                    raise ToolError("工作表索引超出范围")
                selected_sheet = sheets[selected_sheet]
        elif extension in {".csv", ".tsv"}:
            separator = "\t" if extension == ".tsv" else None
            last_error: Exception | None = None
            for encoding in ("utf-8-sig", "utf-8", "gb18030"):
                try:
                    frame = pd.read_csv(path, sep=separator, engine="python", encoding=encoding)
                    break
                except UnicodeDecodeError as error:
                    last_error = error
            else:
                raise ToolError("无法识别文本文件编码") from last_error
        elif extension == ".json":
            frame = pd.read_json(path)
        else:
            raise ToolError("附件格式不受支持")
        if not hasattr(frame, "columns"):
            raise ToolError("数据文件没有可读取的表格")
        if len(frame) > MAX_DATA_ROWS:
            raise ToolError(f"数据超过 {MAX_DATA_ROWS} 行，请先拆分或抽样")
        frame.columns = [str(column) for column in frame.columns]
        return frame, {"sheets": sheets, "selectedSheet": selected_sheet}

    def _solve_linear_program(self, arguments: dict[str, Any]) -> dict[str, Any]:
        import numpy as np
        from scipy.optimize import linprog

        objective = np.asarray(arguments.get("objective", []), dtype=float)
        if objective.ndim != 1 or not 1 <= len(objective) <= 200 or not np.isfinite(objective).all():
            raise ToolError("objective 必须是 1-200 个有限数值")
        sense = str(arguments.get("sense", "min")).lower()
        if sense not in {"min", "max"}:
            raise ToolError("sense 必须是 min 或 max")
        size = len(objective)

        def matrix(name: str) -> Any:
            value = arguments.get(name)
            if value in (None, []):
                return None
            array = np.asarray(value, dtype=float)
            if array.ndim != 2 or array.shape[1] != size or not np.isfinite(array).all():
                raise ToolError(f"{name} 的列数必须等于变量数")
            return array

        def vector(name: str, rows: int | None) -> Any:
            value = arguments.get(name)
            if value in (None, []):
                return None
            array = np.asarray(value, dtype=float)
            if array.ndim != 1 or (rows is not None and len(array) != rows) or not np.isfinite(array).all():
                raise ToolError(f"{name} 长度与约束行数不一致")
            return array

        a_ub = matrix("A_ub")
        a_eq = matrix("A_eq")
        b_ub = vector("b_ub", None if a_ub is None else a_ub.shape[0])
        b_eq = vector("b_eq", None if a_eq is None else a_eq.shape[0])
        if (a_ub is None) != (b_ub is None) or (a_eq is None) != (b_eq is None):
            raise ToolError("约束矩阵与右端向量必须成对提供")

        raw_bounds = arguments.get("bounds")
        bounds = [(0, None)] * size if raw_bounds is None else raw_bounds
        if len(bounds) != size or any(not isinstance(item, list) or len(item) != 2 for item in bounds):
            raise ToolError("bounds 必须为每个变量提供 [lower, upper]")

        result = linprog(
            -objective if sense == "max" else objective,
            A_ub=a_ub,
            b_ub=b_ub,
            A_eq=a_eq,
            b_eq=b_eq,
            bounds=[tuple(item) for item in bounds],
            method="highs",
            options={"time_limit": 30.0},
        )
        optimum = None if result.fun is None else float(-result.fun if sense == "max" else result.fun)
        return {
            "success": bool(result.success),
            "status": int(result.status),
            "message": str(result.message),
            "objective": optimum,
            "variables": [] if result.x is None else [float(value) for value in result.x],
            "iterations": int(result.nit),
            "inequalityResidual": [] if not hasattr(result, "ineqlin") else [float(value) for value in result.ineqlin.residual],
            "equalityResidual": [] if not hasattr(result, "eqlin") else [float(value) for value in result.eqlin.residual],
        }

    def _run_python(self, arguments: dict[str, Any], run_id: str) -> dict[str, Any]:
        code = str(arguments.get("code", ""))
        if not code.strip():
            raise ToolError("Python 代码不能为空")
        if len(code) > MAX_PYTHON_CODE_CHARS:
            raise ToolError(f"Python 代码不能超过 {MAX_PYTHON_CODE_CHARS} 个字符")
        try:
            timeout = max(1, min(120, int(arguments.get("timeout_seconds", 60))))
        except (TypeError, ValueError) as error:
            raise ToolError("timeout_seconds 必须是整数") from error
        raw_upload_ids = arguments.get("input_upload_ids", [])
        if not isinstance(raw_upload_ids, list) or len(raw_upload_ids) > 10:
            raise ToolError("input_upload_ids 必须是最多 10 个附件 ID 的数组")

        workspace = self._python_workspace(run_id)
        input_dir = workspace / "inputs"
        output_dir = workspace / "outputs"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        inputs: list[dict[str, Any]] = []
        seen_upload_ids: set[str] = set()
        for raw_upload_id in raw_upload_ids:
            upload_id = str(raw_upload_id).strip()
            if not upload_id or upload_id in seen_upload_ids:
                continue
            seen_upload_ids.add(upload_id)
            record = self.get_upload(upload_id)
            source = self.upload_path(upload_id)
            target = input_dir / self._safe_filename(str(record["name"]))
            shutil.copy2(source, target)
            inputs.append({"uploadId": upload_id, "name": target.name, "relativePath": f"inputs/{target.name}"})

        invocation_id = uuid.uuid4().hex[:12]
        script_path = workspace / f"analysis_{invocation_id}.py"
        wrapper_path = workspace / f"runner_{invocation_id}.py"
        script_path.write_text(code, encoding="utf-8")
        wrapper_path.write_text(self._python_runner_source(), encoding="utf-8")

        environment: dict[str, str] = {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "MPLBACKEND": "Agg",
            "AGENT_PYTHON_WORKSPACE": str(workspace),
        }
        for name in ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "APPDATA", "LOCALAPPDATA", "USERPROFILE"):
            value = os.environ.get(name)
            if value:
                environment[name] = value

        started = datetime.now(timezone.utc)
        try:
            completed = subprocess.run(
                [sys.executable, "-E", "-X", "utf8", str(wrapper_path), str(script_path)],
                cwd=workspace,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
            timed_out = False
            return_code = int(completed.returncode)
            stdout = completed.stdout[-MAX_PYTHON_OUTPUT_CHARS:]
            stderr = completed.stderr[-MAX_PYTHON_OUTPUT_CHARS:]
        except subprocess.TimeoutExpired as error:
            timed_out = True
            return_code = -1
            stdout = self._decode_process_output(error.stdout)[-MAX_PYTHON_OUTPUT_CHARS:]
            stderr = self._decode_process_output(error.stderr)[-MAX_PYTHON_OUTPUT_CHARS:]
        finally:
            wrapper_path.unlink(missing_ok=True)

        artifacts = self._collect_python_artifacts(run_id, output_dir)
        elapsed = max(0.0, (datetime.now(timezone.utc) - started).total_seconds())
        ok = not timed_out and return_code == 0
        result: dict[str, Any] = {
            "ok": ok,
            "exitCode": return_code,
            "timedOut": timed_out,
            "elapsedSeconds": round(elapsed, 3),
            "stdout": stdout,
            "stderr": stderr,
            "inputs": inputs,
            "workspace": {"inputs": "inputs/", "outputs": "outputs/"},
            "artifacts": artifacts,
            "isolation": "受限本机进程（非容器安全边界）",
        }
        if timed_out:
            result["error"] = f"Python 执行超过 {timeout} 秒，已终止"
        elif return_code != 0:
            result["error"] = (stderr or stdout or "Python 执行失败")[-1200:]
        return result

    def _python_workspace(self, run_id: str) -> Path:
        self._artifact_dir(run_id)
        workspace = (self.python_workspace_root / run_id).resolve()
        if workspace.parent != self.python_workspace_root.resolve():
            raise ToolError("Python 工作区无效")
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def _collect_python_artifacts(self, run_id: str, output_dir: Path) -> list[dict[str, str]]:
        artifact_dir = self._artifact_dir(run_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        total = 0
        for source in sorted(output_dir.rglob("*")):
            if not source.is_file() or source.suffix.lower() not in PYTHON_ARTIFACT_EXTENSIONS:
                continue
            size = source.stat().st_size
            if size > MAX_UPLOAD_BYTES or total + size > MAX_PYTHON_ARTIFACT_BYTES:
                continue
            relative = source.relative_to(output_dir).as_posix().replace("/", "__")
            target = artifact_dir / self._safe_filename(relative)
            shutil.copy2(source, target)
            total += size
        return self.list_artifacts(run_id)

    @staticmethod
    def _decode_process_output(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    @staticmethod
    def _python_runner_source() -> str:
        return r'''from __future__ import annotations

import builtins
import os
import pathlib
import runpy
import site
import sys

workspace = pathlib.Path(os.environ["AGENT_PYTHON_WORKSPACE"]).resolve()
allowed_read_roots = {workspace, pathlib.Path(sys.base_prefix).resolve(), pathlib.Path(sys.prefix).resolve()}
for candidate in site.getsitepackages():
    allowed_read_roots.add(pathlib.Path(candidate).resolve())
user_site = site.getusersitepackages()
if user_site:
    allowed_read_roots.add(pathlib.Path(user_site).resolve())


def inside(path, roots):
    try:
        resolved = pathlib.Path(path).resolve()
    except (OSError, TypeError, ValueError):
        return False
    return any(resolved == root or root in resolved.parents for root in roots)


def require_workspace_path(path):
    if not inside(path, {workspace}):
        raise PermissionError("Python 受限工作区禁止修改外部路径")


def audit(event, args):
    if event == "open" and args:
        target = args[0]
        mode = args[1] if len(args) > 1 and isinstance(args[1], str) else "r"
        if isinstance(target, (str, bytes, os.PathLike)):
            if any(flag in mode for flag in "wax+"):
                require_workspace_path(target)
            elif not inside(target, allowed_read_roots):
                raise PermissionError("Python 受限工作区禁止读取外部路径")
    elif event.startswith(("subprocess.", "socket.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "pty.spawn"
    }:
        raise PermissionError("Python 受限工作区禁止网络或子进程操作")
    elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chdir", "os.truncate"} and args:
        require_workspace_path(args[0])
    elif event in {"os.rename", "os.replace"} and len(args) >= 2:
        require_workspace_path(args[0])
        require_workspace_path(args[1])


sys.addaudithook(audit)
os.chdir(workspace)
runpy.run_path(sys.argv[1], run_name="__main__")
'''

    def _run_script(self, script_name: str, arguments: dict[str, Any], run_id: str) -> dict[str, Any]:
        local_script = SOURCE_ROOT / "scripts" / script_name
        script = local_script if local_script.is_file() else TOOLKIT_ROOT / "scripts" / script_name
        if not script.is_file():
            raise ToolError(f"工具脚本不存在：{script_name}")
        output_dir = self._artifact_dir(run_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False, dir=output_dir) as handle:
            json.dump(arguments, handle, ensure_ascii=False)
            spec_path = Path(handle.name)
        try:
            completed = subprocess.run(
                [sys.executable, str(script), "--spec", str(spec_path), "--output-dir", str(output_dir)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=90,
                check=False,
            )
        finally:
            spec_path.unlink(missing_ok=True)
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout).strip()[-1200:]
            raise ToolError(message or f"{script_name} 执行失败")
        try:
            result = json.loads(completed.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as error:
            raise ToolError(f"{script_name} 返回无效 JSON") from error
        result["artifacts"] = self.list_artifacts(run_id)
        return result

    def _skill_text(self, name: str) -> str:
        skill_dir = self._skill_dir(name)
        path = skill_dir / "SKILL.md" if skill_dir is not None else None
        return path.read_text(encoding="utf-8-sig") if path is not None and path.is_file() else ""

    def _skill_dir(self, name: str) -> Path | None:
        for root in self._skill_roots():
            path = (root / name).resolve()
            if path.parent == root and path.is_dir():
                return path
        return None

    def _skill_roots(self) -> tuple[Path, ...]:
        roots = (self.root / "skills", SOURCE_ROOT / "skills", SKILL_ROOT)
        unique: list[Path] = []
        for root in roots:
            resolved = root.resolve()
            if resolved not in unique:
                unique.append(resolved)
        return tuple(unique)

    @staticmethod
    def _frontmatter_value(text: str, key: str) -> str:
        match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.MULTILINE)
        return match.group(1).strip().strip('"\'') if match else ""

    @staticmethod
    def _finite(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if number == number and abs(number) != float("inf") else None

    def _artifact_dir(self, run_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise ToolError("任务 ID 无效")
        return self.artifact_root / run_id

    def _upload_dir(self, upload_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", upload_id):
            raise ToolError("附件 ID 无效")
        return self.upload_root / upload_id

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = Path(str(filename).replace("\\", "/")).name.strip()
        name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", name).strip(" .")
        if not name:
            raise ToolError("文件名无效")
        extension = Path(name).suffix
        stem = Path(name).stem
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
        if stem.upper() in reserved:
            name = f"_{name}"
        if len(name) > 180:
            name = f"{Path(name).stem[: 180 - len(extension)]}{extension}"
        return name

    def _artifact_record(self, path: Path, run_id: str) -> dict[str, str]:
        mime_type, _ = mimetypes.guess_type(path.name)
        return {
            "name": path.name,
            "url": f"/api/artifacts/{run_id}/{quote(path.name)}",
            "mimeType": mime_type or "application/octet-stream",
        }
