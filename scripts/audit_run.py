"""Verify the saved files and indexes of a completed run without changing it."""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import unquote
import xml.etree.ElementTree as ET

from PIL import Image
from uftr.archive import artifact_rows, file_hash, write_json


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        self.paths.extend(value for key, value in attrs if key in {"href", "src"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, default=Path("docs/validation/run_audit.json"))
    args = parser.parse_args()
    root = args.root.resolve()
    results = root / "results"
    run = results / "runs" / args.run_id
    run.resolve().relative_to((results / "runs").resolve())
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "success", "run not successful"
    assert file_hash(run / manifest["config"]) == manifest["config_sha256"], "config changed"
    for item in manifest["inputs"]:
        assert file_hash(Path(item["path"])) == item["sha256"], f"input changed: {item['path']}"
    for artifact in manifest["artifacts"]:
        path = run / artifact["path"]
        assert file_hash(path) == artifact["sha256"], f"artifact changed: {path}"
        for source in artifact["sources"]:
            assert file_hash(root / source["path"]) == source["sha256"], f"source changed: {source['path']}"
        if path.suffix == ".png":
            with Image.open(path) as image:
                image.verify()
        elif path.suffix == ".svg":
            assert ET.parse(path).getroot().tag.endswith("svg")
    links = Links()
    links.feed((results / "index.html").read_text(encoding="utf-8"))
    for value in links.paths:
        assert (results / unquote(value)).is_file(), f"broken local index link: {value}"
    rows = [row for row in artifact_rows(results) if row["run_id"] == args.run_id]
    assert len(rows) == len(manifest["artifacts"])
    dependency_imports=None
    if manifest['phase']=='00':
        environment = json.loads((run / "raw/environment.json").read_text(encoding="utf-8"))
        assert all(item["ok"] for item in environment["dependencies"])
        dependency_imports=len(environment['dependencies'])
    elif manifest['phase']=='01':
        network=json.loads((run/'raw/network_report.json').read_text(encoding='utf-8'))
        processed=root/network['processed_root']
        inventory=json.loads((processed/'output_inventory.json').read_text(encoding='utf-8'))
        for item in inventory['files']:
            path=(processed/item['path']).resolve(); path.relative_to(processed.resolve())
            assert file_hash(path)==item['sha256'],f'processed output changed: {path}'
        assert all(network[k]['missing_required_attributes']==0 for k in ['small','nanshan'])
    report = {"run_id": args.run_id, "status": "passed", "artifacts_verified": len(rows),
              "inputs_verified": len(manifest["inputs"]), "index_links_verified": len(links.paths),
              "dependency_imports": dependency_imports, "git": manifest["git"],
              "elapsed_s": manifest["elapsed_s"], "visual_png_review": "separate human/agent inspection required"}
    write_json(root / args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
