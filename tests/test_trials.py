import pytest

from quantrail.research.trials import TrialRegistry, code_version, write_source_snapshot

CODE = {"commit": None, "dirty": None, "source_sha256": "x"}


def registration(**overrides):
    base = dict(study_id="s", strategy_id="B0", config={"b": 1, "a": 2}, data_manifest_sha256="m",
                hypothesis="h", change_reason="initial", code=CODE)
    return base | overrides


def test_failures_stay_in_the_append_only_log(tmp_path):
    registry = TrialRegistry(tmp_path / "experiment_registry.jsonl")
    with pytest.raises(RuntimeError), registry.trial(**registration()):
        raise RuntimeError("bad data")
    ok = registry.register(**registration(strategy_id="S1"))
    registry.finish(ok, "COMPLETED", result_path="r")
    states = registry.trials()
    assert [t["status"] for t in states] == ["FAILED", "COMPLETED"]
    assert "bad data" in states[0]["status_reason"]
    assert len(registry.path.read_text().splitlines()) == 4


def test_terminal_status_cannot_be_rewritten(tmp_path):
    registry = TrialRegistry(tmp_path / "r.jsonl")
    trial = registry.register(**registration())
    registry.finish(trial, "BLOCKED", reason="tax table unverified")
    with pytest.raises(ValueError):
        registry.finish(trial, "COMPLETED")


def test_block_without_outcome_is_not_silently_completed(tmp_path):
    registry = TrialRegistry(tmp_path / "r.jsonl")
    with registry.trial(**registration()):
        pass
    assert registry.trials()[0]["status"] == "FAILED"


def test_config_hash_ignores_key_order_and_parent_must_exist(tmp_path):
    registry = TrialRegistry(tmp_path / "r.jsonl")
    registry.register(**registration(config={"a": 2, "b": 1}))
    registry.register(**registration(config={"b": 1, "a": 2}))
    assert len({t["config_sha256"] for t in registry.trials()}) == 1
    with pytest.raises(ValueError):
        registry.register(**registration(parent_trial_id="nope"))


def test_uncommitted_edit_changes_source_hash_and_snapshot_is_deterministic(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "m.py").write_text("a = 1\n")
    before = code_version(tmp_path)["source_sha256"]
    one = write_source_snapshot(tmp_path / "one.tar.gz", tmp_path).read_bytes()
    two = write_source_snapshot(tmp_path / "two.tar.gz", tmp_path).read_bytes()
    assert one == two
    (tmp_path / "src" / "m.py").write_text("a = 2\n")
    assert code_version(tmp_path)["source_sha256"] != before
