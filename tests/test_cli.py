import json
from pathlib import Path
import pytest
import yaml

from uftr.archive import RunArchive
from uftr.cli import main
from uftr.config import load_config

CONFIG = Path(__file__).resolve().parents[1] / "configs/phase00.yaml"


def test_history_honors_custom_output_and_filters(tmp_path, capsys):
    config = load_config(CONFIG)
    config["outputs"]["root"] = "custom-results"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    with RunArchive(tmp_path, config) as run:
        source = run.path / "raw/test.json"
        source.write_text("{}")
        run.add_artifact(source, title="observed", kind="diagnostic", data_kind="observed-environment", source_paths=[source])
    arguments = ["--root", str(tmp_path), "history", "--config", str(config_path)]
    main(arguments + ["--phase", "00", "--run-id", run.run_id, "--kind", "diagnostic"])
    assert len(json.loads(capsys.readouterr().out)) == 1
    main(arguments + ["--phase", "01"])
    assert json.loads(capsys.readouterr().out) == []
    main(["--root", str(tmp_path), "reindex", "--config", str(config_path)])
    assert json.loads(capsys.readouterr().out)["artifacts"] == 1
    assert (tmp_path / "custom-results/index.html").exists()


def test_cli_rejects_unimplemented_phase():
    with pytest.raises(SystemExit) as error:
        main(["run", "--phase", "02"])
    assert error.value.code == 2
