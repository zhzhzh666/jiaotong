"""Actual host observations and import checks, never simulated measurements."""
from __future__ import annotations

from importlib import import_module, metadata
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import time
import psutil

from .archive import now

DEPENDENCIES = {
    "osmnx": "osmnx", "networkx": "networkx", "geopandas": "geopandas", "shapely": "shapely",
    "rasterio": "rasterio", "pandas": "pandas", "numpy": "numpy", "scipy": "scipy",
    "matplotlib": "matplotlib", "plotly": "plotly", "streamlit": "streamlit", "pytest": "pytest",
    "sumolib": "sumolib", "traci": "traci", "pyarrow": "pyarrow", "PyYAML": "yaml",
    "psutil": "psutil", "pypdf": "pypdf", "PyMuPDF": "pymupdf", "Pillow": "PIL",
}


def collect_environment(project_root: Path) -> dict:
    memory = psutil.virtual_memory()
    dependencies = []
    for distribution, module in DEPENDENCIES.items():
        started = time.perf_counter()
        try:
            import_module(module)
            dependencies.append({"package": distribution, "module": module, "ok": True,
                                 "version": metadata.version(distribution), "elapsed_s": time.perf_counter() - started})
        except Exception as exc:
            dependencies.append({"package": distribution, "module": module, "ok": False, "error": repr(exc),
                                 "elapsed_s": time.perf_counter() - started})
    drives = {}
    for drive in sorted({project_root.anchor, Path(sys.executable).anchor, "D:\\"}):
        if drive and Path(drive).exists():
            usage = shutil.disk_usage(drive)
            drives[drive] = {"total_gib": usage.total / 2**30, "free_gib": usage.free / 2**30}
    gpu = {"available": False, "reason": "nvidia-smi not on PATH"}
    binary = shutil.which("nvidia-smi")
    if binary:
        try:
            result = subprocess.run([binary, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                    capture_output=True, text=True, timeout=15)
            gpu = {"available": result.returncode == 0, "output": result.stdout.strip(), "error": result.stderr.strip()}
        except (OSError, subprocess.TimeoutExpired) as exc:
            gpu = {"available": False, "reason": str(exc)}
    return {"observed_at": now(), "data_kind": "observed-environment", "python": sys.version,
            "python_executable": sys.executable, "platform": platform.platform(), "cpu": platform.processor(),
            "physical_cores": psutil.cpu_count(logical=False), "logical_cores": psutil.cpu_count(),
            "memory": {"total_gib": memory.total / 2**30, "available_gib": memory.available / 2**30},
            "disks": drives, "gpu": gpu, "dependencies": dependencies,
            "tools": {tool: shutil.which(tool) for tool in ("git", "conda", "sumo", "sumo-gui", "netconvert")}}
