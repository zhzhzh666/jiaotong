import csv
import json
from pathlib import Path
import random
import numpy as np
from PIL import Image
import pytest

from uftr.archive import RunArchive, artifact_rows, file_hash, rebuild_index
from uftr.config import load_config

CONFIG = Path(__file__).resolve().parents[1] / "configs/phase00.yaml"


def test_collision_free_runs_and_queryable_image_provenance(tmp_path):
    config = load_config(CONFIG)
    first = RunArchive(tmp_path, config)
    with first:
        source = first.path / "raw" / "observed.json"
        source.write_text('{"value": 1}', encoding="utf-8")
        image = first.path / "figures" / "中文.png"
        Image.new("RGB", (40, 40), "white").save(image)
        first.add_artifact(image, title='<测试 & "图">', kind="figure", data_kind="observed-environment", source_paths=[source])
    with RunArchive(tmp_path, config) as second:
        pass
    assert first.run_id != second.run_id
    assert image.exists()
    with Image.open(image) as opened:
        opened.verify()
    rows = artifact_rows(tmp_path / "results")
    assert len(rows) == 1 and rows[0]["phase"] == "00" and rows[0]["status"] == "success"
    assert rows[0]["sha256"] == file_hash(image)
    assert (tmp_path / "results" / rows[0]["path"]).is_file()
    source_item = json.loads(rows[0]["sources"])[0]
    assert file_hash(tmp_path / source_item["path"]) == source_item["sha256"]
    html = (tmp_path / "results/index.html").read_text(encoding="utf-8")
    assert "&lt;测试 &amp; &quot;图&quot;&gt;" in html
    assert "%E4%B8%AD%E6%96%87.png" in html
    rebuild_index(tmp_path / "results")
    with (tmp_path / "results/index.csv").open(encoding="utf-8-sig", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 1


def test_failed_run_keeps_artifact_and_traceback(tmp_path):
    with pytest.raises(RuntimeError, match="intentional"):
        with RunArchive(tmp_path, load_config(CONFIG)) as run:
            source = run.path / "raw" / "diagnostic.txt"
            source.write_text("partial result")
            run.add_artifact(source, title="partial", kind="diagnostic", data_kind="synthetic", source_paths=[source])
            raise RuntimeError("intentional")
    manifest = json.loads((run.path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert source.exists() and (run.path / "logs/error.txt").exists()
    assert artifact_rows(tmp_path / "results")[0]["status"] == "failed"


def test_artifact_cannot_escape_run_or_be_registered_twice(tmp_path):
    config = load_config(CONFIG)
    with RunArchive(tmp_path, config) as run:
        external = tmp_path / "outside.txt"
        external.write_text("test")
        with pytest.raises(ValueError):
            run.add_artifact(external, title="outside", kind="figure", data_kind="real", source_paths=[external])
        internal = run.path / "raw/a.txt"
        internal.write_text("test")
        kwargs = dict(title="a", kind="diagnostic", data_kind="synthetic", source_paths=[internal])
        run.add_artifact(internal, **kwargs)
        with pytest.raises(ValueError, match="already registered"):
            run.add_artifact(internal, **kwargs)


def test_output_cannot_escape_project(tmp_path):
    config = load_config(CONFIG)
    config["outputs"]["root"] = "../outside"
    with pytest.raises(ValueError):
        RunArchive(tmp_path, config)


def test_fixed_seed_reproduces_python_and_numpy_samples():
    seed = load_config(CONFIG)["seed"]
    def sample():
        random.seed(seed)
        rng = np.random.default_rng(seed)
        return random.random(), rng.normal(size=10)
    a, b = sample(), sample()
    assert a[0] == b[0]
    np.testing.assert_array_equal(a[1], b[1])
