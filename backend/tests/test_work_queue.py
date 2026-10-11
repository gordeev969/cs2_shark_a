import hashlib
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import SecretCipher
from backend.app.config import Config
from backend.app.cs2sync import Synchronizer, SyncStore
from backend.app.db import Database
from backend.app.jobs import parse_isolated
from backend.app.main import create_app
from backend.app.work_queue import acquire_worker_lock
from backend.tests.conftest import P, Q
from backend.tests.test_api import DEMO, await_job
from backend.tests.test_auth import login_as
from backend.tests.test_cs2sync import AUTH, CODE_A, CODE_B


def upload(client, number, headers=None):
    return client.post(
        "/api/matches/import",
        files={"file": (f"{number}.dem", DEMO + bytes([number]))},
        headers=headers,
    )


def test_fifo_single_parser_and_ready_statistics_remain_available(tmp_path, parsed):
    config = Config(data_dir=tmp_path, require_steam_login=False)
    db = Database(config.database)
    db.initialize()
    ready_id, _ = db.reserve("ready")
    db.persist(ready_id, parsed)
    started, release = threading.Event(), threading.Event()
    calls = []

    def parse(path, timeout):
        number = path.read_bytes()[-1]
        calls.append(number)
        if number == 1:
            started.set()
            assert release.wait(10)
        if number == 2:
            raise ValueError("Контролируемая ошибка парсера")
        return parsed

    with TestClient(create_app(config, parse)) as client:
        try:
            one = upload(client, 1).json()
            assert started.wait(3)
            two, three = upload(client, 2).json(), upload(client, 3).json()
            assert client.get(f"/api/matches/{one['id']}").json()["status"] == "processing"
            assert two["queue_position"] == 1 and three["queue_position"] == 2
            assert calls == [1]
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                response = pool.submit(client.get, f"/api/matches/{ready_id}").result(timeout=2)
                assert {p["steam_id64"]: p for p in response.json()["players"]} == {
                    p["steam_id64"]: p for p in parsed["players"]
                }
                dashboard = client.get("/api/dashboard").json()
                assert dashboard["match_count"] == 1 and dashboard["queued_count"] == 3
            finally:
                pool.shutdown(wait=False)
        finally:
            release.set()
        assert await_job(client, two["id"])["status"] == "failed"
        assert await_job(client, three["id"])["status"] == "ready"
        assert calls == [1, 2, 3]


def test_two_api_instances_and_users_share_one_worker_without_pending_data_leaks(tmp_path, parsed):
    config = Config(data_dir=tmp_path)
    started, release = threading.Event(), threading.Event()
    calls = []
    app1 = app2 = None

    def parse(path, timeout):
        calls.append(path.read_bytes()[-1])
        if len(calls) == 1:
            started.set()
            assert release.wait(10)
        return parsed

    app1 = create_app(config, parse)
    with TestClient(app1) as first:
        try:
            headers1 = login_as(app1, first, P, "queue-user-one")
            one = upload(first, 1, headers1).json()
            assert started.wait(3)
            app2 = create_app(config, parse)
            with TestClient(app2) as second:
                try:
                    headers2 = login_as(app2, second, Q, "queue-user-two")
                    two = upload(second, 2, headers2).json()
                    assert two["queue_position"] == 1
                    assert calls == [1]
                    # Starting another API does not reset the active parser's state.
                    assert first.get(f"/api/matches/{one['id']}").json()["status"] == "processing"
                    assert second.get(f"/api/matches/{one['id']}").status_code == 404
                    assert first.get(f"/api/matches/{two['id']}").status_code == 404
                    assert first.get("/api/dashboard").json()["queued_count"] == 1
                    assert second.get("/api/dashboard").json()["queued_count"] == 1
                finally:
                    release.set()
                assert await_job(second, two["id"])["status"] == "ready"
        finally:
            release.set()
    assert calls == [1, 2]


def test_capacity_is_atomic_and_duplicates_do_not_take_another_slot(tmp_path, parsed):
    config = Config(data_dir=tmp_path, require_steam_login=False, max_pending_imports=2)
    started, release = threading.Event(), threading.Event()

    def parse(path, timeout):
        started.set()
        assert release.wait(10)
        return parsed

    with TestClient(create_app(config, parse)) as client:
        try:
            one = upload(client, 1).json()
            assert started.wait(3)
            assert upload(client, 2).status_code == 202
            duplicate = upload(client, 1)
            assert duplicate.status_code == 202 and duplicate.json()["duplicate"]
            assert duplicate.json()["id"] == one["id"]
            full = upload(client, 3)
            assert full.status_code == 429 and "Очередь" in full.json()["detail"]
            assert len(client.get("/api/matches").json()) == 2
            assert len(list(config.uploads.glob("*.dem"))) == 2
            assert not list(config.uploads.glob("incoming-*.tmp"))
        finally:
            release.set()


