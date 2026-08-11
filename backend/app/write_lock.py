"""Process-reentrant, cross-process serialization for local vault mutations."""

import functools
import os
import threading
import time
from pathlib import Path
from typing import Callable


LOCKS_DIR = Path(__file__).parent.parent / "data" / "locks"
VAULT_WRITE_LOCK_FILE = LOCKS_DIR / "vault-writes.lock"
APPROVAL_STATE_LOCK_FILE = LOCKS_DIR / "approval-state.lock"


class CrossProcessRLock:
    """A process RLock paired with a one-byte OS file lock for outermost entry."""

    def __init__(self, path: Path):
        self.path = path
        self._rlock = threading.RLock()
        self._local = threading.local()

    def __enter__(self):
        self._rlock.acquire()
        depth = getattr(self._local, "depth", 0)
        try:
            if depth == 0:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                handle = self.path.open("a+b")
                try:
                    self._acquire_file(handle)
                except Exception:
                    handle.close()
                    raise
                self._local.handle = handle
            self._local.depth = depth + 1
            return self
        except Exception:
            self._rlock.release()
            raise

    def __exit__(self, exc_type, exc, traceback):
        depth = getattr(self._local, "depth", 0)
        try:
            if depth <= 0:
                raise RuntimeError("CrossProcessRLock exit without matching entry.")
            depth -= 1
            self._local.depth = depth
            if depth == 0:
                handle = self._local.handle
                try:
                    self._release_file(handle)
                finally:
                    handle.close()
                    del self._local.handle
        finally:
            self._rlock.release()
        return False

    @staticmethod
    def _acquire_file(handle) -> None:
        if os.name == "nt":
            import msvcrt

            if os.fstat(handle.fileno()).st_size == 0:
                handle.seek(0)
                handle.write(b"\0")
                handle.flush()
                os.fsync(handle.fileno())
            handle.seek(0)
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    # LK_LOCK has a short fixed retry window on Windows. Poll the
                    # non-blocking primitive instead so long writes remain serialized.
                    time.sleep(0.05)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)

    @staticmethod
    def _release_file(handle) -> None:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


vault_write_lock = CrossProcessRLock(VAULT_WRITE_LOCK_FILE)
approval_state_lock = CrossProcessRLock(APPROVAL_STATE_LOCK_FILE)


def serialized_vault_write(function: Callable) -> Callable:
    """Decorate a task/calendar mutation with the shared vault write lock."""
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        with vault_write_lock:
            return function(*args, **kwargs)
    return wrapped
