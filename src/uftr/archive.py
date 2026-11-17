"""Append-only run directories and rebuildable, portable artifact indexes."""
from __future__ import annotations

import csv
from datetime import datetime
from hashlib import sha256
import html
import json
from pathlib import Path
import subprocess
import time
import traceback
from urllib.parse import quote
from uuid import uuid4
from zoneinfo import ZoneInfo


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def git_state(root: Path) -> dict:
    def command(*args):
        output = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
        return output.stdout.strip() if output.returncode == 0 else None
    return {"commit": command("rev-parse", "HEAD"), "dirty": bool(command("status", "--porcelain"))}


class RunArchive:
    def __init__(self, project_root: Path, config: dict, inputs: list[Path] | None = None):
        self.started = time.perf_counter()
        self.project_root = project_root.resolve()
        self.results = (self.project_root / config["outputs"]["root"]).resolve()
        self.results.relative_to(self.project_root)
        stamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%dT%H%M%S")
        self.run_id = f"{stamp}_p{config['phase']}_{uuid4().hex[:8]}"
        self.path = self.results / "runs" / self.run_id
        self.path.mkdir(parents=True, exist_ok=False)
        for folder in ("figures", "screenshots", "raw", "logs"):
            (self.path / folder).mkdir()
        write_json(self.path / "config.json", config)
        self.manifest = {
            "schema_version": 1, "run_id": self.run_id, "phase": config["phase"],
            "region": config["region"], "scenario": config["scenario"], "strategy": config["strategy"],
            "seed": config["seed"], "started_at": now(), "status": "running",
            "git": git_state(self.project_root), "config": "config.json",
            "config_sha256": file_hash(self.path / "config.json"),
            "inputs": [{"path": str(p.resolve()), "sha256": file_hash(p)} for p in inputs or []],
            "artifacts": [],
        }
        self.flush()

    def flush(self):
        write_json(self.path / "manifest.json", self.manifest)

    def log(self, message: str):
        with (self.path / "logs" / "run.log").open("a", encoding="utf-8") as stream:
            stream.write(f"{now()} {message}\n")

    def add_artifact(self, path: Path, *, title: str, kind: str, data_kind: str,
                     source_paths: list[Path], simulation_time_s: float | None = None, units: dict | None = None):
        relative = path.resolve().relative_to(self.path)
        if not path.is_file():
            raise FileNotFoundError(path)
        if data_kind not in {"observed-environment", "real", "synthetic", "mixed", "reference-page"}:
            raise ValueError("explicit data provenance is required")
        rel = relative.as_posix()
        if any(item["path"] == rel for item in self.manifest["artifacts"]):
            raise ValueError(f"artifact already registered: {rel}")
        sources = []
        for source in source_paths:
            source.resolve().relative_to(self.project_root)
            sources.append({"path": source.resolve().relative_to(self.project_root).as_posix(), "sha256": file_hash(source)})
        if not sources:
            raise ValueError("an artifact must reference its source result")
        self.manifest["artifacts"].append({
            "path": rel, "title": title, "kind": kind, "data_kind": data_kind,
            "simulation_time_s": simulation_time_s, "units": units or {}, "sources": sources,
            "sha256": file_hash(path), "created_at": now(),
        })
        self.flush()

    def __enter__(self):
        self.log("run started")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.manifest["finished_at"] = now()
        self.manifest["elapsed_s"] = time.perf_counter() - self.started
        self.manifest["status"] = "failed" if exc else "success"
        if exc:
            self.manifest["error"] = {"type": exc_type.__name__, "message": str(exc)}
            (self.path / "logs" / "error.txt").write_text("".join(traceback.format_exception(exc_type, exc, tb)), encoding="utf-8")
        self.log(f"run finished: {self.manifest['status']}")
        self.flush()
        rebuild_index(self.results)
        return False


INDEX_FIELDS = ["run_id", "phase", "region", "scenario", "strategy", "seed", "status", "started_at",
                "title", "kind", "data_kind", "simulation_time_s", "path", "manifest", "config", "sha256", "sources", "units"]


def artifact_rows(results: Path) -> list[dict]:
    rows = []
    for manifest_path in sorted((results / "runs").glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for artifact in manifest["artifacts"]:
            row = {k: manifest[k] for k in ("run_id", "phase", "region", "scenario", "strategy", "seed", "status", "started_at")}
            row.update({k: artifact[k] for k in ("title", "kind", "data_kind", "simulation_time_s", "sha256")})
            row.update({"path": (manifest_path.parent / artifact["path"]).relative_to(results).as_posix(),
                        "manifest": manifest_path.relative_to(results).as_posix(),
                        "config": (manifest_path.parent / manifest["config"]).relative_to(results).as_posix(),
                        "sources": json.dumps(artifact["sources"], ensure_ascii=False),
                        "units": json.dumps(artifact["units"], ensure_ascii=False)})
            rows.append(row)
    return rows


def rebuild_index(results: Path) -> list[dict]:
    results.mkdir(parents=True, exist_ok=True)
    rows = artifact_rows(results)
    with (results / "index.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    cards = []
    for row in rows:
        url = quote(row["path"], safe="/")
        preview = f'<img loading="lazy" src="{url}" alt="{html.escape(row["title"], quote=True)}">' if Path(row["path"]).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"} else ""
        description = " | ".join(str(row[key]) for key in ("phase", "region", "scenario", "strategy", "started_at", "data_kind", "status"))
        cards.append(f'<article><h2>{html.escape(row["title"])}</h2><p>{html.escape(description)}</p>'
                     f'<a href="{url}">{preview or "打开文件"}</a><p><a href="{quote(row["manifest"], safe="/")}">运行记录</a> '
                     f'<a href="{quote(row["config"], safe="/")}">配置</a></p></article>')
    document = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>运行图片查询</title>
<style>body{max-width:1100px;margin:32px auto;padding:16px;font:16px/1.6 "Microsoft YaHei",sans-serif;background:#f5f7fa;color:#152536}input{width:90%;padding:12px}article{background:white;margin:20px 0;padding:20px;border:1px solid #ccd6df}img{max-width:100%;max-height:500px}h2{font-size:20px}</style>
<h1>运行图片查询</h1><p>按阶段、日期、区域、情景或策略输入关键词；多个词以空格分隔。历史结果按原运行状态保留。</p>
<input id="query" aria-label="查询关键词" placeholder="例如：00 environment 2026-11">
''' + "\n".join(cards) + '''<script>document.getElementById('query').addEventListener('input',e=>{const words=e.target.value.toLowerCase().split(/\\s+/).filter(Boolean);document.querySelectorAll('article').forEach(a=>a.hidden=!words.every(w=>a.textContent.toLowerCase().includes(w)))})</script></html>'''
    (results / "index.html").write_text(document, encoding="utf-8")
    return rows
