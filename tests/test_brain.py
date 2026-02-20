"""Tests for the Brain neural decision engine."""

import numpy as np
import pytest

from aura.brain import Brain, ACTIONS, NUM_INPUTS, NUM_ACTIONS


@pytest.fixture
def brain():
    np.random.seed(42)
    return Brain()


class TestBrainCreation:
    def test_weight_shapes(self, brain):
        assert brain.weights_ih.shape == (NUM_INPUTS, 12)
        assert brain.weights_ho.shape == (12, NUM_ACTIONS)
        assert brain.bias_h.shape == (12,)
        assert brain.bias_o.shape == (NUM_ACTIONS,)


class TestBrainDecision:
    def test_decide_returns_valid_action(self, brain):
        inputs = np.random.rand(NUM_INPUTS).astype(np.float32)
        action = brain.decide(inputs)
        assert action in ACTIONS

    def test_different_inputs_can_produce_different_outputs(self, brain):
        actions = set()
        for _ in range(100):
            inputs = np.random.rand(NUM_INPUTS).astype(np.float32)
            actions.add(brain.decide(inputs))
        # With 100 random inputs, we should get at least 2 different actions
        assert len(actions) >= 2

    def test_get_action_scores(self, brain):
        inputs = np.random.rand(NUM_INPUTS).astype(np.float32)
        scores = brain.get_action_scores(inputs)
        assert len(scores) == NUM_ACTIONS
        assert all(a in scores for a in ACTIONS)
        # Probabilities should sum to ~1
        assert abs(sum(scores.values()) - 1.0) < 1e-5


class TestBrainEvolution:
    def test_mutate_creates_different_brain(self, brain):
        child = brain.mutate(rate=0.5)
        # Weights should differ
        assert not np.allclose(brain.weights_ih, child.weights_ih)

    def test_mutate_preserves_shapes(self, brain):
        child = brain.mutate()
        assert child.weights_ih.shape == brain.weights_ih.shape
        assert child.weights_ho.shape == brain.weights_ho.shape

    def test_crossover(self, brain):
        parent_b = Brain()
        child = Brain.crossover(brain, parent_b)
        assert child.weights_ih.shape == brain.weights_ih.shape
        # Child should be a mix, not identical to either parent
        assert not np.allclose(child.weights_ih, brain.weights_ih)
