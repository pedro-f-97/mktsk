"""The single-instance lock for the GUI."""

from mktsk.gui.single_instance import acquire_instance_lock


def _patch_config_path(monkeypatch, tmp_path):
    from mktsk import config

    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")


def test_first_acquire_returns_a_lock(monkeypatch, tmp_path):
    _patch_config_path(monkeypatch, tmp_path)
    lock = acquire_instance_lock(tmp_path)
    assert lock is not None
    lock.unlock()


def test_second_acquire_returns_none_while_held(monkeypatch, tmp_path):
    _patch_config_path(monkeypatch, tmp_path)
    first = acquire_instance_lock(tmp_path)
    assert first is not None
    assert acquire_instance_lock(tmp_path) is None
    first.unlock()


def test_acquire_succeeds_after_release(monkeypatch, tmp_path):
    _patch_config_path(monkeypatch, tmp_path)
    first = acquire_instance_lock(tmp_path)
    assert first is not None
    first.unlock()
    second = acquire_instance_lock(tmp_path)
    assert second is not None
    second.unlock()
