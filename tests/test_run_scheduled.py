import ingest.run_scheduled as run_scheduled
import ingest.sync as sync


def test_logs_output_and_releases_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(run_scheduled, "LOG_DIR", tmp_path)
    monkeypatch.setattr(run_scheduled, "LOCK", tmp_path / "sync.lock")

    def fake_sync(argv):
        print("me@example.com: 3 new")
        return 0

    monkeypatch.setattr(sync, "main", fake_sync)

    assert run_scheduled.main() == 0
    log = (tmp_path / "sync.log").read_text(encoding="utf-8")
    assert "me@example.com: 3 new" in log and "finished with code 0" in log
    assert not (tmp_path / "sync.lock").exists()


def test_crash_is_logged(tmp_path, monkeypatch):
    monkeypatch.setattr(run_scheduled, "LOG_DIR", tmp_path)
    monkeypatch.setattr(run_scheduled, "LOCK", tmp_path / "sync.lock")
    monkeypatch.setattr(sync, "main", lambda argv: 1 / 0)

    assert run_scheduled.main() == 1
    assert "Sync crashed: ZeroDivisionError" in (tmp_path / "sync.log").read_text(encoding="utf-8")


def test_skips_while_another_run_holds_the_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(run_scheduled, "LOG_DIR", tmp_path)
    monkeypatch.setattr(run_scheduled, "LOCK", tmp_path / "sync.lock")
    (tmp_path / "sync.lock").write_text("123", encoding="utf-8")
    monkeypatch.setattr(sync, "main", lambda argv: (_ for _ in ()).throw(AssertionError("must not run")))

    assert run_scheduled.main() == 0
