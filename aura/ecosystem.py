"""Ecosystem mechanics — population seeding, food chain, and events."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from .entity import EntityType
from .fauna import Fauna, Genetics
from .flora import Flora, FloraType

if TYPE_CHECKING:
    from .config import AuraConfig
    from .world import World


def populate_world(world: World) -> None:
    """Seed the world with initial flora and fauna populations."""
    cfg = world.config

    # ── Flora ──────────────────────────────────────────────────
    _spawn_flora(world, FloraType.GRASS, cfg.flora.initial_grass)
    _spawn_flora(world, FloraType.BUSH, cfg.flora.initial_bushes)
    _spawn_flora(world, FloraType.TREE, cfg.flora.initial_trees)

    # ── Fauna ──────────────────────────────────────────────────
    _spawn_fauna(world, EntityType.HERBIVORE, cfg.fauna.initial_herbivores, cfg)
    _spawn_fauna(world, EntityType.PREDATOR, cfg.fauna.initial_predators, cfg)
    _spawn_fauna(world, EntityType.OMNIVORE, cfg.fauna.initial_omnivores, cfg)


def _spawn_flora(world: World, flora_type: FloraType, count: int) -> None:
    """Place flora randomly, with some in mature stage for immediate food."""
    for i in range(count):
        x, y = world.random_position()
        plant = Flora.create(x, y, flora_type, world)

        # 60% start mature so fauna has food at the beginning
        if random.random() < 0.6:
            plant.growth_stage = plant.growth_stage.__class__.MATURE
            from .entity import GrowthStage
            plant.growth_stage = GrowthStage.MATURE
            plant.growth_progress = plant._growth_ticks

        world.add_entity(plant)


def _spawn_fauna(world: World, species: EntityType, count: int, cfg: AuraConfig) -> None:
    """Spawn fauna with species-appropriate genetics."""
    for _ in range(count):
        x, y = world.random_position()

        # Species-specific base genetics
        if species == EntityType.HERBIVORE:
            genetics = Genetics(
                speed=cfg.fauna.herbivore.speed + random.gauss(0, 0.1),
                vision_range=cfg.fauna.vision_radius + random.gauss(0, 0.5),
                size=cfg.fauna.herbivore.size + random.gauss(0, 0.1),
                metabolism=0.8 + random.gauss(0, 0.05),
            )
        elif species == EntityType.PREDATOR:
            genetics = Genetics(
                speed=cfg.fauna.predator.speed + random.gauss(0, 0.1),
                vision_range=cfg.fauna.vision_radius + random.gauss(0, 0.5),
                size=cfg.fauna.predator.size + random.gauss(0, 0.1),
                metabolism=1.2 + random.gauss(0, 0.05),
            )
        else:  # Omnivore
            genetics = Genetics(
                speed=cfg.fauna.omnivore.speed + random.gauss(0, 0.1),
                vision_range=cfg.fauna.vision_radius + random.gauss(0, 0.5),
                size=cfg.fauna.omnivore.size + random.gauss(0, 0.1),
                metabolism=1.0 + random.gauss(0, 0.05),
            )

        agent = Fauna(x=x, y=y, species=species, genetics=genetics)
        agent.energy = 70.0 + random.random() * 20
        world.add_entity(agent)