def test_restart_keeps_fifo_and_places_retries_at_the_tail(tmp_path, parsed):
    config = Config(data_dir=tmp_path, require_steam_login=False)
    config.uploads.mkdir()
    db = Database(config.database)
    db.initialize()
    ids = []
    for number in [1, 2, 3]:
        digest = hashlib.sha256(DEMO + bytes([number])).hexdigest()
        match_id, _ = db.reserve(digest)
        ids.append(match_id)
        (config.uploads / f"{digest}.dem").write_bytes(DEMO + bytes([number]))
        if number == 1:
            db.status(match_id, "failed", "Previous failure")
    # Old match ID, newly queued attempt. It must stay behind jobs 2 and 3.
    db.reserve(hashlib.sha256(DEMO + b"\x01").hexdigest())
    db.status(ids[1], "processing")
    calls = []

    def parse(path, timeout):
        calls.append(path.read_bytes()[-1])
        return parsed

    with TestClient(create_app(config, parse)) as client:
        assert await_job(client, ids[0])["status"] == "ready"
        assert calls == [2, 3, 1]


def test_shutdown_preserves_waiting_jobs(tmp_path, parsed):
    config = Config(data_dir=tmp_path, require_steam_login=False)
    started, release = threading.Event(), threading.Event()
    calls = []

    def parse(path, timeout):
        calls.append(path.read_bytes()[-1])
        started.set()
        assert release.wait(10)
        return parsed

    app = create_app(config, parse)
    with TestClient(app) as client:
        try:
            upload(client, 1)
            assert started.wait(3)
            two = upload(client, 2).json()
            stopping = threading.Thread(target=app.state.queue.stop)
            stopping.start()
            assert app.state.queue._stop.wait(3)
        finally:
            release.set()
        stopping.join(3)
        assert not stopping.is_alive()
        assert client.get(f"/api/matches/{two['id']}").json()["status"] == "queued"
        assert calls == [1]
    with TestClient(create_app(config, parse)) as client:
        assert await_job(client, two["id"])["status"] == "ready"
    assert calls == [1, 2]


def test_prepared_statistics_have_priority_over_sync_discovery(tmp_path, parsed):
    config = Config(data_dir=tmp_path, require_steam_login=False)
    started, release = threading.Event(), threading.Event()
    order = []

    def parse(path, timeout):
        number = path.read_bytes()[-1]
        order.append(number)
        if number == 1:
            started.set()
            assert release.wait(10)
        return parsed

    class Sync:
        def __init__(self, store):
            self.store = store

        def status(self, steam):
            return self.store.status(steam)

        def refresh(self, steam):
            order.append("sync")
            self.store.set_state(steam, "idle")

    app = create_app(config, parse, sync_factory=lambda db, config, store: Sync(store))
    with TestClient(app) as client:
        try:
            upload(client, 1)
            assert started.wait(3)
            app.state.sync_store.configure(P, AUTH, CODE_A)
            assert app.state.sync_store.enqueue(P)
            two = upload(client, 2).json()
        finally:
            release.set()
        assert await_job(client, two["id"])["status"] == "ready"
        deadline = time.monotonic() + 3
        while order[-1] != "sync" and time.monotonic() < deadline:
            time.sleep(0.01)
        assert order == [1, 2, "sync"]


def test_failed_file_publication_rolls_back_the_job(tmp_path, monkeypatch):
    with TestClient(create_app(Config(data_dir=tmp_path, require_steam_login=False))) as client:

        def fail(*args):
            raise OSError("Disk full")

        monkeypatch.setattr(Path, "replace", fail)
        assert upload(client, 1).status_code == 507
        assert client.get("/api/matches").json() == []
        with client.app.state.db.connect() as c:
            assert c.execute("SELECT COUNT(*) FROM work_queue").fetchone()[0] == 0


def test_sync_cannot_lose_a_new_request_while_finishing_the_previous_job(tmp_path):
    config = Config(data_dir=tmp_path)
    db = Database(config.database)
    db.initialize()
    store = SyncStore(db, SecretCipher(config))
    store.initialize()
    store.configure(P, AUTH, CODE_A)
    assert store.enqueue(P)
    job = db.claim_work("sync")
    # refresh() has published its final state, but the worker is still finalizing.
    store.set_state(P, "idle")
    assert not store.enqueue(P)
    assert store.connection(P)["status"] == "idle"
    db.finish_work(job["id"])
    assert store.enqueue(P)
    assert db.claim_work("sync")["subject"] == P


