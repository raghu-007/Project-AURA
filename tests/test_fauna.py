"""Tests for Fauna agents."""

import pytest
from aura.config import load_config
from aura.world import World
from aura.entity import EntityType
from aura.fauna import Fauna, Genetics
from aura.ecosystem import populate_world


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def world(config):
    w = World(config)
    return w


class TestFaunaCreation:
    def test_initial_state(self):
        f = Fauna(10, 10, species=EntityType.HERBIVORE)
        assert f.x == 10
        assert f.y == 10
        assert f.species == EntityType.HERBIVORE
        assert f.energy == 80.0
        assert f.hunger == 30.0
        assert f.alive

    def test_genetics_defaults(self):
        g = Genetics()
        assert g.speed == 1.0
        assert g.vision_range == 6.0
        assert g.size == 1.0


class TestFaunaBehavior:
    def test_energy_decays(self, world):
        f = Fauna(10, 10, species=EntityType.HERBIVORE)
        world.add_entity(f)
        initial_energy = f.energy
        f.update(world)
        assert f.energy < initial_energy

    def test_hunger_increases(self, world):
        f = Fauna(10, 10, species=EntityType.HERBIVORE)
        world.add_entity(f)
        initial_hunger = f.hunger
        f.update(world)
        assert f.hunger > initial_hunger

    def test_dies_at_zero_energy(self, world):
        f = Fauna(10, 10, species=EntityType.HERBIVORE)
        f.energy = 0.1
        world.add_entity(f)
        f.update(world)
        # Should be queued for death
        assert f in world._deaths or not f.alive


class TestGenetics:
    def test_mutation(self):
        g = Genetics(speed=1.0, vision_range=6.0, size=1.0)
        mutated = g.mutate(rate=0.5)
        # Values should differ (with high mutation rate)
        differs = (
            mutated.speed != g.speed or
            mutated.vision_range != g.vision_range or
            mutated.size != g.size
        )
        assert differs

    def test_mutation_clamps_minimum(self):
        g = Genetics(speed=0.3, vision_range=2.0, size=0.3)
        for _ in range(50):
            mutated = g.mutate(rate=1.0)
            assert mutated.speed >= 0.3
            assert mutated.vision_range >= 2
            assert mutated.size >= 0.3


class TestFaunaSerialization:
    def test_to_dict(self):
        f = Fauna(10, 10, species=EntityType.HERBIVORE)
        d = f.to_dict()
        assert d["species"] == "HERBIVORE"
        assert "hunger" in d
        assert "generation" in d
        assert "speed" in d
