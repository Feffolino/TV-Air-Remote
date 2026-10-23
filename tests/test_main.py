from pathlib import Path

from tv_air_remote.__main__ import build_config, main, parse_args


def test_parse_args_defaults():
    args = parse_args([])
    assert args.config == "config.yaml"
    assert args.camera is None
    assert not args.dry_run


def test_dry_run_without_config_uses_defaults(tmp_path):
    args = parse_args(["--dry-run", "--config", str(tmp_path / "missing.yaml")])
    assert build_config(args).tv.host == "dry-run"


def test_missing_config_exits_with_error(tmp_path, caplog):
    assert main(["--config", str(tmp_path / "missing.yaml")]) == 1
    assert "config.example.yaml" in caplog.text


def test_example_config_is_valid():
    example = Path(__file__).resolve().parent.parent / "config.example.yaml"
    args = parse_args(["--config", str(example)])
    cfg = build_config(args)
    assert cfg.tv.port == 8002
    assert cfg.mapping["tv"]["PALM_CLICK"].key == "KEY_ENTER"
    assert "Victory" not in cfg.mapping["tv"]
