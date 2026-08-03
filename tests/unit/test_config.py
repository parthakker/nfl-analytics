import importlib
import sys


def test_env_override_wins(monkeypatch, tmp_path):
    """NFL_DB env var must override the default path — the whole fixture-test
    strategy depends on this."""
    fake = tmp_path / "other.duckdb"
    monkeypatch.setenv("NFL_DB", str(fake))
    sys.modules.pop("nfl_analytics.config", None)
    config = importlib.import_module("nfl_analytics.config")
    assert config.NFL_DB == fake
    # restore module state for other tests in this process
    monkeypatch.delenv("NFL_DB")
    sys.modules.pop("nfl_analytics.config", None)
    importlib.import_module("nfl_analytics.config")


def test_defaults_are_repo_rooted():
    from nfl_analytics import config
    assert config.DATA_DIR == config.ROOT / "data"
    assert (config.ROOT / "pyproject.toml").exists()
