"""Tests for the Ecosystem module."""

import pytest
from aura.config import load_config
from aura.world import World
from aura.entity import EntityType
from aura.ecosystem import populate_world
from aura.stats import StatsTracker


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def populated_world(config):
    w = World(config)
    w.stats = StatsTracker()
    populate_world(w)
    return w


class TestEcosystemPopulation:
    def test_populates_flora(self, populated_world):
        flora = [e for e in populated_world.entities if e.entity_type == EntityType.FLORA]
        assert len(flora) > 0

    def test_populates_fauna(self, populated_world):
        fauna = [e for e in populated_world.entities if e.entity_type != EntityType.FLORA]
        assert len(fauna) > 0

    def test_correct_species_counts(self, populated_world, config):
        herbs = [e for e in populated_world.entities if e.entity_type == EntityType.HERBIVORE]
        preds = [e for e in populated_world.entities if e.entity_type == EntityType.PREDATOR]
        omnis = [e for e in populated_world.entities if e.entity_type == EntityType.OMNIVORE]
        assert len(herbs) == config.fauna.initial_herbivores
        assert len(preds) == config.fauna.initial_predators
        assert len(omnis) == config.fauna.initial_omnivores


class TestSimulationRun:
    def test_simulation_runs_without_crash(self, populated_world):
        """Run 50 ticks and ensure nothing crashes."""
        for _ in range(50):
            populated_world.tick()
        assert populated_world.tick_count == 50

    def test_stats_recorded(self, populated_world):
        for _ in range(10):
            populated_world.tick()
        snapshot = populated_world.stats.current_snapshot()
        assert "population" in snapshot
        assert "biodiversity" in snapshot


class TestStatsTracker:
    def test_summary_string(self, populated_world):
        for _ in range(5):
            populated_world.tick()
        summary = populated_world.stats.summary_string()
        assert "Flora" in summary
        assert "Herb" in summary
