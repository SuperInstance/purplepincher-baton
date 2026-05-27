"""Tests for TimeoutHandler."""

import time

import pytest

from purplepincher_baton import Baton, BatonState, TimeoutHandler, TimeoutPolicy


class TestTimeoutCheck:
    def test_detects_expired(self):
        handler = TimeoutHandler(default_timeout=0.0)
        b = Baton(payload="work", sender="a", timeout_seconds=0.0)
        time.sleep(0.01)
        expired = handler.check([b])
        assert len(expired) == 1
        assert b.state == BatonState.TIMED_OUT

    def test_no_expired(self):
        handler = TimeoutHandler()
        b = Baton(payload="work", sender="a", timeout_seconds=999.0)
        expired = handler.check([b])
        assert expired == []

    def test_applies_default_timeout(self):
        handler = TimeoutHandler(default_timeout=0.0)
        b = Baton(payload="work", sender="a")  # no timeout set
        time.sleep(0.01)
        expired = handler.check([b])
        assert len(expired) == 1

    def test_skips_terminal(self):
        handler = TimeoutHandler()
        b = Baton(payload="work", sender="a", timeout_seconds=0.0)
        b.complete("a")
        assert handler.check([b]) == []


class TestEscalation:
    def test_mark_timed_out(self):
        handler = TimeoutHandler()
        b = Baton(payload="work", sender="a", timeout_seconds=0.0)
        time.sleep(0.01)
        b.check_timeout()
        rec = handler.escalate(b, policy=TimeoutPolicy.MARK_TIMED_OUT)
        assert rec.policy == TimeoutPolicy.MARK_TIMED_OUT
        assert len(handler.escalation_log) == 1

    def test_drop_policy(self):
        handler = TimeoutHandler()
        b = Baton(payload="work", sender="a", timeout_seconds=0.0)
        time.sleep(0.01)
        b.check_timeout()
        handler.escalate(b, policy=TimeoutPolicy.DROP)
        assert b.state == BatonState.DROPPED

    def test_retry_policy(self):
        handler = TimeoutHandler(max_retries=3)
        b = Baton(payload="work", sender="a", receiver="a", timeout_seconds=0.01)
        time.sleep(0.02)
        b.check_timeout()
        rec = handler.escalate(b, policy=TimeoutPolicy.RETRY)
        assert rec.attempt == 1
        assert handler.retry_count[b.id] == 1

    def test_escalate_policy(self):
        handler = TimeoutHandler()
        b = Baton(payload="work", sender="a", receiver="a", timeout_seconds=0.0)
        time.sleep(0.01)
        b.check_timeout()
        # Escalate needs the baton to be passable — reset state for test
        b.state = BatonState.HELD
        b.updated_at = time.time()
        handler.escalate(b, policy=TimeoutPolicy.ESCALATE, escalate_to="supervisor")
        assert b.receiver == "supervisor"

    def test_on_timeout_callback(self):
        calls = []
        handler = TimeoutHandler()
        handler.on_timeout(lambda baton, policy: calls.append((baton.id, policy)))
        b = Baton(payload="work", sender="a", timeout_seconds=0.0)
        time.sleep(0.01)
        b.check_timeout()
        handler.escalate(b, policy=TimeoutPolicy.DROP)
        assert len(calls) == 1
        assert calls[0][1] == TimeoutPolicy.DROP


class TestHandlerState:
    def test_clear(self):
        handler = TimeoutHandler()
        b = Baton(payload="work", sender="a", timeout_seconds=0.0)
        time.sleep(0.01)
        b.check_timeout()
        handler.escalate(b)
        handler.clear()
        assert len(handler.escalation_log) == 0
        assert len(handler.retry_count) == 0
