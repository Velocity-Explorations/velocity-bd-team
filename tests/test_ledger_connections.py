"""The ledger reuses one Postgres connection per thread across transactions (PRO-550).

The first full scan spent about half a second opening a connection for every ledger read or
write, and two portals' fetches ran past their limit. These tests use a stand-in connection,
so they never reach a database.
"""
from __future__ import annotations

import threading
from typing import Any

import pytest

import run
from ledger import db
from portals.registry import Portal


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False
        self.broken = False
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        if self.broken:
            raise RuntimeError("the server closed the connection")
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> Any:
    made: list[FakeConnection] = []

    def connect(url: str | None = None) -> FakeConnection:
        made.append(FakeConnection())
        return made[-1]

    monkeypatch.setenv("DATABASE_URL", "postgresql://scanner@example.invalid/ledger")
    monkeypatch.setattr(db, "connect", connect)
    db.release()
    yield made
    db.release()


def test_transactions_on_one_thread_share_a_connection_and_each_commits(opened: list[FakeConnection]) -> None:
    for _ in range(3):
        with db.tx():
            pass
    assert len(opened) == 1 and opened[0].commits == 3 and not opened[0].closed


def test_an_error_rolls_back_and_keeps_a_healthy_connection(opened: list[FakeConnection]) -> None:
    with pytest.raises(ValueError, match="bad row"):
        with db.tx():
            raise ValueError("bad row")
    with db.tx():
        pass
    assert len(opened) == 1 and (opened[0].rollbacks, opened[0].commits) == (1, 1)


def test_a_dropped_or_broken_connection_is_replaced(opened: list[FakeConnection]) -> None:
    with db.tx() as first:
        pass
    first.closed = True                       # dropped by the server or the network
    with db.tx() as second:
        pass
    assert second is not first
    second.broken = True                      # lost in the middle of a transaction
    with pytest.raises(ValueError, match="lost"):   # the caller sees its own error, not the rollback's
        with db.tx():
            raise ValueError("lost")
    with db.tx() as third:
        pass
    assert third is not second and second.closed and len(opened) == 3


def test_each_thread_has_its_own_connection_and_release_closes_it(opened: list[FakeConnection]) -> None:
    def work() -> None:
        with db.tx():
            pass
        db.release()

    worker = threading.Thread(target=work)
    worker.start()
    worker.join()
    with db.tx():
        pass
    assert len(opened) == 2 and opened[0].closed and not opened[1].closed


def test_a_transaction_inside_another_keeps_its_own_connection(opened: list[FakeConnection]) -> None:
    with db.tx() as outer:
        with db.tx() as inner:
            assert inner is not outer
        assert inner.closed and inner.commits == 1
    assert not outer.closed and outer.commits == 1
    with db.tx() as again:
        assert again is outer   # the reused connection is free again


def test_the_pipeline_closes_a_fetch_threads_connection(opened: list[FakeConnection]) -> None:
    def fetch(page: Any, run_id: int, limit: int | None = None) -> dict[str, int]:
        with db.tx():
            pass
        return {"found": 1, "scraped": 1, "new": 1, "failed": 0}

    portal = Portal(slug="example", name="Example", fetch=fetch, filter=lambda rows: ([], []), needs_browser=False)
    status, counts, error = run.run_fetch(portal, 1, 30, None)
    assert (status, counts["new"], error) == ("completed", 1, None)
    assert len(opened) == 1 and opened[0].closed


def test_sqlite_still_opens_a_connection_per_transaction(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    real, count = db.connect, []

    def counting(url: str | None = None) -> Any:
        count.append(url)
        return real(url)

    monkeypatch.setattr(db, "connect", counting)
    for _ in range(2):
        with db.tx():
            pass
    assert len(count) == 2
