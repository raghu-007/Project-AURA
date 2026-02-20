"""Tests for the World simulation engine."""

import pytest
from aura.config import load_config
from aura.world import World, Season, TimeOfDay
from aura.entity import Entity, EntityType


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def world(config):
    return World(config)


class TestWorldCreation:
    def test_dimensions(self, world, config):
        assert world.width == config.world.width
        assert world.height == config.world.height

    def test_initial_state(self, world):
        assert world.tick_count == 0
        assert world.season == Season.SPRING
        assert len(world.entities) == 0

    def test_soil_nutrients_initialized(self, world):
        assert world.soil_nutrients.shape == (world.height, world.width)
        assert world.soil_nutrients.min() == 1.0


class TestEntityManagement:
    def test_add_entity(self, world):
        e = Entity(5, 5, entity_type=EntityType.FLORA)
        world.add_entity(e)
        assert len(world.entities) == 1
        assert world.entities[0] is e

    def test_add_entity_clamps_position(self, world):
        e = Entity(9999, -5, entity_type=EntityType.FLORA)
        world.add_entity(e)
        assert 0 <= e.x < world.width
        assert 0 <= e.y < world.height

    def test_remove_entity(self, world):
        e = Entity(5, 5, entity_type=EntityType.FLORA)
        world.add_entity(e)
        world.remove_entity(e)
        assert len(world.entities) == 0

    def test_move_entity_wraps(self, world):
        e = Entity(0, 0, entity_type=EntityType.HERBIVORE)
        world.add_entity(e)
        world.move_entity(e, -1, -1)
        assert e.x == world.width - 1
        assert e.y == world.height - 1

    def test_get_neighbors(self, world):
        e1 = Entity(10, 10, entity_type=EntityType.FLORA)
        e2 = Entity(11, 10, entity_type=EntityType.FLORA)
        e3 = Entity(50, 50, entity_type=EntityType.FLORA)  # far away
        world.add_entity(e1)
        world.add_entity(e2)
        world.add_entity(e3)
        neighbors = world.get_neighbors(10, 10, 3, EntityType.FLORA)
        assert e2 in neighbors
        assert e3 not in neighbors


class TestTimeSystems:
    def test_tick_advances(self, world):
        world.tick()
        assert world.tick_count == 1

    def test_season_changes(self, world):
        # Fast-forward past one season
        for _ in range(world.config.world.season_length + 1):
            world.tick()
        assert world.season == Season.SUMMER

    def test_random_position(self, world):
        for _ in range(100):
            x, y = world.random_position()
            assert 0 <= x < world.width
            assert 0 <= y < world.height


class TestWorldSerialization:
    def test_to_dict(self, world):
        data = world.to_dict()
        assert "tick" in data
        assert "width" in data
        assert "height" in data
        assert "season" in data
        assert "entities" in data
