from __future__ import annotations

import os
from pathlib import Path


def portable_path(root: Path, value: str) -> Path:
    path = Path(os.path.expandvars(value)).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def local_config_value(root: Path, name: str) -> str:
    environment = os.environ.get(name)
    if environment is not None:
        return environment.strip()
    env_file = root / ".env"
    if not env_file.is_file():
        return ""
    try:
        lines = env_file.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == name:
            return value.strip().strip("\"'")
    return ""


def agent_data_dir(root: Path) -> Path:
    configured = local_config_value(root, "AGENT_DATA_DIR")
    return portable_path(root, configured) if configured else (root / ".agent-data").resolve()
