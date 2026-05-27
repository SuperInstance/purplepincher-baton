"""Tests for the RelayStation class."""

import time

import pytest

from purplepincher_baton import BatonState, RelayStation


@pytest.fixture
def station():
    s = RelayStation()
    s.register_agent("alice")
    s.register_agent("bob")
    s.register_agent("charlie")
    return s


class TestAgentManagement:
    def test_register_agent(self, station):
        assert "alice" in station.agents

    def test_duplicate_registration(self, station):
        with pytest.raises(ValueError, match="already registered"):
            station.register_agent("alice")

    def test_agent_info(self, station):
        info = station.agent_info("alice")
        assert info.name == "alice"

    def test_unknown_agent_info(self, station):
        with pytest.raises(KeyError):
            station.agent_info("nobody")

    def test_register_with_metadata(self):
        s = RelayStation()
        s.register_agent("worker", role="renderer", priority=1)
        info = s.agent_info("worker")
        assert info.metadata["role"] == "renderer"


class TestBatonLifecycle:
    def test_create_baton(self, station):
        b = station.create_baton(payload={"task": "x"}, sender="alice", receiver="bob")
        assert b.state == BatonState.CREATED
        assert b.receiver == "bob"
        assert station.get_baton(b.id) is b

    def test_create_defaults_receiver_to_sender(self, station):
        b = station.create_baton(payload="work", sender="alice")
        assert b.receiver == "alice"

    def test_pass_baton(self, station):
        b = station.create_baton(payload="work", sender="alice", receiver="alice")
        station.pass_baton(b.id, from_agent="alice", to_agent="bob")
        assert b.state == BatonState.PASSED
        assert b.receiver == "bob"

    def test_pass_requires_registered_agents(self, station):
        b = station.create_baton(payload="work", sender="alice", receiver="alice")
        with pytest.raises(KeyError, match="not registered"):
            station.pass_baton(b.id, from_agent="alice", to_agent="nobody")

    def test_acknowledge(self, station):
        b = station.create_baton(payload="work", sender="alice", receiver="alice")
        station.pass_baton(b.id, from_agent="alice", to_agent="bob")
        station.acknowledge_baton(b.id, agent="bob")
        assert b.state == BatonState.ACKNOWLEDGED

    def test_complete(self, station):
        b = station.create_baton(payload="work", sender="alice", receiver="alice")
        station.complete_baton(b.id, agent="alice")
        assert b.state == BatonState.COMPLETED
        assert station.agent_info("alice").batons_completed == 1

    def test_drop(self, station):
        b = station.create_baton(payload="work", sender="alice", receiver="alice")
        station.drop_baton(b.id, agent="alice", reason="borked")
        assert b.state == BatonState.DROPPED
        assert station.agent_info("alice").batons_dropped == 1
        assert b.metadata["drop_reason"] == "borked"

    def test_fork(self, station):
        b = station.create_baton(payload="data", sender="alice", receiver="bob")
        child = station.fork_baton(b.id, new_receiver="charlie")
        assert child.parent_id == b.id
        assert child.receiver == "charlie"
        assert station.get_baton(child.id) is child

    def test_get_unknown_baton(self, station):
        with pytest.raises(KeyError, match="not found"):
            station.get_baton("nonexistent")


class TestQueries:
    def test_inbox(self, station):
        station.create_baton(payload="w1", sender="alice", receiver="bob")
        station.create_baton(payload="w2", sender="alice", receiver="bob")
        inbox = station.inbox("bob")
        assert len(inbox) == 2

    def test_inbox_excludes_terminal(self, station):
        b = station.create_baton(payload="w1", sender="alice", receiver="bob")
        station.complete_baton(b.id, agent="bob")
        assert len(station.inbox("bob")) == 0

    def test_active_batons(self, station):
        b1 = station.create_baton(payload="w1", sender="alice", receiver="alice")
        b2 = station.create_baton(payload="w2", sender="bob", receiver="bob")
        station.complete_baton(b1.id, agent="alice")
        active = station.active_batons()
        assert len(active) == 1
        assert active[0].id == b2.id

    def test_history_filter(self, station):
        b = station.create_baton(payload="work", sender="alice", receiver="alice")
        station.complete_baton(b.id, agent="alice")
        h = station.history(baton_id=b.id)
        assert len(h) >= 2
        assert h[0].action == "create"

    def test_history_all(self, station):
        station.create_baton(payload="w1", sender="alice", receiver="alice")
        station.create_baton(payload="w2", sender="bob", receiver="bob")
        assert len(station.history()) >= 4


class TestTimeouts:
    def test_check_timeouts(self, station):
        b = station.create_baton(
            payload="work", sender="alice", receiver="alice", timeout_seconds=0.0
        )
        time.sleep(0.01)
        timed_out = station.check_timeouts()
        assert len(timed_out) == 1
        assert timed_out[0].id == b.id
        assert b.state == BatonState.TIMED_OUT

    def test_check_timeouts_skips_terminal(self, station):
        b = station.create_baton(
            payload="work", sender="alice", receiver="alice", timeout_seconds=0.0
        )
        station.complete_baton(b.id, agent="alice")
        assert station.check_timeouts() == []
