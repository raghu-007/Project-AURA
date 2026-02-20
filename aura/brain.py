"""Lightweight neural decision engine for Fauna agents."""

from __future__ import annotations

import numpy as np


# ── Action labels ──────────────────────────────────────────────
ACTIONS = ["wander", "forage", "flee", "chase", "reproduce", "rest"]
NUM_ACTIONS = len(ACTIONS)

# ── Input labels ───────────────────────────────────────────────
# hunger, energy, fear, nearest_food_dist, nearest_predator_dist,
# nearest_mate_dist, time_of_day, crowding
NUM_INPUTS = 8
HIDDEN_SIZE = 12


class Brain:
    """
    A simple feed-forward neural network that maps sensory inputs
    to action scores.

    Architecture:  inputs(8) → hidden(12, tanh) → actions(6, softmax)

    Weights are inherited from parents with small mutations,
    enabling evolution of behavior without gradient descent.
    """

    def __init__(
        self,
        weights_ih: np.ndarray | None = None,
        bias_h: np.ndarray | None = None,
        weights_ho: np.ndarray | None = None,
        bias_o: np.ndarray | None = None,
    ) -> None:
        if weights_ih is not None:
            self.weights_ih = weights_ih.copy()
            self.bias_h = bias_h.copy()
            self.weights_ho = weights_ho.copy()
            self.bias_o = bias_o.copy()
        else:
            # Xavier-ish initialization
            self.weights_ih = np.random.randn(NUM_INPUTS, HIDDEN_SIZE).astype(np.float32) * 0.5
            self.bias_h = np.zeros(HIDDEN_SIZE, dtype=np.float32)
            self.weights_ho = np.random.randn(HIDDEN_SIZE, NUM_ACTIONS).astype(np.float32) * 0.5
            self.bias_o = np.zeros(NUM_ACTIONS, dtype=np.float32)

    WEIGHT_CLIP = 5.0  # Prevent runaway weights over generations

    def decide(self, inputs: np.ndarray) -> str:
        """
        Given a normalized input vector, return the chosen action name.

        Args:
            inputs: numpy array of shape (NUM_INPUTS,), values in [0, 1]

        Returns:
            The action name with the highest score.
        """
        # Sanitize inputs — guard against NaN/Inf
        inputs = np.nan_to_num(inputs, nan=0.0, posinf=1.0, neginf=0.0)
        inputs = np.clip(inputs, 0.0, 1.0)

        # Hidden layer with tanh activation
        hidden = np.tanh(inputs @ self.weights_ih + self.bias_h)

        # Output layer
        logits = hidden @ self.weights_ho + self.bias_o

        # Softmax for probabilities
        exp_logits = np.exp(logits - np.max(logits))  # numerical stability
        probs = exp_logits / exp_logits.sum()

        # Guard against NaN in probs (fallback to uniform)
        if np.any(np.isnan(probs)):
            probs = np.ones(NUM_ACTIONS, dtype=np.float32) / NUM_ACTIONS

        # Weighted random choice (adds stochasticity)
        action_idx = np.random.choice(NUM_ACTIONS, p=probs)
        return ACTIONS[action_idx]

    def get_action_scores(self, inputs: np.ndarray) -> dict[str, float]:
        """Return raw scores for all actions (for debugging / viz)."""
        inputs = np.nan_to_num(inputs, nan=0.0, posinf=1.0, neginf=0.0)
        hidden = np.tanh(inputs @ self.weights_ih + self.bias_h)
        logits = hidden @ self.weights_ho + self.bias_o
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / exp_logits.sum()
        return {action: float(prob) for action, prob in zip(ACTIONS, probs)}

    def _clip_weights(self) -> None:
        """Clip all weights to prevent runaway values."""
        np.clip(self.weights_ih, -self.WEIGHT_CLIP, self.WEIGHT_CLIP, out=self.weights_ih)
        np.clip(self.bias_h, -self.WEIGHT_CLIP, self.WEIGHT_CLIP, out=self.bias_h)
        np.clip(self.weights_ho, -self.WEIGHT_CLIP, self.WEIGHT_CLIP, out=self.weights_ho)
        np.clip(self.bias_o, -self.WEIGHT_CLIP, self.WEIGHT_CLIP, out=self.bias_o)

    def mutate(self, rate: float = 0.1) -> Brain:
        """
        Create a mutated copy of this brain.

        Used during reproduction to produce offspring with
        slightly different behavior.
        """
        child = Brain(
            weights_ih=self.weights_ih,
            bias_h=self.bias_h,
            weights_ho=self.weights_ho,
            bias_o=self.bias_o,
        )
        # Add Gaussian noise proportional to mutation rate
        child.weights_ih += np.random.randn(*child.weights_ih.shape).astype(np.float32) * rate
        child.bias_h += np.random.randn(*child.bias_h.shape).astype(np.float32) * rate
        child.weights_ho += np.random.randn(*child.weights_ho.shape).astype(np.float32) * rate
        child.bias_o += np.random.randn(*child.bias_o.shape).astype(np.float32) * rate
        child._clip_weights()
        return child

    @staticmethod
    def crossover(parent_a: Brain, parent_b: Brain) -> Brain:
        """Create a child brain by mixing two parent brains."""
        mask_ih = np.random.random(parent_a.weights_ih.shape) > 0.5
        mask_ho = np.random.random(parent_a.weights_ho.shape) > 0.5

        child = Brain(
            weights_ih=np.where(mask_ih, parent_a.weights_ih, parent_b.weights_ih),
            bias_h=(parent_a.bias_h + parent_b.bias_h) / 2,
            weights_ho=np.where(mask_ho, parent_a.weights_ho, parent_b.weights_ho),
            bias_o=(parent_a.bias_o + parent_b.bias_o) / 2,
        )
        return child