def test_sync_parses_waiting_statistics_before_downloading_the_next_match(tmp_path, parsed):
    config = Config(data_dir=tmp_path, require_steam_login=False, max_pending_imports=1)
    downloading, release = threading.Event(), threading.Event()
    order = []

    def parse(path, timeout):
        order.append(("parse", path.read_bytes()[-1]))
        return parsed

    class Downloader:
        count = 0

        def download(self, url, path):
            self.count += 1
            number = self.count + 9
            order.append(("download", number))
            if self.count == 1:
                downloading.set()
                assert release.wait(10)
            data = DEMO + bytes([number])
            path.write_bytes(data)
            return hashlib.sha256(data).hexdigest()

    def factory(db, config, store):
        return Synchronizer(
            db,
            config,
            store,
            SimpleNamespace(api_key="test", next_code=lambda *args: None),
            SimpleNamespace(resolve=lambda code: {"demo_url": code}),
            Downloader(),
            parse,
        )

    app = create_app(config, parse, sync_factory=factory)
    with TestClient(app) as client:
        try:
            app.state.sync_store.configure(P, AUTH, CODE_A)
            app.state.sync_store.discover(P, CODE_B)
            assert app.state.sync_store.enqueue(P)
            app.state.queue.notify()
            assert downloading.wait(3)
            manual = upload(client, 2).json()
        finally:
            release.set()
        assert await_job(client, manual["id"])["status"] == "ready"
        deadline = time.monotonic() + 3
        while app.state.sync_store.connection(P)["status"] != "idle":
            assert time.monotonic() < deadline
            time.sleep(0.01)
        assert order == [
            ("download", 10),
            ("parse", 2),
            ("parse", 10),
            ("download", 11),
            ("parse", 11),
        ]
        assert app.state.synchronizer.status(P)["imported_count"] == 2


def test_version_two_database_recovers_imports_without_losing_ready_stats(tmp_path, parsed):
    config = Config(data_dir=tmp_path, require_steam_login=False)
    config.uploads.mkdir()
    db = Database(config.database)
    db.initialize()
    ready, _ = db.reserve("ready")
    db.persist(ready, parsed)
    digest = hashlib.sha256(DEMO).hexdigest()
    (config.uploads / f"{digest}.dem").write_bytes(DEMO)
    with db.connect() as c:
        c.execute("DROP TABLE work_queue")
        c.execute("PRAGMA user_version=2")
        c.execute(
            "INSERT INTO matches(file_sha256,status,imported_at) VALUES(?,'processing','2026-01-01')",
            (digest,),
        )
        pending = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    with TestClient(create_app(config, lambda path, timeout: parsed)) as client:
        assert await_job(client, pending)["status"] == "ready"
        assert {
            p["steam_id64"]: p for p in client.get(f"/api/matches/{ready}").json()["players"]
        } == {p["steam_id64"]: p for p in parsed["players"]}
        with db.connect() as c:
            assert c.execute("PRAGMA user_version").fetchone()[0] == 3


@pytest.mark.skipif(os.name == "nt", reason="POSIX inherited file-lock semantics")
def test_child_keeps_global_lock_when_parent_descriptor_closes(tmp_path):
    path = tmp_path / ".work-queue.lock"
    handle = acquire_worker_lock(path)
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; print('ready',flush=True); time.sleep(10)"],
        stdout=subprocess.PIPE,
        text=True,
        pass_fds=(handle.fileno(),),
    )
    try:
        assert child.stdout.readline().strip() == "ready"
        handle.close()
        assert acquire_worker_lock(path) is None
    finally:
        child.terminate()
        child.wait(timeout=3)
    another = acquire_worker_lock(path)
    assert another is not None
    another.close()


def test_native_parser_inherits_lock_and_uses_one_cpu_thread(tmp_path, monkeypatch):
    handle = acquire_worker_lock(tmp_path / ".work-queue.lock")

    def finish(command, **kwargs):
        if os.name != "nt":
            assert kwargs["pass_fds"] == (handle.fileno(),)
        assert kwargs["env"]["POLARS_MAX_THREADS"] == "1"
        assert kwargs["env"]["RAYON_NUM_THREADS"] == "1"
        Path(command[-1]).write_text('{"players": []}')
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", finish)
    try:
        parse_isolated(tmp_path / "test.dem", 3, inherit_fds=(handle.fileno(),))
    finally:
        handle.close()
