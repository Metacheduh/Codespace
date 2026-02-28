"""Tests for DAG-based job dependency resolution."""

import pytest

from agent_manager.dag import CyclicDependencyError, JobDAG, MissingDependencyError


class TestJobDAG:
    def test_empty_dag(self):
        dag = JobDAG()
        assert dag.topological_order() == []

    def test_single_job_no_deps(self):
        dag = JobDAG()
        dag.add_job("job_a")
        assert dag.topological_order() == ["job_a"]

    def test_linear_dependency(self):
        dag = JobDAG()
        dag.add_job("job_a")
        dag.add_job("job_b", depends_on=["job_a"])
        dag.add_job("job_c", depends_on=["job_b"])
        order = dag.topological_order()
        assert order.index("job_a") < order.index("job_b")
        assert order.index("job_b") < order.index("job_c")

    def test_diamond_dependency(self):
        dag = JobDAG()
        dag.add_job("root")
        dag.add_job("left", depends_on=["root"])
        dag.add_job("right", depends_on=["root"])
        dag.add_job("sink", depends_on=["left", "right"])
        order = dag.topological_order()
        assert order.index("root") < order.index("left")
        assert order.index("root") < order.index("right")
        assert order.index("left") < order.index("sink")
        assert order.index("right") < order.index("sink")

    def test_cyclic_dependency_raises(self):
        dag = JobDAG()
        dag.add_job("a", depends_on=["b"])
        dag.add_job("b", depends_on=["a"])
        with pytest.raises(CyclicDependencyError):
            dag.validate()

    def test_is_ready(self):
        dag = JobDAG()
        dag.add_job("a")
        dag.add_job("b", depends_on=["a"])
        assert dag.is_ready("a", set()) is True
        assert dag.is_ready("b", set()) is False
        assert dag.is_ready("b", {"a"}) is True

    def test_get_dependencies(self):
        dag = JobDAG()
        dag.add_job("a")
        dag.add_job("b", depends_on=["a"])
        assert dag.get_dependencies("a") == []
        assert dag.get_dependencies("b") == ["a"]
