from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import random
import sys
import numpy as np

from .archive import RunArchive, artifact_rows, rebuild_index, write_json
from .config import load_config, time_grid
from .environment import collect_environment


def run_phase00(root: Path, config_path: Path) -> Path:
    config = load_config(config_path)
    if config["phase"] != "00":
        raise ValueError("only Phase 00 is implemented")
    random.seed(config["seed"])
    np.random.seed(config["seed"])
    inputs = [config_path, *sorted(root.glob("*.pdf"))]
    with RunArchive(root, config, inputs) as run:
        run.manifest["command"] = [sys.executable, *sys.argv]
        run.flush()
        report = collect_environment(root)
        report["time_grid"] = {"endpoint_count": len(time_grid(config)), "interval_count": len(time_grid(config)) - 1}
        source = run.path / "raw" / "environment.json"
        write_json(source, report)
        run.log(f"checked {len(report['dependencies'])} imports")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
        memory = report["memory"]
        names = ["RAM", *report["disks"]]
        free = [memory["available_gib"], *[d["free_gib"] for d in report["disks"].values()]]
        used = [memory["total_gib"] - free[0], *[d["total_gib"] - d["free_gib"] for d in report["disks"].values()]]
        axes[0].barh(names, used, label="Used", color="#758ca5")
        axes[0].barh(names, free, left=used, label="Available", color="#36a38b")
        axes[0].set_xlabel("GiB (actual observation)")
        axes[0].set_title("Memory and disk snapshot")
        axes[0].legend()
        count = sum(item["ok"] for item in report["dependencies"])
        axes[1].bar(["Passed", "Failed"], [count, len(report["dependencies"]) - count], color=["#36a38b", "#cc5544"])
        axes[1].set_ylim(0, len(report["dependencies"]) + 2)
        axes[1].set_ylabel("Python packages")
        axes[1].set_title("Dependency import checks")
        for i, value in enumerate((count, len(report["dependencies"]) - count)):
            axes[1].text(i, value + .25, str(value), ha="center")
        fig.suptitle("Phase 00 | " + report["observed_at"] + " | seed=" + str(config["seed"]))
        for extension in ("png", "svg"):
            path = run.path / "figures" / f"environment_check.{extension}"
            fig.savefig(path, dpi=config["outputs"]["dpi"])
            run.add_artifact(path, title="Phase 00 环境与依赖检查", kind="figure", data_kind="observed-environment",
                             source_paths=[source], units={"storage": "GiB"})
        plt.close(fig)
        if count != len(report["dependencies"]):
            raise RuntimeError("required imports failed; see raw/environment.json")
        print(json.dumps({"run_id": run.run_id, "imports_passed": count, "path": str(run.path)}, ensure_ascii=False))
    return run.path


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="城市暴雨内涝交通韧性研究（Phase 00—02）")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="项目根目录")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-config")
    check.add_argument("--config", type=Path, default=Path("configs/phase00.yaml"))
    run = sub.add_parser("run")
    run.add_argument("--phase", choices=["00","01","02"], required=True)
    run.add_argument("--config", type=Path)
    run.add_argument("--offline-source",type=Path,help="Phase 01/02 已保存的原始数据快照目录，校验后离线重建")
    history = sub.add_parser("history")
    history.add_argument("--config", type=Path, default=Path("configs/phase00.yaml"))
    for flag in ("phase", "region", "scenario", "strategy", "kind", "run-id", "date"):
        history.add_argument("--" + flag)
    reindex = sub.add_parser("reindex")
    reindex.add_argument("--config", type=Path, default=Path("configs/phase00.yaml"))
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command in {"run", "check-config"}:
        selected=args.config or Path(f'configs/phase{args.phase}.yaml')
        path = (root / selected).resolve()
        if args.command == "check-config":
            config = load_config(path)
            print(json.dumps({"valid": True, "phase": config["phase"], "endpoints": len(time_grid(config))}))
        else:
            if args.phase=='00':
                if args.offline_source: parser.error('--offline-source only applies to Phase 01/02')
                run_phase00(root, path)
            elif args.phase=='01':
                from .phase01 import run_phase01
                run_phase01(root,path,args.offline_source)
            else:
                from .phase02 import run_phase02
                run_phase02(root,path,args.offline_source)
    elif args.command == "reindex":
        results = (root / load_config(root / args.config)["outputs"]["root"]).resolve()
        results.relative_to(root)
        rows = rebuild_index(results)
        print(json.dumps({"artifacts": len(rows), "index": str(results / "index.html")}))
    else:
        results = (root / load_config(root / args.config)["outputs"]["root"]).resolve()
        results.relative_to(root)
        rows = artifact_rows(results)
        for key in ("phase", "region", "scenario", "strategy", "kind", "run_id"):
            value = getattr(args, key)
            if value is not None:
                rows = [row for row in rows if str(row[key]) == value]
        if args.date:
            datetime.strptime(args.date, "%Y-%m-%d")
            rows = [row for row in rows if row["started_at"].startswith(args.date)]
        print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
