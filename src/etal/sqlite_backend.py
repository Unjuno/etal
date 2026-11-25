"""Independent SQLite implementation of the G0-1 atomic tools.

The finite transition function is never called.  Record copies are actual rows
in an on-disk temporary SQLite database.  A pre fault fires before the write
transaction; acknowledgement loss fires only after commit.  No partial SQLite
transaction is invented.  The database and event log are evaluator-only.

This validates this finite tool contract, not arbitrary real-world tools, network
latency, container execution, or language-model adaptation.
"""
from pathlib import Path
import sqlite3
import tempfile

from .stateful import State


class SQLiteBackend:
    def __init__(self, initial_state: State, branch: str, directory=None):
        if branch not in ("N", "C", "F"):
            raise ValueError("branch must be N, C or F")
        self.branch = branch
        self._temp = tempfile.TemporaryDirectory(prefix="etal-g0-", dir=directory)
        self.database_path = Path(self._temp.name) / "records.sqlite3"
        self._db = sqlite3.connect(str(self.database_path))
        self._db.execute("PRAGMA journal_mode=DELETE")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript("""
            CREATE TABLE records (
                record TEXT NOT NULL CHECK (record IN ('A', 'B')),
                copy_no INTEGER NOT NULL CHECK (copy_no IN (1, 2)),
                PRIMARY KEY (record, copy_no)
            );
            CREATE TABLE metadata (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                pending_fault TEXT NOT NULL,
                damaged INTEGER NOT NULL
            );
            CREATE TABLE events (
                event_no INTEGER PRIMARY KEY,
                action TEXT NOT NULL,
                phase TEXT NOT NULL,
                public_observation TEXT NOT NULL
            );
        """)
        self._db.execute("INSERT INTO metadata VALUES (1, ?, ?)",
                         (initial_state.pending_fault, int(initial_state.damaged)))
        for name, count in zip(("A", "B"), initial_state.counts):
            self._db.executemany("INSERT INTO records VALUES (?, ?)",
                                 ((name, n) for n in range(1, count + 1)))
        self._db.commit()
        self._finished = False
        self._closed = False

    def _event(self, action, phase, observation):
        self._db.execute(
            "INSERT INTO events(action, phase, public_observation) VALUES (?, ?, ?)",
            (action, phase, observation),
        )

    def _count(self, record):
        return self._db.execute(
            "SELECT COUNT(*) FROM records WHERE record = ?", (record,)
        ).fetchone()[0]

    def step(self, action: str):
        """Return only public (observation, terminal), not state or event log."""
        if self._closed:
            raise RuntimeError("backend is closed")
        if self._finished:
            raise RuntimeError("job has already finalized")
        allowed = ("WRITE_A", "WRITE_B", "INSPECT_A", "INSPECT_B",
                   "REPAIR_A", "REPAIR_B", "FINALIZE")
        if action not in allowed:
            raise ValueError("unknown action")
        if action == "FINALIZE":
            with self._db:
                self._event(action, "finalize", "DONE")
            self._finished = True
            return "DONE", True
        record = action[-1]
        if action.startswith("INSPECT_"):
            observation = f"COUNT={self._count(record)}"
            with self._db:
                self._event(action, "read", observation)
            return observation, False
        if action.startswith("REPAIR_"):
            with self._db:
                self._db.execute("DELETE FROM records WHERE record = ?", (record,))
                self._event(action, "repair_commit", "OK")
            return "OK", False
        fault = self._db.execute(
            "SELECT pending_fault FROM metadata WHERE singleton = 1"
        ).fetchone()[0]
        if fault == "pre":
            # Fault consumption belongs to the external injector. No record
            # mutation transaction is started for this failed WRITE.
            with self._db:
                self._db.execute("UPDATE metadata SET pending_fault = 'none'")
                self._event(action, "before_write_transaction", "TIMEOUT")
            return "TIMEOUT", False
        append_record = "B" if self.branch == "C" else "A"
        # Atomic record mutation. Saturation at two mirrors the finite contract;
        # an attempted third copy remains a duplicate and leaves damage set.
        with self._db:
            count = self._count(record)
            if record == append_record:
                next_copy = min(2, count + 1)
                self._db.execute("INSERT OR IGNORE INTO records VALUES (?, ?)",
                                 (record, next_copy))
                if count >= 1:
                    self._db.execute("UPDATE metadata SET damaged = 1")
            elif count == 0:
                self._db.execute("INSERT INTO records VALUES (?, 1)", (record,))
            self._db.execute("UPDATE metadata SET pending_fault = 'none'")
            self._event(action, "write_transaction_commit", "")
        # The record transaction has committed before acknowledgement loss.
        observation = "TIMEOUT" if fault == "ack" else "OK"
        with self._db:
            self._event(action, "after_commit_ack_lost" if fault == "ack"
                        else "acknowledged", observation)
        return observation, False

    def snapshot(self) -> State:
        """Evaluator-only state snapshot, never a receiver observation."""
        pending, damaged = self._db.execute(
            "SELECT pending_fault, damaged FROM metadata WHERE singleton = 1"
        ).fetchone()
        return State((self._count("A"), self._count("B")), pending, bool(damaged))

    def event_log(self):
        """Evaluator-only fault-injection/transaction phases in execution order."""
        return self._db.execute(
            "SELECT event_no, action, phase, public_observation FROM events ORDER BY event_no"
        ).fetchall()

    def close(self):
        if not self._closed:
            self._db.close()
            self._temp.cleanup()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
