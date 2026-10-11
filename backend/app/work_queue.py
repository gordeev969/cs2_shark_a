"""One durable worker per data directory; API reads run independently.

An OS file lock is shared by every API process using this SQLite database.
Imports have priority over sync discovery, and preserve their FIFO job IDs.
"""

import logging
import os
import threading

from .cs2sync import SyncError
from .jobs import parse_isolated, run_job

log = logging.getLogger(__name__)


def acquire_worker_lock(path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    handle = os.fdopen(descriptor, "r+b")
    try:
        if os.name == "nt":
            import msvcrt

            if not path.stat().st_size:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


class WorkQueue:
    def __init__(self, db, config, synchronizer, parse, interval=0.25):
        self.db, self.config = db, config
        self.synchronizer, self.parse = synchronizer, parse
        self.interval = interval
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._handle = None
        self._thread = threading.Thread(target=self._run, name="cs2-work-queue", daemon=True)
        # A sync prepares one replay, then processes available statistics before
        # downloading another replay. This callback runs in the same worker.
        if hasattr(synchronizer, "process_imports"):
            synchronizer.process_imports = self.drain_imports

    def start(self):
        self._thread.start()

    def notify(self):
        self._wake.set()

    def stop(self):
        self._stop.set()
        self._wake.set()
        self._thread.join()

    def _wait(self):
        self._wake.wait(self.interval)
        self._wake.clear()

    def _run(self):
        while not self._stop.is_set():
            handle = acquire_worker_lock(self.config.data_dir / ".work-queue.lock")
            if handle is None:
                self._wait()
                continue
            try:
                self._handle = handle
                self.db.recover_work()
                while not self._stop.is_set():
                    job = self.db.claim_work()
                    if job:
                        self._execute(job)
                    else:
                        self._wait()
            except Exception:
                log.exception("Queue worker interrupted; pending work will be recovered")
                self._wait()
            finally:
                # Closing the descriptor releases the OS lock, including on crashes.
                handle.close()
                self._handle = None

    def drain_imports(self, match_id, parse):
        while job := self.db.claim_work("import"):
            self._execute(job, parse if job["subject"] == str(match_id) else None)

    def _execute(self, job, parse_override=None):
        try:
            if job["kind"] == "import":
                match_id = int(job["subject"])
                match = self.db.match(match_id)
                if match and match["status"] in ("queued", "processing"):
                    path = self.config.uploads / f"{match['file_sha256']}.dem"
                    if path.is_file():
                        parse = parse_override or self.parse
                        if parse is parse_isolated and self._handle and os.name != "nt":
                            descriptor = self._handle.fileno()

                            def parse(path, timeout):
                                # Keep the global lock in the child if its parent is killed.
                                return parse_isolated(path, timeout, inherit_fds=(descriptor,))

                        run_job(self.db, self.config, match_id, path, parse)
                    else:
                        self.db.status(
                            match_id,
                            "failed",
                            "Импорт прерван: файл отсутствует. Загрузите демку повторно.",
                        )
                result = self.db.match(match_id)
                self.db.finish_work(
                    job["id"], "done" if result and result["status"] == "ready" else "failed"
                )
            else:
                try:
                    self.synchronizer.refresh(job["subject"])
                except SyncError as exc:
                    self.synchronizer.store.set_state(
                        job["subject"], exc.status, str(exc), completed=True
                    )
                except Exception:
                    self.synchronizer.store.set_state(
                        job["subject"],
                        "error",
                        "Синхронизация прервана. Повторите позже.",
                        completed=True,
                    )
                self.db.finish_work(job["id"])
        except Exception:
            log.exception("Queued task failed")
            if job["kind"] == "import":
                self.db.status(
                    int(job["subject"]),
                    "failed",
                    "Не удалось обработать импорт. Повторите загрузку.",
                )
            self.db.finish_work(job["id"], "failed")
