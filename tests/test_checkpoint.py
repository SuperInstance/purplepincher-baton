"""Tests for Checkpoint."""

import time

import pytest

from purplepincher_baton import BatonRoute, Checkpoint, CheckpointStatus, RouteStep


@pytest.fixture
def route():
    return BatonRoute(name="test-route", steps=[
        RouteStep(agent="loader", label="Load"),
        RouteStep(agent="renderer", label="Render"),
        RouteStep(agent="uploader", label="Upload"),
    ])


@pytest.fixture
def checkpoint(route):
    return Checkpoint(route=route, baton_id="baton-123")


class TestCheckpointCreation:
    def test_steps_created_from_route(self, checkpoint, route):
        assert len(checkpoint.steps) == len(route.steps)

    def test_all_steps_pending(self, checkpoint):
        assert all(s.status == CheckpointStatus.PENDING for s in checkpoint.steps)

    def test_agents_match(self, checkpoint):
        agents = [s.agent for s in checkpoint.steps]
        assert agents == ["loader", "renderer", "uploader"]


class TestCheckpointProgress:
    def test_start_and_complete(self, checkpoint):
        checkpoint.start_step(0)
        assert checkpoint.steps[0].status == CheckpointStatus.IN_PROGRESS
        assert checkpoint.current_index == 0

        checkpoint.complete_step(0, result={"files": 42})
        assert checkpoint.steps[0].status == CheckpointStatus.COMPLETED
        assert checkpoint.steps[0].result == {"files": 42}
        assert checkpoint.progress() == 1
        assert checkpoint.current_index == 1  # next pending

    def test_skip_step(self, checkpoint):
        checkpoint.skip_step(1)
        assert checkpoint.steps[1].status == CheckpointStatus.SKIPPED
        assert checkpoint.progress() == 1

    def test_fail_step(self, checkpoint):
        checkpoint.fail_step(2, error="upload failed")
        assert checkpoint.steps[2].status == CheckpointStatus.FAILED
        assert checkpoint.steps[2].error == "upload failed"
        assert checkpoint.is_failed() is True

    def test_full_lifecycle(self, checkpoint):
        checkpoint.start_step(0)
        checkpoint.complete_step(0)
        checkpoint.start_step(1)
        checkpoint.complete_step(1)
        checkpoint.start_step(2)
        checkpoint.complete_step(2)
        assert checkpoint.is_complete() is True
        assert checkpoint.is_failed() is False
        assert checkpoint.progress_fraction() == 1.0

    def test_out_of_range(self, checkpoint):
        with pytest.raises(IndexError):
            checkpoint.start_step(99)


class TestCheckpointCurrentStep:
    def test_initial_current(self, checkpoint):
        assert checkpoint.current_index == 0

    def test_no_current_when_complete(self, checkpoint):
        for i in range(3):
            checkpoint.complete_step(i)
        assert checkpoint.current_step is None
        assert checkpoint.current_index is None


class TestStepCheckpointTiming:
    def test_duration_after_complete(self, checkpoint):
        checkpoint.start_step(0)
        time.sleep(0.02)
        checkpoint.complete_step(0)
        dur = checkpoint.steps[0].duration()
        assert dur is not None
        assert dur >= 0.01

    def test_duration_none_before_start(self, checkpoint):
        assert checkpoint.steps[0].duration() is None


class TestCheckpointSummary:
    def test_summary_structure(self, checkpoint):
        checkpoint.start_step(0)
        checkpoint.complete_step(0, result={"ok": True})
        summary = checkpoint.summary()
        assert summary["route"] == "test-route"
        assert summary["baton_id"] == "baton-123"
        assert summary["progress"] == "1/3"
        assert summary["fraction"] == pytest.approx(0.33, abs=0.01)
        assert len(summary["steps"]) == 3
        assert summary["steps"][0]["status"] == "completed"
