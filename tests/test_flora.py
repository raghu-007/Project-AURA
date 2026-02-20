"""Tests for Flora entities."""

import pytest
from aura.config import load_config
from aura.world import World, Season
from aura.entity import EntityType, GrowthStage
from aura.flora import Flora, FloraType


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def world(config):
    return World(config)


class TestFloraCreation:
    def test_create_factory(self, world):
        plant = Flora.create(10, 10, FloraType.GRASS, world)
        assert plant.x == 10
        assert plant.y == 10
        assert plant.flora_type == FloraType.GRASS
        assert plant.entity_type == EntityType.FLORA
        assert plant.alive

    def test_create_sets_config(self, world):
        grass = Flora.create(5, 5, FloraType.GRASS, world)
        tree = Flora.create(5, 5, FloraType.TREE, world)
        assert tree._energy_value > grass._energy_value
        assert tree._growth_ticks > grass._growth_ticks


class TestFloraGrowth:
    def test_growth_stages(self, world):
        plant = Flora.create(10, 10, FloraType.GRASS, world)
        plant.growth_stage = GrowthStage.SEED
        plant.growth_progress = 0

        # Advance until sprout
        for _ in range(50):
            plant.update(world)
            if plant.growth_stage == GrowthStage.SPROUT:
                break
        assert plant.growth_stage in (GrowthStage.SPROUT, GrowthStage.MATURE)

    def test_season_affects_growth(self, world):
        plant1 = Flora.create(10, 10, FloraType.GRASS, world)
        plant1.growth_stage = GrowthStage.SEED
        plant1.growth_progress = 0

        # Spring growth
        world.season = Season.SPRING
        initial_mod = world.growth_modifier

        world.season = Season.WINTER
        winter_mod = world.growth_modifier

        assert initial_mod > winter_mod


class TestFloraDecay:
    def test_old_flora_decays(self, world):
        plant = Flora.create(10, 10, FloraType.GRASS, world)
        plant.age = plant._max_age + 1
        plant.update(world)
        assert plant.growth_stage == GrowthStage.DECAYING


class TestFloraSerialization:
    def test_to_dict(self, world):
        plant = Flora.create(10, 10, FloraType.BUSH, world)
        d = plant.to_dict()
        assert d["flora_type"] == "BUSH"
        assert "stage" in d
        assert d["type"] == "FLORA"
