"""Tests for the Baton class."""

import time

from purplepincher_baton import Baton, BatonState


class TestBatonCreation:
    def test_basic_creation(self):
        b = Baton(payload={"task": "x"}, sender="alice")
        assert b.sender == "alice"
        assert b.receiver == "alice"
        assert b.state == BatonState.CREATED
        assert b.payload == {"task": "x"}
        assert b.timeout_seconds is None
        assert b.parent_id is None
        assert len(b.history) == 1

    def test_creation_with_receiver(self):
        b = Baton(payload=None, sender="alice", receiver="bob")
        assert b.receiver == "bob"

    def test_unique_ids(self):
        ids = {Baton(payload=1, sender="a").id for _ in range(100)}
        assert len(ids) == 100

    def test_metadata(self):
        b = Baton(payload="data", sender="a", metadata={"priority": "high"})
        assert b.metadata["priority"] == "high"


class TestBatonPassing:
    def test_pass_to(self):
        b = Baton(payload="work", sender="alice", receiver="alice")
        b.pass_to("bob")
        assert b.state == BatonState.PASSED
        assert b.receiver == "bob"
        assert b.sender == "alice"

    def test_acknowledge(self):
        b = Baton(payload="work", sender="alice", receiver="alice")
        b.pass_to("bob")
        b.acknowledge("bob")
        assert b.state == BatonState.ACKNOWLEDGED

    def test_hold(self):
        b = Baton(payload="work", sender="alice")
        b.hold("alice")
        assert b.state == BatonState.HELD

    def test_complete(self):
        b = Baton(payload="work", sender="alice")
        b.complete("alice")
        assert b.state == BatonState.COMPLETED
        assert b.is_terminal()

    def test_drop(self):
        b = Baton(payload="work", sender="alice")
        b.drop("alice", reason="something went wrong")
        assert b.state == BatonState.DROPPED
        assert b.metadata["drop_reason"] == "something went wrong"
        assert b.is_terminal()

    def test_cannot_pass_completed(self):
        b = Baton(payload="work", sender="alice")
        b.complete("alice")
        try:
            b.pass_to("bob")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_cannot_pass_dropped(self):
        b = Baton(payload="work", sender="alice")
        b.drop("alice")
        try:
            b.pass_to("bob")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_cannot_acknowledge_unpassed(self):
        b = Baton(payload="work", sender="alice")
        try:
            b.acknowledge("alice")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


class TestBatonHistory:
    def test_history_records_events(self):
        b = Baton(payload="work", sender="alice")
        b.pass_to("bob")
        b.acknowledge("bob")
        b.complete("bob")
        assert len(b.history) == 4  # created + passed + ack + completed
        agents = [h[0] for h in b.history]
        assert agents == ["alice", "alice", "bob", "bob"]

    def test_history_timestamps_monotonic(self):
        b = Baton(payload="work", sender="alice")
        b.pass_to("bob")
        timestamps = [h[1] for h in b.history]
        assert timestamps == sorted(timestamps)


class TestBatonTimeout:
    def test_no_timeout_when_not_set(self):
        b = Baton(payload="work", sender="alice")
        assert b.check_timeout() is False

    def test_timeout_triggers(self):
        b = Baton(payload="work", sender="alice", timeout_seconds=0.0)
        time.sleep(0.01)
        assert b.check_timeout() is True
        assert b.state == BatonState.TIMED_OUT

    def test_timeout_not_yet(self):
        b = Baton(payload="work", sender="alice", timeout_seconds=100.0)
        assert b.check_timeout() is False

    def test_timeout_terminal_states_not_checked(self):
        b = Baton(payload="work", sender="alice", timeout_seconds=0.0)
        b.complete("alice")
        assert b.check_timeout() is False


class TestBatonFork:
    def test_fork_creates_child(self):
        b = Baton(payload={"key": "val"}, sender="alice", receiver="bob")
        child = b.fork("charlie")
        assert child.receiver == "charlie"
        assert child.sender == "bob"
        assert child.parent_id == b.id
        assert child.payload == b.payload
        assert child.id != b.id

    def test_fork_copies_metadata(self):
        b = Baton(payload="data", sender="a", metadata={"x": 1})
        child = b.fork("c")
        assert child.metadata == {"x": 1}
        child.metadata["x"] = 99
        assert b.metadata["x"] == 1  # independent copy


class TestBatonTiming:
    def test_age_increases(self):
        b = Baton(payload="work", sender="a")
        age1 = b.age()
        time.sleep(0.02)
        age2 = b.age()
        assert age2 > age1

    def test_idle_resets_on_state_change(self):
        b = Baton(payload="work", sender="a")
        time.sleep(0.02)
        idle1 = b.idle()
        b.pass_to("b")
        idle2 = b.idle()
        assert idle2 < idle1
