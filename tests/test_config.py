import pytest
from pathlib import Path
from vidx.config import Config, merge_dict


def test_merge_dict():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 99}, "e": 4}
    res = merge_dict(base, override)
    assert res == {"a": 1, "b": {"c": 99, "d": 3}, "e": 4}


def test_config_defaults():
    cfg = Config()
    assert cfg.video["fps"] == 24
    assert cfg.video["codec"] == "libx264"
    assert cfg.project["output_dir"] == "output"
    assert cfg.style["verse"]["font"] == "Nirmala UI"
    assert cfg.publishing["platform"] == "youtube"
    assert cfg.publishing["enabled"] is False


def test_config_from_dict():
    custom = {
        "project": {"name": "Test Project"},
        "video": {"fps": 30, "resolution": "1080x1920"},
    }
    cfg = Config(config_dict=custom)
    assert cfg.project["name"] == "Test Project"
    assert cfg.video["fps"] == 30
    assert cfg.video["resolution"] == "1080x1920"
    # Ensure untouched defaults remain
    assert cfg.video["codec"] == "libx264"


def test_config_from_file():
    sample_path = Path("examples/sindhi_mark_16x9.yaml")
    if sample_path.exists():
        cfg = Config(config_path=sample_path)
        assert cfg.video["resolution"] == "1920x1080"
        assert cfg.style["verse"]["font"] == "Nirmala UI"
        assert len(cfg.get("jobs", [])) > 0


def test_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        Config(config_path="non_existent_config.yaml")


def test_config_save(tmp_path):
    out_file = tmp_path / "saved_config.yaml"
    cfg = Config(config_dict={"project": {"name": "Saved Project"}})
    cfg.save(out_file)
    assert out_file.exists()

    # Reload and verify
    reloaded = Config(config_path=out_file)
    assert reloaded.project["name"] == "Saved Project"
