"""Tests for BatonRoute."""

import pytest

from purplepincher_baton import BatonRoute, RouteStep, StepType


class TestRouteCreation:
    def test_basic_route(self):
        r = BatonRoute(name="test", steps=[
            RouteStep(agent="a"),
            RouteStep(agent="b"),
            RouteStep(agent="c"),
        ])
        assert len(r) == 3

    def test_add_step_chaining(self):
        r = BatonRoute(name="test").add_step("a").add_step("b").add_step("c")
        assert len(r) == 3

    def test_unique_id(self):
        r1 = BatonRoute(name="test")
        r2 = BatonRoute(name="test")
        assert r1.id != r2.id


class TestRouteResolve:
    def test_sequential_resolve(self):
        r = BatonRoute(name="seq", steps=[
            RouteStep(agent="a"),
            RouteStep(agent="b"),
            RouteStep(agent="c"),
        ])
        groups = r.resolve()
        assert groups == [["a"], ["b"], ["c"]]

    def test_parallel_resolve(self):
        r = BatonRoute(name="par", steps=[
            RouteStep(agent="a", step_type=StepType.PARALLEL),
            RouteStep(agent="b", step_type=StepType.PARALLEL),
            RouteStep(agent="c"),
        ])
        groups = r.resolve()
        assert groups == [["a", "b"], ["c"]]

    def test_all_parallel(self):
        r = BatonRoute(name="allpar", steps=[
            RouteStep(agent="a", step_type=StepType.PARALLEL),
            RouteStep(agent="b", step_type=StepType.PARALLEL),
        ])
        groups = r.resolve()
        assert groups == [["a", "b"]]

    def test_conditional_included(self):
        r = BatonRoute(name="cond", steps=[
            RouteStep(agent="a"),
            RouteStep(agent="b", step_type=StepType.CONDITIONAL,
                      condition=lambda p: p.get("flag") is True),
            RouteStep(agent="c"),
        ])
        groups = r.resolve(payload={"flag": True})
        assert groups == [["a"], ["b"], ["c"]]

    def test_conditional_excluded(self):
        r = BatonRoute(name="cond", steps=[
            RouteStep(agent="a"),
            RouteStep(agent="b", step_type=StepType.CONDITIONAL,
                      condition=lambda p: p.get("flag") is True),
            RouteStep(agent="c"),
        ])
        groups = r.resolve(payload={"flag": False})
        assert groups == [["a"], ["c"]]

    def test_conditional_no_payload(self):
        r = BatonRoute(name="cond", steps=[
            RouteStep(agent="a"),
            RouteStep(agent="b", step_type=StepType.CONDITIONAL,
                      condition=lambda p: True),
        ])
        groups = r.resolve(payload=None)
        assert groups == [["a"]]

    def test_mixed_sequence(self):
        r = BatonRoute(name="mix", steps=[
            RouteStep(agent="a"),
            RouteStep(agent="b", step_type=StepType.PARALLEL),
            RouteStep(agent="c", step_type=StepType.PARALLEL),
            RouteStep(agent="d"),
        ])
        groups = r.resolve()
        assert groups == [["a"], ["b", "c"], ["d"]]


class TestRouteAgents:
    def test_flat_agents(self):
        r = BatonRoute(name="test", steps=[
            RouteStep(agent="a"),
            RouteStep(agent="b", step_type=StepType.PARALLEL),
            RouteStep(agent="c", step_type=StepType.PARALLEL),
            RouteStep(agent="d"),
        ])
        assert r.agents() == ["a", "b", "c", "d"]


class TestRouteValidation:
    def test_valid_route(self):
        r = BatonRoute(name="ok", steps=[
            RouteStep(agent="a"),
            RouteStep(agent="b"),
        ])
        assert r.validate() == []

    def test_conditional_no_condition(self):
        r = BatonRoute(name="bad", steps=[
            RouteStep(agent="a", step_type=StepType.CONDITIONAL),
        ])
        issues = r.validate()
        assert any("no condition" in i for i in issues)

    def test_empty_agent(self):
        r = BatonRoute(name="bad", steps=[RouteStep(agent="")])
        issues = r.validate()
        assert any("empty" in i for i in issues)

    def test_parallel_with_condition_warns(self):
        r = BatonRoute(name="bad", steps=[
            RouteStep(agent="a", step_type=StepType.PARALLEL, condition=lambda p: True),
        ])
        issues = r.validate()
        assert any("cannot have conditions" in i for i in issues)

    def test_repr(self):
        r = BatonRoute(name="test", steps=[RouteStep(agent="a")])
        assert "test" in repr(r)
        assert "1" in repr(r)
